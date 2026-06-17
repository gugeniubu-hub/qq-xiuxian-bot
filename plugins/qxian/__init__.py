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
    contemplate_method,
    consume_item,
    craft_elixir,
    create_market_listing,
    create_player_if_missing,
    duel,
    encounter,
    end_meditation,
    get_player_methods,
    get_player_status,
    get_rankings,
    get_today_world_state,
    join_sect,
    list_inventory,
    list_market,
    list_sects_for_player,
    rebirth,
    set_primary_method,
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
primary_method_cmd = on_command("主修功法", aliases={"切换主修"})
inventory_cmd = on_command("背包")
adventure_cmd = on_command("历练")
encounter_cmd = on_command("奇遇")
breakthrough_cmd = on_command("突破")
meditate_cmd = on_command("闭关")
leave_meditation_cmd = on_command("出关")
consume_cmd = on_command("服用")
insight_cmd = on_command("参悟")
alchemy_cmd = on_command("炼丹")
duel_cmd = on_command("斗法", aliases={"pk", "PK"})
market_list_cmd = on_command("坊市")
market_create_cmd = on_command("坊市上架")
market_buy_cmd = on_command("坊市购买", aliases={"购买"})
ranking_cmd = on_command("排行", aliases={"排行榜"})
world_cmd = on_command("天象", aliases={"今日天象", "世界状态"})


@driver.on_startup
async def startup() -> None:
    initialize_database(settings.database_url)


def _meditation_usage() -> str:
    return "闭关 [分钟] [吐纳|凝练|参玄|冲关]，例如：闭关 45 参玄"


def _duel_target_text(args: Message) -> str:
    plain = args.extract_plain_text().strip()
    if plain:
        return plain
    for seg in args:
        if seg.type == "at":
            qq = seg.data.get("qq")
            if qq:
                return str(qq)
    return ""


@help_cmd.handle()
async def handle_help(event: MessageEvent) -> None:
    await help_cmd.finish(HELP_TEXT.format(user_id=event.get_user_id()))


@world_cmd.handle()
async def handle_world_state() -> None:
    result = await get_today_world_state()
    await world_cmd.finish(
        f"今日天象：{result.title}\n{result.description}\n"
        f"历练修正 {result.adventure_bonus:+} | 奇遇修正 {result.encounter_bonus:+} | "
        f"闭关修正 {int(result.meditation_bonus * 100):+}%"
    )


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
            f"道友入道成功，灵根为{player.root_type.value}，主属性 {player.root_affinity.value}，纯度 {player.root_purity}。"
            f"性情 {player.root_temperament.value}，特质 {player.root_trait.value}。"
            f"初始灵石 {player.spirit_stones}，福缘 {player.fortune}。发送“我的状态”查看详情。"
        )
    await enter_path_cmd.finish(
        f"道友早已踏上仙途，当前境界 {player.realm.value}，灵根 {player.root_type.value}·{player.root_affinity.value}。"
    )


@status_cmd.handle()
async def handle_status(event: MessageEvent) -> None:
    user_id = event.get_user_id()
    player = await get_player_status(user_id)
    if player is None:
        await status_cmd.finish("你还未入道，发送“入道”开始。")
    methods = await get_player_methods(user_id)
    primary_method = next((method for method in methods if bool(method.get("equipped"))), None)
    method_summary = "未定主修" if primary_method is None else (
        f"{primary_method['name']} [{primary_method['mastery_title']}]"
    )
    await status_cmd.finish(
        "\n".join(
            [
                f"道号: {player.nickname}",
                f"灵根: {player.root_type.value}·{player.root_affinity.value}系 | 纯度 {player.root_purity}",
                f"根性: {player.root_temperament.value} | 特质: {player.root_trait.value}",
                f"境界: {player.realm.value}",
                f"修为: {player.cultivation}",
                f"悟性: {player.comprehension} | 道悟: {player.insight} | 冲关底蕴: {player.breakthrough_ready}",
                f"主修: {method_summary}",
                f"灵石: {player.spirit_stones} | 福缘: {player.fortune} | 体力: {player.stamina}",
                f"寿元: {player.age}/{player.lifespan}",
                f"轮回: {player.rebirth_count} 转 | 前尘点: {player.legacy_points} | 轮回印记: {player.soul_marks}",
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
        f"[{result.world_title}] 签到完成，获得灵石 {result.base_reward}，福缘池分红 {result.pool_reward}，"
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
        f"道友已转世重修，前尘点 +{result.legacy_points_gained}。"
        f"新灵根保底为 {result.new_root_floor}，本次根骨：{result.root_brief}。"
        f"解锁内容: {unlocks}。"
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
        mark = " [主修]" if bool(method.get("equipped")) else ""
        lines.append(
            f"- {method['name']}{mark} | {method['grade']} {method['method_type']} {method['affinity']}系"
        )
        lines.append(
            f"  境界需求 {method['realm_requirement']} | 修炼+{int(float(method['practice_total']) * 100)}%"
            f" | 冲关+{int(method['breakthrough_total'])}% | 悟道+{int(float(method['insight_total']) * 100)}%"
        )
        lines.append(
            f"  熟练 {method['mastery']} [{method['mastery_title']}] | 风格 {method['style']}"
        )
    await methods_cmd.finish("\n".join(lines))


@primary_method_cmd.handle()
async def handle_primary_method(event: MessageEvent, args: Message = CommandArg()) -> None:
    method_name = args.extract_plain_text().strip()
    if not method_name:
        await primary_method_cmd.finish("格式：主修功法 功法名")
    try:
        result = await set_primary_method(event.get_user_id(), method_name)
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await primary_method_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "method_not_found":
            await primary_method_cmd.finish("未找到这门功法，先发送“我的功法”查看。")
        raise
    await primary_method_cmd.finish(
        f"已将《{result.method_name}》设为主修。"
        f"当前层次 {result.mastery_title}，修炼+{result.practice_bonus_percent}% ，"
        f"冲关+{result.breakthrough_bonus_percent}% ，悟道+{result.insight_bonus_percent}% 。"
    )


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
    if result.insight_delta:
        reward_line += f" 道悟 {result.insight_delta:+}。"
    if result.reward_item_name:
        reward_line += f" 额外获得 {result.reward_item_name}。"
    lines = [f"[{result.world_title}] {result.message}", f"roll={result.roll_value}", reward_line]
    if result.mastery_method_name and result.mastery_gain:
        lines.append(f"《{result.mastery_method_name}》熟练 +{result.mastery_gain}。")
    if result.lifespan_notice:
        lines.append(result.lifespan_notice)
    await adventure_cmd.finish("\n".join(lines))


@encounter_cmd.handle()
async def handle_encounter(event: MessageEvent) -> None:
    try:
        result = await encounter(event.get_user_id())
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await encounter_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "not_enough_stamina":
            await encounter_cmd.finish("体力不足，暂时承不起这一桩奇遇。")
        raise

    lines = [
        f"[{result.world_title}] {result.message}",
        f"roll={result.roll_value}",
        f"灵石 {result.spirit_stones_delta:+}，修为 {result.cultivation_delta:+}，体力 {result.stamina_delta}，福缘 {result.fortune_delta:+}。",
    ]
    if result.insight_delta:
        lines.append(f"道悟 {result.insight_delta:+}。")
    if result.reward_item_name:
        lines.append(f"额外获得 {result.reward_item_name}。")
    if result.mastery_method_name and result.mastery_gain:
        lines.append(f"《{result.mastery_method_name}》熟练 +{result.mastery_gain}。")
    if result.lifespan_notice:
        lines.append(result.lifespan_notice)
    await encounter_cmd.finish("\n".join(lines))


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
        if reason == "not_enough_preparation":
            await breakthrough_cmd.finish("冲关底蕴不足。先用“闭关 冲关”或“闭关 凝练”积蓄，再来突破。")
        if reason == "realm_maxed":
            await breakthrough_cmd.finish("当前已至此世尽头，后续以转世为主。")
        raise

    lines = [f"[{result.world_title}] roll={result.roll_value} / 成功率约 {result.chance_percent}%"]
    if result.preparation_cost:
        lines.append(f"本次消耗冲关底蕴 {result.preparation_cost}。")
    if result.soul_mark_gained:
        lines.append("你在天地压迫中凝成了一枚轮回印记。")
    elif result.success:
        lines.append(f"突破成功！ {result.current_realm} -> {result.next_realm}")
    else:
        lines.append(f"突破失败，修为变动 {result.cultivation_delta}。")
    if result.unlocked_methods:
        lines.append(f"宗门传承感应而至：{'、'.join(result.unlocked_methods)}。")
    if result.lifespan_notice:
        lines.append(result.lifespan_notice)
    await breakthrough_cmd.finish("\n".join(lines))


@meditate_cmd.handle()
async def handle_meditation(event: MessageEvent, args: Message = CommandArg()) -> None:
    parts = args.extract_plain_text().strip().split()
    minutes = None
    mode = None
    if parts:
        if parts[0].isdigit():
            minutes = int(parts[0])
            if len(parts) >= 2:
                mode = parts[1]
        else:
            mode = parts[0]
            if len(parts) >= 2 and parts[1].isdigit():
                minutes = int(parts[1])
            elif len(parts) >= 2:
                await meditate_cmd.finish(_meditation_usage())
    try:
        result = await start_meditation(event.get_user_id(), minutes, mode)
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await meditate_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "already_meditating":
            await meditate_cmd.finish("你已在闭关中，发送“出关”查看。")
        if reason == "invalid_meditation_minutes":
            await meditate_cmd.finish("闭关时长需在 10 到 180 分钟之间。")
        if reason == "invalid_meditation_mode":
            await meditate_cmd.finish(_meditation_usage())
        raise

    lines = [
        f"[{result.world_title}] 你已开始{result.mode_name}闭关 {result.minutes} 分钟，预计至 {result.until} 出关。",
        f"本次可获修为 {result.reward}，道悟 {result.insight_reward}，冲关底蕴 {result.breakthrough_reward}。",
    ]
    if result.method_name:
        lines.append(f"主修功法：《{result.method_name}》。")
    await meditate_cmd.finish("\n".join(lines))


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
            f"{result.mode_name or '闭关'}尚未结束，还需约 {result.remaining_minutes} 分钟，可得修为 {result.reward}。"
        )
    lines = [f"你已出关，本次{result.mode_name or '闭关'} {result.minutes} 分钟，获得修为 {result.reward}。"]
    if result.insight_gain:
        lines.append(f"道悟 +{result.insight_gain}。")
    if result.breakthrough_ready_gain:
        lines.append(f"冲关底蕴 +{result.breakthrough_ready_gain}。")
    if result.method_name and result.mastery_gain:
        lines.append(f"《{result.method_name}》熟练 +{result.mastery_gain}。")
    if result.lifespan_notice:
        lines.append(result.lifespan_notice)
    await leave_meditation_cmd.finish("\n".join(lines))


@consume_cmd.handle()
async def handle_consume(event: MessageEvent, args: Message = CommandArg()) -> None:
    item_name = args.extract_plain_text().strip()
    if not item_name:
        await consume_cmd.finish("格式：服用 物品名")
    try:
        result = await consume_item(event.get_user_id(), item_name)
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await consume_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "item_not_found":
            await consume_cmd.finish("未找到该物品。")
        if reason == "item_not_consumable":
            await consume_cmd.finish("这东西不能直接服用。")
        if reason == "rebirth_required":
            await consume_cmd.finish("洗髓丹药力太烈，至少一转之后再服用。")
        if reason == "not_enough_items":
            await consume_cmd.finish("背包数量不足。")
        raise

    lines = [f"{result.message} 你服用了 {result.item_name}。"]
    if result.cultivation_delta:
        lines.append(f"修为 {result.cultivation_delta:+}")
    if result.stamina_delta:
        lines.append(f"体力 {result.stamina_delta:+}")
    if result.lifespan_delta:
        lines.append(f"寿元上限 {result.lifespan_delta:+}")
    await consume_cmd.finish("，".join(lines) + "。")


@alchemy_cmd.handle()
async def handle_alchemy(event: MessageEvent, args: Message = CommandArg()) -> None:
    recipe_name = args.extract_plain_text().strip()
    if not recipe_name:
        await alchemy_cmd.finish("格式：炼丹 丹药名，例如：炼丹 凝元丹")
    try:
        result = await craft_elixir(event.get_user_id(), recipe_name)
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await alchemy_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "recipe_not_found":
            await alchemy_cmd.finish("未找到这张丹方。当前建议尝试：聚气丹 / 回灵散 / 凝元丹 / 悟道丹 / 洗髓丹")
        if reason == "recipe_locked":
            await alchemy_cmd.finish("这张丹方需要转世后才能稳住药力。")
        if reason == "not_enough_materials":
            await alchemy_cmd.finish("灵材不足，先去历练、奇遇或坊市再备料。")
        raise

    lines = [
        f"[{result.world_title}] {result.message}",
        f"目标丹药《{result.item_name}》 | roll={result.roll_value} / 成丹率约 {result.chance_percent}%",
    ]
    if result.success:
        lines.append(f"获得 {result.item_name} x{result.quantity}。")
        if result.insight_gain:
            lines.append(f"炼丹反哺心神，道悟 +{result.insight_gain}。")
    elif result.byproduct_name:
        lines.append(f"获得副产物 {result.byproduct_name} x{result.byproduct_quantity}。")
    await alchemy_cmd.finish("\n".join(lines))


@insight_cmd.handle()
async def handle_insight(event: MessageEvent, args: Message = CommandArg()) -> None:
    method_name = args.extract_plain_text().strip() or None
    try:
        result = await contemplate_method(event.get_user_id(), method_name)
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await insight_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "method_not_found":
            await insight_cmd.finish("未找到可参悟的功法，请先加入宗门或确认功法名。")
        if reason == "not_enough_fragments":
            await insight_cmd.finish("缺少吐纳残篇，先去历练或奇遇搜集。")
        raise

    lines = [
        f"[{result.world_title}] 你借残篇参悟《{result.method_name}》，熟练 +{result.mastery_gain}，"
        f"当前熟练 {result.new_mastery}，修为 +{result.cultivation_gain}。"
    ]
    if result.insight_gain:
        lines.append(f"道悟 +{result.insight_gain}。")
    if result.breakthrough_ready_gain:
        lines.append(f"冲关底蕴 +{result.breakthrough_ready_gain}。")
    await insight_cmd.finish("\n".join(lines))


@duel_cmd.handle()
async def handle_duel(event: MessageEvent, args: Message = CommandArg()) -> None:
    target = _duel_target_text(args)
    if not target:
        await duel_cmd.finish("格式：斗法 @目标 或 斗法 QQ号")
    try:
        result = await duel(event.get_user_id(), target)
    except GameError as exc:
        reason = str(exc)
        if reason == "player_not_found":
            await duel_cmd.finish("你还未入道，发送“入道”开始。")
        if reason == "target_not_found":
            await duel_cmd.finish("未找到斗法目标，对方需要先入道。")
        if reason == "cannot_duel_self":
            await duel_cmd.finish("对着自己出手，容易走火入魔。")
        if reason == "not_enough_stamina":
            await duel_cmd.finish("有一方体力不足，今日这场斗法暂时开不了。")
        raise

    await duel_cmd.finish(
        "\n".join(
            [
                f"[{result.world_title}] {result.message}",
                f"{result.attacker_name}: roll={result.attacker_roll} | 总势 {result.attacker_total}",
                f"{result.defender_name}: roll={result.defender_roll} | 总势 {result.defender_total}",
                f"胜者 {result.winner_name}，获灵石 +{result.winner_spirit_stones_gain}，修为 +{result.winner_cultivation_gain}，道悟 +{result.winner_insight_gain}。",
                f"败者 {result.loser_name}，修为 {result.loser_cultivation_loss}，双方体力各消耗 {abs(result.attacker_stamina_delta)}。",
            ]
        )
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
