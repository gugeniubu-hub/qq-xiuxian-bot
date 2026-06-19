from __future__ import annotations

import time
from typing import Any

import httpx
from nonebot import logger

from xianbot.config import get_settings


_daily_bucket: str | None = None
_daily_calls = 0
_last_user_call: dict[str, float] = {}


def llm_available() -> bool:
    settings = get_settings()
    return bool(settings.llm_enabled and settings.llm_api_key.strip())


def _reserve_call(user_id: str) -> bool:
    global _daily_bucket, _daily_calls
    settings = get_settings()
    today = time.strftime("%Y-%m-%d")
    if _daily_bucket != today:
        _daily_bucket = today
        _daily_calls = 0
        _last_user_call.clear()
    if _daily_calls >= max(0, int(settings.llm_daily_limit)):
        return False

    now = time.monotonic()
    cooldown = max(0, int(settings.llm_user_cooldown_seconds))
    last = _last_user_call.get(user_id)
    if last is not None and now - last < cooldown:
        return False

    _daily_calls += 1
    _last_user_call[user_id] = now
    return True


def _clean_text(text: str) -> str:
    settings = get_settings()
    cleaned = text.strip()
    for prefix in ("旁白：", "旁白:", "说书人：", "说书人:"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    max_chars = max(80, int(settings.llm_max_output_chars))
    if len(cleaned) > max_chars:
        cleaned = cleaned[: max_chars - 1].rstrip("，。；、 \n") + "。"
    return cleaned


async def _chat_completion(messages: list[dict[str, str]]) -> str | None:
    settings = get_settings()
    base_url = settings.llm_base_url.rstrip("/")
    url = f"{base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0.85,
        "max_tokens": max(64, int(settings.llm_max_tokens)),
        "stream": False,
    }
    if settings.llm_provider.lower() == "deepseek":
        payload["thinking"] = {"type": "disabled"}

    try:
        async with httpx.AsyncClient(timeout=float(settings.llm_timeout_seconds)) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("qxian llm narration skipped: {}", exc)
        return None

    choices = data.get("choices")
    if not choices:
        return None
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    return _clean_text(content)


async def narrate_adventure(user_id: str, summary: dict[str, object], fallback: str) -> str:
    if not llm_available() or not _reserve_call(user_id):
        return fallback
    prompt = (
        "你是QQ群文字修仙游戏的说书人。根据结构化结果润色一段历练描述。"
        "只写剧情旁白，不改数值，不承诺额外奖励，不超过120字。"
    )
    result = await _chat_completion(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": str(summary)},
        ]
    )
    return result or fallback


async def narrate_duel(user_id: str, summary: dict[str, object], fallback_rounds: list[str]) -> list[str]:
    if not llm_available() or not _reserve_call(user_id):
        return fallback_rounds
    prompt = (
        "你是QQ群文字修仙游戏的斗法说书人。根据固定战斗结果润色2到4行战报。"
        "不能改变胜负、roll、奖励、伤害和任何数值，不新增功法或掉落。每行不超过45字。"
    )
    result = await _chat_completion(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": str(summary)},
        ]
    )
    if not result:
        return fallback_rounds
    lines = [line.strip("- 　") for line in result.splitlines() if line.strip()]
    return lines[:4] or fallback_rounds


async def suggest_command(user_id: str, message: str) -> str | None:
    if not llm_available() or not _reserve_call(user_id):
        return None
    prompt = (
        "你是QQ群文字修仙游戏的指令助手。玩家发了无法识别的内容，"
        "请推测最可能的已有指令，并用一句中文提示。不要执行指令，不超过60字。"
        "可用指令包括：入道、面板、属性、签到、历练、探索 地图名、地图、奇遇、突破、"
        "闭关 分钟 模式、出关、背包、服用 物品名、炼丹 丹药名、斗法 @目标、"
        "宗门列表、加入宗门、我的功法、功法详情、请法、主修功法、坊市、排行、帮助。"
    )
    return await _chat_completion(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": message[:160]},
        ]
    )
