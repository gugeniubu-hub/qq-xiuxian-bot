import asyncio

from xianbot.config import get_settings
from xianbot.llm import narrate_adventure, narrate_duel, suggest_command


def test_llm_disabled_keeps_fallback(monkeypatch) -> None:
    monkeypatch.setenv("QXIAN_LLM_ENABLED", "false")
    monkeypatch.setenv("QXIAN_LLM_API_KEY", "")
    get_settings.cache_clear()

    async def scenario() -> None:
        assert await narrate_adventure("u1", {"roll": 88}, "原本文案") == "原本文案"
        assert await narrate_duel("u1", {"winner": "甲"}, ["第1回合"]) == ["第1回合"]
        assert await suggest_command("u1", "/foo") is None

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_llm_failure_keeps_fallback(monkeypatch) -> None:
    monkeypatch.setenv("QXIAN_LLM_ENABLED", "true")
    monkeypatch.setenv("QXIAN_LLM_API_KEY", "test-key")
    get_settings.cache_clear()

    async def fail_chat(messages):
        return None

    monkeypatch.setattr("xianbot.llm._chat_completion", fail_chat)

    async def scenario() -> None:
        assert await narrate_adventure("u2", {"roll": 99}, "本地历练") == "本地历练"
        assert await narrate_duel("u3", {"winner": "乙"}, ["本地战报"]) == ["本地战报"]

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_llm_success_uses_narration(monkeypatch) -> None:
    monkeypatch.setenv("QXIAN_LLM_ENABLED", "true")
    monkeypatch.setenv("QXIAN_LLM_API_KEY", "test-key")
    monkeypatch.setenv("QXIAN_LLM_USER_COOLDOWN_SECONDS", "0")
    get_settings.cache_clear()

    async def fake_chat(messages):
        return "霜风穿林，剑光在夜色中一闪而没。"

    monkeypatch.setattr("xianbot.llm._chat_completion", fake_chat)

    async def scenario() -> None:
        assert await narrate_adventure("u4", {"roll": 100}, "本地") == "霜风穿林，剑光在夜色中一闪而没。"
        assert await narrate_duel("u4", {"winner": "甲"}, ["本地"]) == ["霜风穿林，剑光在夜色中一闪而没。"]

    asyncio.run(scenario())
    get_settings.cache_clear()
