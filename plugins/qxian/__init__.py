from nonebot import get_driver, on_command
from nonebot.adapters.onebot.v11 import MessageEvent

from xianbot.config import get_settings
from xianbot.database import initialize_database
from xianbot.game_text import (
    DESIGN_SUMMARY_TEXT,
    HELP_TEXT,
    MARKET_SUMMARY_TEXT,
    REBIRTH_SUMMARY_TEXT,
    SECT_SUMMARY_TEXT,
)
from xianbot.services import create_player_if_missing, get_player_status, list_sects_for_player, rebirth, sign_in

driver = get_driver()
settings = get_settings()

help_cmd = on_command("帮助", aliases={"修仙帮助", "仙途帮助"})
design_cmd = on_command("设计", aliases={"玩法设计", "初版设计"})
sect_cmd = on_command("宗门帮助", aliases={"宗门设计"})
market_cmd = on_command("坊市帮助", aliases={"坊市设计"})
rebirth_help_cmd = on_command("轮回帮助", aliases={"转世帮助", "轮回设计"})
enter_path_cmd = on_command("入道")
status_cmd = on_command("我的状态", aliases={"状态", "面板"})
sign_in_cmd = on_command("签到", aliases={"修仙签到"})
sect_list_cmd = on_command("宗门列表")
rebirth_cmd = on_command("转世", aliases={"轮回"})


@driver.on_startup
async def startup() -> None:
    initialize_database(settings.database_url)


@help_cmd.handle()
async def handle_help(event: MessageEvent) -> None:
    await help_cmd.finish(HELP_TEXT.format(user_id=event.get_user_id()))


@design_cmd.handle()
async def handle_design() -> None:
    await design_cmd.finish(DESIGN_SUMMARY_TEXT)


@sect_cmd.handle()
async def handle_sect() -> None:
    await sect_cmd.finish(SECT_SUMMARY_TEXT)


@market_cmd.handle()
async def handle_market() -> None:
    await market_cmd.finish(MARKET_SUMMARY_TEXT)


@rebirth_help_cmd.handle()
async def handle_rebirth() -> None:
    await rebirth_help_cmd.finish(REBIRTH_SUMMARY_TEXT)


@enter_path_cmd.handle()
async def handle_enter_path(event: MessageEvent) -> None:
    user_id = event.get_user_id()
    player, created = await create_player_if_missing(user_id, event.sender.nickname or user_id)
    if created:
        await enter_path_cmd.finish(
            f"道友入道成功，灵根为{player.root_type.value}。"
            f"初始灵石 {player.spirit_stones}，福缘 {player.fortune}。"
            "发送“我的状态”查看详情。"
        )
    await enter_path_cmd.finish(
        f"道友早已踏上仙途，当前境界 {player.realm.value}，灵根 {player.root_type.value}。"
    )


@status_cmd.handle()
async def handle_status(event: MessageEvent) -> None:
    player = await get_player_status(event.get_user_id())
    if player is None:
        await status_cmd.finish("你还未入道，发送“入道”开始。")
    await status_cmd.finish(
        "\n".join(
            [
                f"道号: {player.nickname}",
                f"灵根: {player.root_type.value}",
                f"境界: {player.realm.value}",
                f"修为: {player.cultivation}",
                f"灵石: {player.spirit_stones}",
                f"福缘: {player.fortune}",
                f"悟性: {player.comprehension}",
                f"寿元: {player.age}/{player.lifespan}",
                f"轮回: {player.rebirth_count} 转",
                f"前尘点: {player.legacy_points}",
            ]
        )
    )


@sign_in_cmd.handle()
async def handle_sign_in(event: MessageEvent) -> None:
    user_id = event.get_user_id()
    player = await get_player_status(user_id)
    if player is None:
        await sign_in_cmd.finish("你还未入道，发送“入道”开始。")

    try:
        result = await sign_in(user_id)
    except ValueError as exc:
        if str(exc) == "already_signed":
            await sign_in_cmd.finish("今天已经签到过了，明日再来。")
        raise

    extra = "今日鸿运加身。" if result.fortune_roll >= 96 else "气运平稳。"
    await sign_in_cmd.finish(
        f"签到完成，获得灵石 {result.base_reward}，福缘池分红 {result.pool_reward}，"
        f"修为提升后总计 {result.total_cultivation}。{extra}"
    )


@sect_list_cmd.handle()
async def handle_sect_list(event: MessageEvent) -> None:
    sects = await list_sects_for_player(event.get_user_id())
    if not sects:
        await sect_list_cmd.finish("当前没有可加入的宗门。")

    lines = ["当前可见宗门:"]
    for sect in sects:
        gate = ""
        if int(sect["required_rebirth_count"]) > 0:
            gate = f" [需{sect['required_rebirth_count']}转]"
        lines.append(f"- {sect['name']}{gate}: {sect['description']}")
    await sect_list_cmd.finish("\n".join(lines))


@rebirth_cmd.handle()
async def handle_rebirth_action(event: MessageEvent) -> None:
    try:
        result = await rebirth(event.get_user_id())
    except ValueError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await rebirth_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "rebirth_locked":
            await rebirth_cmd.finish("转世条件未满足: 需要化神圆满，并持有至少 1 枚轮回印记。")
        raise

    unlocks = "、".join(result.unlocked_features) if result.unlocked_features else "暂无"
    await rebirth_cmd.finish(
        f"道友已转世重修，前尘点 +{result.legacy_points_gained}，"
        f"新灵根保底为 {result.new_root_floor}，解锁内容: {unlocks}。"
    )
