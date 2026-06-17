from nonebot import get_driver, on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent
from nonebot.params import CommandArg

from xianbot.config import get_settings
from xianbot.database import initialize_database
from xianbot.game_text import (
    DESIGN_SUMMARY_TEXT,
    HELP_TEXT,
    MARKET_SUMMARY_TEXT,
    REBIRTH_SUMMARY_TEXT,
    SECT_SUMMARY_TEXT,
)
from xianbot.services import (
    GameError,
    adventure,
    breakthrough,
    buy_market_listing,
    create_market_listing,
    create_player_if_missing,
    end_meditation,
    get_player_methods,
    get_player_status,
    get_rankings,
    join_sect,
    list_inventory,
    list_market,
    list_sects_for_player,
    rebirth,
    sign_in,
    start_meditation,
)

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
join_sect_cmd = on_command("加入宗门")
methods_cmd = on_command("我的功法", aliases={"宗门传承"})
inventory_cmd = on_command("背包")
adventure_cmd = on_command("历练")
breakthrough_cmd = on_command("突破")
meditate_cmd = on_command("闭关")
leave_meditation_cmd = on_command("出关")
market_list_cmd = on_command("坊市")
market_create_cmd = on_command("坊市上架")
market_buy_cmd = on_command("坊市购买", aliases={"购买"})
ranking_cmd = on_command("排行", aliases={"排行榜"})


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
    except GameError as exc:
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
    except GameError as exc:
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


@join_sect_cmd.handle()
async def handle_join_sect(event: MessageEvent, args: Message = CommandArg()) -> None:
    sect_name = args.extract_plain_text().strip()
    if not sect_name:
        await join_sect_cmd.finish("请输入宗门名，例如：加入宗门 青岚宗")
    try:
        result = await join_sect(event.get_user_id(), sect_name)
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await join_sect_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "already_in_sect":
            await join_sect_cmd.finish("你已有宗门归属，暂不支持二次加入。")
        if reason == "sect_not_found":
            await join_sect_cmd.finish("未找到该宗门，先发送“宗门列表”看看。")
        if reason == "sect_locked":
            await join_sect_cmd.finish("该宗门需要更高轮回次数才能加入。")
        raise

    extra = f"，并得传功法《{result.method_name}》" if result.method_name else ""
    await join_sect_cmd.finish(f"你已拜入 {result.sect_name}{extra}。")


@methods_cmd.handle()
async def handle_methods(event: MessageEvent) -> None:
    player = await get_player_status(event.get_user_id())
    if player is None:
        await methods_cmd.finish("你还未入道，发送“入道”开始。")
    methods = await get_player_methods(event.get_user_id())
    if not methods:
        await methods_cmd.finish("你目前尚未习得功法，先加入宗门吧。")

    lines = ["你已习得的功法:"]
    for method in methods:
        lines.append(
            f"- {method['name']} ({method['realm_requirement']}) 修炼+{int(float(method['practice_bonus']) * 100)}%"
        )
    await methods_cmd.finish("\n".join(lines))


@inventory_cmd.handle()
async def handle_inventory(event: MessageEvent) -> None:
    player = await get_player_status(event.get_user_id())
    if player is None:
        await inventory_cmd.finish("你还未入道，发送“入道”开始。")
    items = await list_inventory(event.get_user_id())
    if not items:
        await inventory_cmd.finish("你的背包空空如也。")

    lines = ["当前背包:"]
    for item in items:
        lines.append(f"- {item['name']} x{item['quantity']} [{item['item_type']}/{item['rarity']}]")
    await inventory_cmd.finish("\n".join(lines))


@adventure_cmd.handle()
async def handle_adventure(event: MessageEvent) -> None:
    try:
        result = await adventure(event.get_user_id())
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await adventure_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "not_enough_stamina":
            await adventure_cmd.finish("体力不足，先歇息片刻或等后续回复体力机制。")
        raise

    reward_line = (
        f"灵石 {result.spirit_stones_delta:+}，修为 {result.cultivation_delta:+}，体力 {result.stamina_delta}。"
    )
    if result.reward_item_name:
        reward_line += f" 额外获得 {result.reward_item_name}。"
    await adventure_cmd.finish(f"{result.message}\nroll={result.roll_value}\n{reward_line}")


@breakthrough_cmd.handle()
async def handle_breakthrough(event: MessageEvent) -> None:
    try:
        result = await breakthrough(event.get_user_id())
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await breakthrough_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "not_enough_cultivation":
            await breakthrough_cmd.finish("修为尚不足以冲关。")
        if reason == "realm_maxed":
            await breakthrough_cmd.finish("当前已至此世尽头，后续以转世为主。")
        raise

    if result.soul_mark_gained:
        await breakthrough_cmd.finish(f"roll={result.roll_value}，你在天地压迫中凝成了一枚轮回印记。")
    if result.success:
        await breakthrough_cmd.finish(
            f"roll={result.roll_value}，突破成功！ {result.current_realm} -> {result.next_realm}"
        )
    await breakthrough_cmd.finish(
        f"roll={result.roll_value}，突破失败，修为变动 {result.cultivation_delta}。"
    )


@meditate_cmd.handle()
async def handle_meditation(event: MessageEvent, args: Message = CommandArg()) -> None:
    minutes_text = args.extract_plain_text().strip()
    minutes = None
    if minutes_text:
        if not minutes_text.isdigit():
            await meditate_cmd.finish("请输入闭关分钟数，例如：闭关 30")
        minutes = int(minutes_text)
    try:
        result = await start_meditation(event.get_user_id(), minutes)
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await meditate_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "already_meditating":
            await meditate_cmd.finish("你已在闭关中，发送“出关”查看。")
        if reason == "invalid_meditation_minutes":
            await meditate_cmd.finish("闭关时长需在 10 到 180 分钟之间。")
        raise

    await meditate_cmd.finish(
        f"你已开始闭关 {result.minutes} 分钟，预计至 {result.until} 出关，可获修为 {result.reward}。"
    )


@leave_meditation_cmd.handle()
async def handle_leave_meditation(event: MessageEvent) -> None:
    try:
        result = await end_meditation(event.get_user_id())
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await leave_meditation_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "not_meditating":
            await leave_meditation_cmd.finish("你当前并未闭关。")
        raise

    if result.still_waiting:
        await leave_meditation_cmd.finish(
            f"闭关尚未结束，还需约 {result.remaining_minutes} 分钟，可得修为 {result.reward}。"
        )
    await leave_meditation_cmd.finish(
        f"你已出关，本次闭关 {result.minutes} 分钟，获得修为 {result.reward}。"
    )


@market_list_cmd.handle()
async def handle_market_list() -> None:
    listings = await list_market()
    if not listings:
        await market_list_cmd.finish("坊市目前空空如也。")

    lines = ["坊市在售:"]
    for listing in listings:
        lines.append(
            f"#{listing['id']} {listing['item_name']} x{listing['quantity']} "
            f"- {listing['unit_price']} 灵石/件 卖家:{listing['seller_name']}"
        )
    await market_list_cmd.finish("\n".join(lines))


@market_create_cmd.handle()
async def handle_market_create(event: MessageEvent, args: Message = CommandArg()) -> None:
    parts = args.extract_plain_text().strip().split()
    if len(parts) != 3:
        await market_create_cmd.finish("格式：坊市上架 物品名 单价 数量")
    item_name, unit_price_text, quantity_text = parts
    if not unit_price_text.isdigit() or not quantity_text.isdigit():
        await market_create_cmd.finish("单价和数量都需要是正整数。")
    try:
        result = await create_market_listing(
            event.get_user_id(),
            item_name,
            int(unit_price_text),
            int(quantity_text),
        )
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await market_create_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "item_not_found":
            await market_create_cmd.finish("背包里找不到这个物品。")
        if reason == "item_not_tradable":
            await market_create_cmd.finish("该物品不可交易。")
        if reason == "not_enough_items":
            await market_create_cmd.finish("背包数量不足。")
        if reason == "invalid_listing_params":
            await market_create_cmd.finish("单价和数量都需要大于 0。")
        raise

    await market_create_cmd.finish(
        f"上架成功：#{result.listing_id} {result.item_name} x{result.quantity}，单价 {result.unit_price} 灵石。"
    )


@market_buy_cmd.handle()
async def handle_market_buy(event: MessageEvent, args: Message = CommandArg()) -> None:
    listing_text = args.extract_plain_text().strip()
    if not listing_text.isdigit():
        await market_buy_cmd.finish("格式：坊市购买 编号")
    try:
        result = await buy_market_listing(event.get_user_id(), int(listing_text))
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await market_buy_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "listing_not_found":
            await market_buy_cmd.finish("未找到该上架编号。")
        if reason == "listing_unavailable":
            await market_buy_cmd.finish("该上架已被买走或下架。")
        if reason == "cannot_buy_own_listing":
            await market_buy_cmd.finish("不能购买自己上架的物品。")
        if reason == "not_enough_spirit_stones":
            await market_buy_cmd.finish("灵石不足。")
        raise

    await market_buy_cmd.finish(
        f"购买成功：{result.item_name} x{result.quantity}，共支付 {result.total_price} 灵石。"
        f"坊市抽取手续费 {result.fee}，卖家 {result.seller_name} 已收款。"
    )


@ranking_cmd.handle()
async def handle_ranking() -> None:
    rankings = await get_rankings()
    if not rankings:
        await ranking_cmd.finish("当前尚无排行数据。")

    lines = ["修仙排行榜:"]
    for index, row in enumerate(rankings, start=1):
        lines.append(
            f"{index}. {row['nickname']} | {row['realm']} | 修为 {row['cultivation']} | 灵石 {row['spirit_stones']}"
        )
    await ranking_cmd.finish("\n".join(lines))
