from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from xianbot.config import get_settings
from xianbot.domain import Player, Realm, RootType
from xianbot.progression import calculate_rebirth_outcome, can_rebirth
from xianbot.repository import GameRepository
from xianbot.rules import (
    breakthrough_base_chance,
    next_realm,
    realm_requirement,
    root_adventure_bonus,
    root_breakthrough_bonus,
    root_training_multiplier,
)


ROOT_ROLL_TABLE: tuple[tuple[int, RootType], ...] = (
    (45, RootType.MORTAL),
    (75, RootType.YELLOW),
    (92, RootType.MYSTIC),
    (99, RootType.EARTH),
    (100, RootType.HEAVEN),
)

WORLD_STATE_POOL: tuple[dict[str, Any], ...] = (
    {
        "title": "流火天",
        "description": "天地火气炽盛，外出历练更容易碰上激烈机缘，也更耗寿元。",
        "adventure_bonus": 12,
        "meditation_bonus": -0.08,
        "encounter_bonus": 6,
        "fortune_bonus": 1,
        "lifespan_bonus": 1,
    },
    {
        "title": "甘霖夜",
        "description": "夜雨如酥，闭关吐纳最为安稳，寿元流逝也稍缓。",
        "adventure_bonus": -4,
        "meditation_bonus": 0.12,
        "encounter_bonus": 0,
        "fortune_bonus": 1,
        "lifespan_bonus": -1,
    },
    {
        "title": "星辉潮",
        "description": "星辉垂落，奇遇与悟道都更容易触发，适合参悟功法。",
        "adventure_bonus": 4,
        "meditation_bonus": 0.05,
        "encounter_bonus": 10,
        "fortune_bonus": 2,
        "lifespan_bonus": 0,
    },
    {
        "title": "朔风劫",
        "description": "寒煞横空，外出与突破都更凶险，失败的代价更沉重。",
        "adventure_bonus": -8,
        "meditation_bonus": -0.04,
        "encounter_bonus": -6,
        "fortune_bonus": -1,
        "lifespan_bonus": 1,
    },
    {
        "title": "虚市回响",
        "description": "轮回余韵浮现，转世者更容易撞见隐秘机缘与稀有货物。",
        "adventure_bonus": 6,
        "meditation_bonus": 0.02,
        "encounter_bonus": 12,
        "fortune_bonus": 3,
        "lifespan_bonus": 0,
    },
)


class GameError(ValueError):
    pass


@dataclass(slots=True)
class SignInResult:
    base_reward: int
    pool_reward: int
    fortune_roll: int
    total_spirit_stones: int
    total_cultivation: int
    world_title: str


@dataclass(slots=True)
class RebirthResult:
    legacy_points_gained: int
    unlocked_features: list[str]
    new_root_floor: str


@dataclass(slots=True)
class JoinSectResult:
    sect_name: str
    method_name: str | None


@dataclass(slots=True)
class WorldStateResult:
    title: str
    description: str
    adventure_bonus: int
    meditation_bonus: float
    encounter_bonus: int
    fortune_bonus: int
    lifespan_bonus: int


@dataclass(slots=True)
class AdventureResult:
    roll_value: int
    message: str
    spirit_stones_delta: int
    cultivation_delta: int
    stamina_delta: int
    reward_item_name: str | None
    world_title: str
    mastery_method_name: str | None = None
    mastery_gain: int = 0
    lifespan_notice: str | None = None


@dataclass(slots=True)
class EncounterResult:
    roll_value: int
    message: str
    spirit_stones_delta: int
    cultivation_delta: int
    stamina_delta: int
    fortune_delta: int
    reward_item_name: str | None
    world_title: str
    mastery_method_name: str | None = None
    mastery_gain: int = 0
    lifespan_notice: str | None = None


@dataclass(slots=True)
class BreakthroughResult:
    roll_value: int
    success: bool
    current_realm: str
    next_realm: str | None
    cultivation_delta: int
    chance_percent: int
    world_title: str
    soul_mark_gained: bool = False
    lifespan_notice: str | None = None


@dataclass(slots=True)
class MeditationResult:
    minutes: int
    reward: int
    until: str
    world_title: str
    method_name: str | None


@dataclass(slots=True)
class MeditationClaimResult:
    reward: int
    minutes: int
    still_waiting: bool
    method_name: str | None = None
    mastery_gain: int = 0
    lifespan_notice: str | None = None
    remaining_minutes: int = 0


@dataclass(slots=True)
class MarketCreateResult:
    listing_id: int
    item_name: str
    quantity: int
    unit_price: int


@dataclass(slots=True)
class MarketBuyResult:
    listing_id: int
    item_name: str
    quantity: int
    total_price: int
    fee: int
    seller_name: str


@dataclass(slots=True)
class ConsumeItemResult:
    item_name: str
    message: str
    cultivation_delta: int = 0
    stamina_delta: int = 0
    lifespan_delta: int = 0


@dataclass(slots=True)
class MethodInsightResult:
    method_name: str
    mastery_gain: int
    new_mastery: int
    cultivation_gain: int
    world_title: str


def get_repository() -> GameRepository:
    return GameRepository(get_settings().database_url)


def roll_root_type() -> RootType:
    roll = random.randint(1, 100)
    for threshold, root_type in ROOT_ROLL_TABLE:
        if roll <= threshold:
            return root_type
    return RootType.MORTAL


def _now() -> datetime:
    return datetime.now()


def _today() -> date:
    return _now().date()


def _generate_world_state(state_date: str) -> dict[str, Any]:
    rng = random.Random(f"qxian-world-{state_date}")
    return dict(rng.choice(WORLD_STATE_POOL))


async def _get_today_world_state() -> WorldStateResult:
    repo = get_repository()
    state_date = _today().isoformat()
    state = await repo.get_world_state(state_date)
    if state is None:
        state = _generate_world_state(state_date)
        await repo.save_world_state(
            state_date=state_date,
            title=str(state["title"]),
            description=str(state["description"]),
            adventure_bonus=int(state["adventure_bonus"]),
            meditation_bonus=float(state["meditation_bonus"]),
            encounter_bonus=int(state["encounter_bonus"]),
            fortune_bonus=int(state["fortune_bonus"]),
            lifespan_bonus=int(state["lifespan_bonus"]),
        )
    return WorldStateResult(
        title=str(state["title"]),
        description=str(state["description"]),
        adventure_bonus=int(state["adventure_bonus"]),
        meditation_bonus=float(state["meditation_bonus"]),
        encounter_bonus=int(state["encounter_bonus"]),
        fortune_bonus=int(state["fortune_bonus"]),
        lifespan_bonus=int(state["lifespan_bonus"]),
    )


def _mastery_practice_bonus(mastery: int) -> float:
    return min(0.12, (mastery // 25) * 0.02)


def _mastery_breakthrough_bonus(mastery: int) -> int:
    return min(12, (mastery // 25) * 2)


def _primary_method(methods: list[dict[str, object]]) -> dict[str, object] | None:
    if not methods:
        return None
    return max(
        methods,
        key=lambda method: (
            int(method.get("mastery", 0)),
            float(method["practice_bonus"]),
            float(method["breakthrough_bonus"]),
        ),
    )


def _method_breakthrough_bonus(methods: list[dict[str, object]]) -> int:
    if not methods:
        return 0
    return max(
        int(float(method["breakthrough_bonus"]) * 100)
        + _mastery_breakthrough_bonus(int(method.get("mastery", 0)))
        for method in methods
    )


def _method_practice_bonus(methods: list[dict[str, object]]) -> float:
    if not methods:
        return 0.0
    return max(
        float(method["practice_bonus"]) + _mastery_practice_bonus(int(method.get("mastery", 0)))
        for method in methods
    )


def _lifespan_reward_multiplier(player: Player) -> float:
    ratio = player.age / max(player.lifespan, 1)
    if ratio >= 0.95:
        return 0.72
    if ratio >= 0.85:
        return 0.82
    if ratio >= 0.75:
        return 0.92
    return 1.0


def _lifespan_breakthrough_penalty(player: Player) -> int:
    ratio = player.age / max(player.lifespan, 1)
    if ratio >= 0.95:
        return 12
    if ratio >= 0.85:
        return 8
    if ratio >= 0.75:
        return 4
    return 0


def _lifespan_notice(before: Player, after: Player) -> str | None:
    if after.age > before.age:
        return f"岁月流转，你的寿元来到 {after.age}/{after.lifespan}。"
    remaining = after.lifespan - after.age
    if remaining <= 5:
        return f"你已感到寿元枯竭，仅余 {remaining} 载。"
    if remaining <= 12:
        return f"你隐约察觉寿元逼近极限，当前 {after.age}/{after.lifespan}。"
    return None


async def _apply_method_mastery(
    repo: GameRepository,
    user_id: str,
    method: dict[str, object] | None,
    amount: int,
) -> tuple[str | None, int]:
    if method is None or amount <= 0:
        return None, 0
    await repo.add_method_mastery(user_id, str(method["id"]), amount)
    return str(method["name"]), amount


async def _apply_lifespan_progress(
    repo: GameRepository,
    player: Player,
    progress_delta: int,
    lifespan_delta: int = 0,
) -> tuple[Player, str | None]:
    if progress_delta or lifespan_delta:
        await repo.apply_lifespan_progress(
            player.user_id,
            progress_delta=max(0, progress_delta),
            lifespan_delta=lifespan_delta,
        )
    updated = await repo.get_player(player.user_id)
    assert updated is not None
    return updated, _lifespan_notice(player, updated)


def _meditation_age_progress(minutes: int, world_state: WorldStateResult) -> int:
    settings = get_settings()
    base_steps = max(0, (minutes + 59) // 60)
    return base_steps * settings.lifespan_progress_per_60_meditation_minutes + world_state.lifespan_bonus


def _encounter_cost() -> int:
    return max(10, get_settings().adventure_stamina_cost - 5)


async def create_player_if_missing(user_id: str, nickname: str) -> tuple[Player, bool]:
    repo = get_repository()
    existing = await repo.get_player(user_id)
    if existing is not None:
        return existing, False

    player = Player(
        user_id=user_id,
        nickname=nickname,
        root_type=roll_root_type(),
        spirit_stones=300,
        fortune=random.randint(5, 15),
        comprehension=random.randint(8, 14),
        stamina=100,
    )
    await repo.create_player(player)
    await repo.add_inventory_item(user_id, "qigather", 2)
    await repo.add_inventory_item(user_id, "spirit-herb", 3)
    return await repo.get_player(user_id) or player, True


async def get_player_status(user_id: str) -> Player | None:
    return await get_repository().get_player(user_id)


async def get_today_world_state() -> WorldStateResult:
    return await _get_today_world_state()


async def list_sects_for_player(user_id: str) -> list[dict[str, object]]:
    repo = get_repository()
    player = await repo.get_player(user_id)
    rebirth_count = 0 if player is None else player.rebirth_count
    return await repo.list_accessible_sects(rebirth_count)


async def get_player_methods(user_id: str) -> list[dict[str, object]]:
    return await get_repository().get_player_methods(user_id)


async def list_inventory(user_id: str) -> list[dict[str, object]]:
    return await get_repository().list_inventory(user_id)


async def sign_in(user_id: str) -> SignInResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")

    sign_date = _today().isoformat()
    if await repo.get_today_signin(user_id, sign_date):
        raise GameError("already_signed")

    world_state = await _get_today_world_state()
    settings = get_settings()
    base_reward = random.randint(
        settings.sign_in_base_min + player.fortune,
        settings.sign_in_base_max + player.fortune,
    )
    cultivation_gain = random.randint(
        settings.sign_in_cultivation_min + player.comprehension,
        settings.sign_in_cultivation_max + player.comprehension,
    )
    fortune_roll = min(100, random.randint(1, 100) + world_state.fortune_bonus)

    current_pool = await repo.get_fortune_pool_amount()
    releasable = int(current_pool * settings.daily_pool_release_rate)
    pool_reward = 0
    if releasable > 0:
        if fortune_roll >= 96:
            pool_reward = max(1, int(releasable * 0.60))
        elif fortune_roll >= 80:
            pool_reward = max(1, int(releasable * 0.35))
        elif fortune_roll >= 50:
            pool_reward = max(1, int(releasable * 0.20))
        else:
            pool_reward = max(1, int(releasable * 0.10))
        pool_reward = min(pool_reward, current_pool)
        await repo.adjust_fortune_pool(-pool_reward)

    await repo.update_player_stats(
        user_id,
        spirit_stones_delta=base_reward + pool_reward,
        cultivation_delta=cultivation_gain,
        stamina_delta=12,
    )
    await repo.record_signin(
        user_id=user_id,
        sign_date=sign_date,
        base_reward=base_reward,
        pool_reward=pool_reward,
        fortune_roll=fortune_roll,
    )

    updated = await repo.get_player(user_id)
    assert updated is not None
    return SignInResult(
        base_reward=base_reward,
        pool_reward=pool_reward,
        fortune_roll=fortune_roll,
        total_spirit_stones=updated.spirit_stones,
        total_cultivation=updated.cultivation,
        world_title=world_state.title,
    )


async def join_sect(user_id: str, sect_name: str) -> JoinSectResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")
    if player.sect_id is not None:
        raise GameError("already_in_sect")

    sect = await repo.get_sect_by_name(sect_name)
    if sect is None:
        raise GameError("sect_not_found")
    if player.rebirth_count < int(sect["required_rebirth_count"]):
        raise GameError("sect_locked")

    await repo.set_player_sect(user_id, str(sect["id"]))
    methods = await repo.get_sect_methods(str(sect["id"]), player.rebirth_count)
    granted_method_name: str | None = None
    if methods:
        starter = methods[0]
        if await repo.grant_player_method(user_id, str(starter["id"])):
            granted_method_name = str(starter["name"])

    return JoinSectResult(sect_name=str(sect["name"]), method_name=granted_method_name)


async def adventure(user_id: str) -> AdventureResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")

    settings = get_settings()
    if player.stamina < settings.adventure_stamina_cost:
        raise GameError("not_enough_stamina")

    methods = await repo.get_player_methods(user_id)
    world_state = await _get_today_world_state()
    primary_method = _primary_method(methods)
    roll_value = (
        random.randint(1, 100)
        + root_adventure_bonus(player.root_type)
        + player.fortune // 12
        + world_state.adventure_bonus // 3
        + min(8, player.rebirth_count * 2)
    )

    cultivation_gain = 0
    spirit_stones_gain = 0
    stamina_delta = -settings.adventure_stamina_cost
    item_id: str | None = None
    item_name: str | None = None
    message: str

    if roll_value <= 18:
        cultivation_gain = -max(18, int(player.cultivation * 0.04))
        spirit_stones_gain = random.randint(8, 24)
        message = "历练途中误入凶地，虽侥幸脱身，但心神受损。"
    elif roll_value <= 54:
        cultivation_gain = random.randint(90, 150)
        spirit_stones_gain = random.randint(40, 90)
        message = "你在山野间搜寻机缘，收获了一批灵石与修为。"
    elif roll_value <= 88:
        cultivation_gain = random.randint(150, 240)
        spirit_stones_gain = random.randint(80, 150)
        message = "你在历练中斩获颇丰，灵气流转颇为顺畅。"
        if random.random() < 0.35:
            item_id = "spirit-herb"
    elif roll_value <= 103:
        cultivation_gain = random.randint(200, 340)
        spirit_stones_gain = random.randint(130, 240)
        message = "你撞上了一次大机缘，洞府残痕中留有前人遗泽。"
        luck_draw = random.random()
        if luck_draw < 0.18:
            item_id = "rebirth-mark"
        elif luck_draw < 0.52:
            item_id = "method-fragment"
        elif luck_draw < 0.76:
            item_id = "longevity-fruit"
        else:
            item_id = "qigather"
    else:
        cultivation_gain = random.randint(260, 430)
        spirit_stones_gain = random.randint(180, 300)
        if player.rebirth_count >= 1:
            message = "你闯入了一处轮回者才可感知的遗迹夹层，古老气息扑面而来。"
        else:
            message = "你仰见星芒坠落，顺着灵机追索而去，竟得一桩超常机缘。"
        item_id = "method-fragment" if player.rebirth_count < 2 else random.choice(
            ["method-fragment", "longevity-fruit", "rebirth-mark"]
        )

    reward_multiplier = _lifespan_reward_multiplier(player)
    if cultivation_gain > 0:
        cultivation_gain = int(cultivation_gain * reward_multiplier)
    if spirit_stones_gain > 0:
        spirit_stones_gain = int(spirit_stones_gain * reward_multiplier)

    if cultivation_gain > 0:
        cultivation_gain = int(
            cultivation_gain
            * (1 + root_training_multiplier(player.root_type) + _method_practice_bonus(methods))
        )

    if item_id is not None:
        item = await repo.get_item_by_id(item_id)
        if item is not None:
            item_name = str(item["name"])
            await repo.add_inventory_item(user_id, item_id, 1)

    mastery_gain = settings.method_mastery_adventure_gain + (1 if roll_value >= 88 else 0)
    mastery_method_name, applied_mastery = await _apply_method_mastery(
        repo,
        user_id,
        primary_method,
        mastery_gain if cultivation_gain > 0 else 0,
    )

    await repo.update_player_stats(
        user_id,
        spirit_stones_delta=spirit_stones_gain,
        cultivation_delta=cultivation_gain,
        stamina_delta=stamina_delta,
    )
    await repo.record_adventure(
        user_id,
        action_type="adventure",
        roll_value=roll_value,
        outcome=message,
        reward_spirit_stones=spirit_stones_gain,
        reward_cultivation=cultivation_gain,
        reward_item_id=item_id,
    )
    _, lifespan_notice = await _apply_lifespan_progress(
        repo,
        player,
        settings.lifespan_progress_per_adventure + world_state.lifespan_bonus,
    )

    return AdventureResult(
        roll_value=roll_value,
        message=message,
        spirit_stones_delta=spirit_stones_gain,
        cultivation_delta=cultivation_gain,
        stamina_delta=stamina_delta,
        reward_item_name=item_name,
        world_title=world_state.title,
        mastery_method_name=mastery_method_name,
        mastery_gain=applied_mastery,
        lifespan_notice=lifespan_notice,
    )


async def encounter(user_id: str) -> EncounterResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")

    stamina_cost = _encounter_cost()
    if player.stamina < stamina_cost:
        raise GameError("not_enough_stamina")

    settings = get_settings()
    methods = await repo.get_player_methods(user_id)
    primary_method = _primary_method(methods)
    world_state = await _get_today_world_state()
    roll_value = (
        random.randint(1, 100)
        + player.fortune // 8
        + world_state.encounter_bonus
        + min(12, player.rebirth_count * 3)
    )

    cultivation_gain = 0
    spirit_stones_gain = 0
    fortune_delta = 0
    stamina_delta = -stamina_cost
    item_id: str | None = None
    item_name: str | None = None
    message: str

    if roll_value <= 15:
        cultivation_gain = -max(20, int(max(player.cultivation, 120) * 0.05))
        spirit_stones_gain = random.randint(0, 20)
        message = "你误触残阵，幻象缠身，险些在奇遇中折损根基。"
    elif roll_value <= 48:
        cultivation_gain = random.randint(70, 130)
        spirit_stones_gain = random.randint(25, 55)
        fortune_delta = 1
        message = "你在偏僻石壁后发现一缕灵脉余温，虽不惊艳，却也受益匪浅。"
    elif roll_value <= 82:
        cultivation_gain = random.randint(110, 190)
        spirit_stones_gain = random.randint(60, 110)
        fortune_delta = 1
        item_id = random.choice(["qigather", "spirit-herb"])
        message = "你撞见了一场恰到好处的机缘，灵材与感悟一并入手。"
    elif roll_value <= 100:
        cultivation_gain = random.randint(170, 280)
        spirit_stones_gain = random.randint(90, 170)
        fortune_delta = 2
        if player.rebirth_count >= 1:
            item_id = random.choice(["method-fragment", "longevity-fruit"])
            message = "你在轮回残响中看见古修遗刻，心神一震，收获远超寻常。"
        else:
            item_id = random.choice(["method-fragment", "qigather"])
            message = "你偶得一段前人传音，字句不多，却足够你在仙途上再进一步。"
    else:
        cultivation_gain = random.randint(240, 380)
        spirit_stones_gain = random.randint(150, 260)
        fortune_delta = 3
        if player.rebirth_count >= 2:
            item_id = random.choice(["rebirth-mark", "longevity-fruit", "method-fragment"])
            message = "虚市裂缝在你面前一闪而过，你从中换得了一件极罕见的东西。"
        else:
            item_id = random.choice(["longevity-fruit", "method-fragment"])
            message = "天穹星辉忽然倾泻，你在片刻失神后，竟捧回了一桩大机缘。"

    reward_multiplier = _lifespan_reward_multiplier(player)
    if cultivation_gain > 0:
        cultivation_gain = int(cultivation_gain * reward_multiplier)
        cultivation_gain = int(
            cultivation_gain
            * (1 + root_training_multiplier(player.root_type) + _method_practice_bonus(methods))
        )
    if spirit_stones_gain > 0:
        spirit_stones_gain = int(spirit_stones_gain * reward_multiplier)

    if item_id is not None:
        item = await repo.get_item_by_id(item_id)
        if item is not None:
            item_name = str(item["name"])
            await repo.add_inventory_item(user_id, item_id, 1)

    mastery_gain = settings.method_mastery_encounter_gain + (2 if roll_value >= 100 else 0)
    mastery_method_name, applied_mastery = await _apply_method_mastery(
        repo,
        user_id,
        primary_method,
        mastery_gain if cultivation_gain > 0 else 0,
    )

    await repo.update_player_stats(
        user_id,
        spirit_stones_delta=spirit_stones_gain,
        cultivation_delta=cultivation_gain,
        fortune_delta=fortune_delta,
        stamina_delta=stamina_delta,
    )
    await repo.record_adventure(
        user_id,
        action_type="encounter",
        roll_value=roll_value,
        outcome=message,
        reward_spirit_stones=spirit_stones_gain,
        reward_cultivation=cultivation_gain,
        reward_item_id=item_id,
    )
    _, lifespan_notice = await _apply_lifespan_progress(
        repo,
        player,
        settings.lifespan_progress_per_encounter + world_state.lifespan_bonus,
    )

    return EncounterResult(
        roll_value=roll_value,
        message=message,
        spirit_stones_delta=spirit_stones_gain,
        cultivation_delta=cultivation_gain,
        stamina_delta=stamina_delta,
        fortune_delta=fortune_delta,
        reward_item_name=item_name,
        world_title=world_state.title,
        mastery_method_name=mastery_method_name,
        mastery_gain=applied_mastery,
        lifespan_notice=lifespan_notice,
    )


async def start_meditation(user_id: str, minutes: int | None = None) -> MeditationResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")
    if player.meditation_until is not None:
        raise GameError("already_meditating")

    settings = get_settings()
    if minutes is None:
        minutes = settings.meditation_default_minutes
    if minutes < settings.meditation_min_minutes or minutes > settings.meditation_max_minutes:
        raise GameError("invalid_meditation_minutes")

    methods = await repo.get_player_methods(user_id)
    primary_method = _primary_method(methods)
    world_state = await _get_today_world_state()
    practice_bonus = _method_practice_bonus(methods)
    reward = int(
        minutes
        * (6 + player.comprehension / 4)
        * (
            1
            + root_training_multiplier(player.root_type)
            + practice_bonus
            + world_state.meditation_bonus
        )
        * _lifespan_reward_multiplier(player)
    )
    started_at = _now()
    until = started_at + timedelta(minutes=minutes)
    method_id = str(primary_method["id"]) if primary_method else None
    await repo.set_player_meditation(
        user_id,
        started_at=started_at.isoformat(),
        until=until.isoformat(),
        minutes=minutes,
        reward=max(10, reward),
        method_id=method_id,
    )
    return MeditationResult(
        minutes=minutes,
        reward=max(10, reward),
        until=until.strftime("%H:%M"),
        world_title=world_state.title,
        method_name=None if primary_method is None else str(primary_method["name"]),
    )


async def end_meditation(user_id: str) -> MeditationClaimResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")
    if player.meditation_until is None or player.meditation_started_at is None:
        raise GameError("not_meditating")

    until = datetime.fromisoformat(player.meditation_until)
    now = _now()
    if now < until:
        remaining = int((until - now).total_seconds() // 60) + 1
        method_name = None
        if player.meditation_method_id:
            methods = await repo.get_player_methods(user_id)
            primary_method = next(
                (method for method in methods if str(method["id"]) == player.meditation_method_id),
                None,
            )
            method_name = None if primary_method is None else str(primary_method["name"])
        return MeditationClaimResult(
            reward=player.meditation_reward,
            minutes=player.meditation_minutes,
            still_waiting=True,
            method_name=method_name,
            remaining_minutes=max(1, remaining),
        )

    methods = await repo.get_player_methods(user_id)
    method = next(
        (method for method in methods if str(method["id"]) == player.meditation_method_id),
        None,
    )
    mastery_gain = get_settings().method_mastery_meditation_gain + max(
        0,
        player.meditation_minutes // 60 - 1,
    )
    method_name, applied_mastery = await _apply_method_mastery(repo, user_id, method, mastery_gain)
    await repo.update_player_stats(user_id, cultivation_delta=player.meditation_reward)
    await repo.clear_player_meditation(user_id)

    world_state = await _get_today_world_state()
    refreshed_player = await repo.get_player(user_id)
    assert refreshed_player is not None
    _, lifespan_notice = await _apply_lifespan_progress(
        repo,
        refreshed_player,
        _meditation_age_progress(player.meditation_minutes, world_state),
    )

    return MeditationClaimResult(
        reward=player.meditation_reward,
        minutes=player.meditation_minutes,
        still_waiting=False,
        method_name=method_name,
        mastery_gain=applied_mastery,
        lifespan_notice=lifespan_notice,
    )


async def breakthrough(user_id: str) -> BreakthroughResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")

    methods = await repo.get_player_methods(user_id)
    world_state = await _get_today_world_state()
    target = next_realm(player.realm)

    if target is None:
        if player.realm != Realm.SPIRIT_4:
            raise GameError("realm_maxed")
        if player.cultivation < realm_requirement(player.realm):
            raise GameError("not_enough_cultivation")

        chance = 65 + player.fortune // 8 + world_state.fortune_bonus - _lifespan_breakthrough_penalty(player)
        chance = max(18, min(chance, 98))
        roll_value = random.randint(1, 100)
        soul_mark_gained = roll_value <= chance

        if soul_mark_gained:
            await repo.update_player_stats(user_id, soul_marks_delta=1)
            _, lifespan_notice = await _apply_lifespan_progress(
                repo,
                player,
                1 + max(0, world_state.lifespan_bonus),
            )
            return BreakthroughResult(
                roll_value=roll_value,
                success=True,
                current_realm=player.realm.value,
                next_realm=None,
                cultivation_delta=0,
                chance_percent=chance,
                world_title=world_state.title,
                soul_mark_gained=True,
                lifespan_notice=lifespan_notice,
            )

        penalty = -max(50, int(player.cultivation * get_settings().breakthrough_fail_penalty_rate))
        await repo.update_player_stats(user_id, cultivation_delta=penalty)
        _, lifespan_notice = await _apply_lifespan_progress(
            repo,
            player,
            1 + max(0, world_state.lifespan_bonus),
        )
        return BreakthroughResult(
            roll_value=roll_value,
            success=False,
            current_realm=player.realm.value,
            next_realm=None,
            cultivation_delta=penalty,
            chance_percent=chance,
            world_title=world_state.title,
            soul_mark_gained=False,
            lifespan_notice=lifespan_notice,
        )

    required = realm_requirement(target)
    if player.cultivation < required:
        raise GameError("not_enough_cultivation")

    chance = breakthrough_base_chance(player.realm)
    chance += root_breakthrough_bonus(player.root_type)
    chance += min(12, player.fortune // 10)
    chance += min(10, player.comprehension // 3)
    chance += world_state.fortune_bonus
    chance += _method_breakthrough_bonus(methods)
    chance -= _lifespan_breakthrough_penalty(player)
    chance = max(18, min(chance, 98))

    roll_value = random.randint(1, 100)
    if roll_value <= chance:
        await repo.update_player_stats(user_id, realm=target)
        _, lifespan_notice = await _apply_lifespan_progress(
            repo,
            player,
            1 + max(0, world_state.lifespan_bonus),
        )
        return BreakthroughResult(
            roll_value=roll_value,
            success=True,
            current_realm=player.realm.value,
            next_realm=target.value,
            cultivation_delta=0,
            chance_percent=chance,
            world_title=world_state.title,
            lifespan_notice=lifespan_notice,
        )

    penalty = -max(30, int(required * get_settings().breakthrough_fail_penalty_rate))
    await repo.update_player_stats(user_id, cultivation_delta=penalty)
    _, lifespan_notice = await _apply_lifespan_progress(
        repo,
        player,
        1 + max(0, world_state.lifespan_bonus),
    )
    return BreakthroughResult(
        roll_value=roll_value,
        success=False,
        current_realm=player.realm.value,
        next_realm=None,
        cultivation_delta=penalty,
        chance_percent=chance,
        world_title=world_state.title,
        lifespan_notice=lifespan_notice,
    )


async def consume_item(user_id: str, item_name: str) -> ConsumeItemResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")

    item = await repo.get_item_by_name(item_name)
    if item is None:
        raise GameError("item_not_found")
    if int(item["consumable"]) != 1:
        raise GameError("item_not_consumable")

    item_id = str(item["id"])
    if item_id not in {"qigather", "restore-powder", "longevity-fruit"}:
        raise GameError("item_not_consumable")
    if not await repo.remove_inventory_item(user_id, item_id, 1):
        raise GameError("not_enough_items")

    if item_id == "qigather":
        cultivation_delta = random.randint(120, 190) + player.comprehension * 3
        await repo.update_player_stats(user_id, cultivation_delta=cultivation_delta)
        return ConsumeItemResult(
            item_name=str(item["name"]),
            message="丹药入腹，灵气迅速化开。",
            cultivation_delta=cultivation_delta,
        )
    if item_id == "restore-powder":
        stamina_delta = random.randint(30, 45)
        await repo.update_player_stats(user_id, stamina_delta=stamina_delta)
        return ConsumeItemResult(
            item_name=str(item["name"]),
            message="药力散开，你的气海重新变得充盈。",
            stamina_delta=stamina_delta,
        )
    if item_id == "longevity-fruit":
        lifespan_delta = random.randint(2, 4)
        await repo.update_player_stats(user_id, lifespan_delta=lifespan_delta)
        return ConsumeItemResult(
            item_name=str(item["name"]),
            message="灵果甘凉入体，你感到寿元中的枯意稍稍退去。",
            lifespan_delta=lifespan_delta,
        )
    raise GameError("item_not_consumable")


async def contemplate_method(user_id: str, method_name: str | None = None) -> MethodInsightResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")

    methods = await repo.get_player_methods(user_id)
    if not methods:
        raise GameError("method_not_found")

    if not await repo.remove_inventory_item(user_id, "method-fragment", 1):
        raise GameError("not_enough_fragments")

    if method_name:
        method = await repo.get_player_method_by_name(user_id, method_name)
    else:
        method = _primary_method(methods)
    if method is None:
        await repo.add_inventory_item(user_id, "method-fragment", 1)
        raise GameError("method_not_found")

    world_state = await _get_today_world_state()
    mastery_gain = (
        random.randint(10, 18)
        + player.comprehension // 5
        + player.rebirth_count * 2
        + max(0, world_state.encounter_bonus // 6)
    )
    cultivation_gain = 60 + mastery_gain * 4

    await repo.add_method_mastery(user_id, str(method["id"]), mastery_gain)
    await repo.update_player_stats(user_id, cultivation_delta=cultivation_gain, stamina_delta=-8)
    refreshed = await repo.get_player_method_by_name(user_id, str(method["name"]))
    assert refreshed is not None
    return MethodInsightResult(
        method_name=str(method["name"]),
        mastery_gain=mastery_gain,
        new_mastery=int(refreshed["mastery"]),
        cultivation_gain=cultivation_gain,
        world_title=world_state.title,
    )


async def list_market() -> list[dict[str, object]]:
    return await get_repository().get_active_market_listings()


async def create_market_listing(
    user_id: str,
    item_name: str,
    unit_price: int,
    quantity: int,
) -> MarketCreateResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")
    if unit_price <= 0 or quantity <= 0:
        raise GameError("invalid_listing_params")

    item = await repo.get_item_by_name(item_name)
    if item is None:
        raise GameError("item_not_found")
    if int(item["tradable"]) != 1:
        raise GameError("item_not_tradable")

    removed = await repo.remove_inventory_item(user_id, str(item["id"]), quantity)
    if not removed:
        raise GameError("not_enough_items")

    listing_id = await repo.create_market_listing(user_id, str(item["id"]), quantity, unit_price)
    return MarketCreateResult(
        listing_id=listing_id,
        item_name=str(item["name"]),
        quantity=quantity,
        unit_price=unit_price,
    )


async def buy_market_listing(user_id: str, listing_id: int) -> MarketBuyResult:
    repo = get_repository()
    buyer = await repo.get_player(user_id)
    if buyer is None:
        raise GameError("player_not_found")

    listing = await repo.get_market_listing(listing_id)
    if listing is None:
        raise GameError("listing_not_found")
    if str(listing["status"]) != "active":
        raise GameError("listing_unavailable")
    if str(listing["seller_user_id"]) == user_id:
        raise GameError("cannot_buy_own_listing")

    total_price = int(listing["quantity"]) * int(listing["unit_price"])
    if buyer.spirit_stones < total_price:
        raise GameError("not_enough_spirit_stones")

    fee = max(1, int(total_price * get_settings().market_fee_rate))
    seller_income = total_price - fee

    await repo.update_player_stats(user_id, spirit_stones_delta=-total_price)
    await repo.update_player_stats(str(listing["seller_user_id"]), spirit_stones_delta=seller_income)
    await repo.adjust_fortune_pool(fee)
    await repo.add_inventory_item(user_id, str(listing["item_id"]), int(listing["quantity"]))
    await repo.mark_market_listing_sold(listing_id, user_id)

    return MarketBuyResult(
        listing_id=listing_id,
        item_name=str(listing["item_name"]),
        quantity=int(listing["quantity"]),
        total_price=total_price,
        fee=fee,
        seller_name=str(listing["seller_name"]),
    )


async def get_rankings() -> list[dict[str, object]]:
    return await get_repository().list_top_players()


async def rebirth(user_id: str) -> RebirthResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")
    if not can_rebirth(player):
        raise GameError("rebirth_locked")

    outcome = calculate_rebirth_outcome(player)
    await repo.update_player_stats(
        user_id,
        cultivation_delta=-player.cultivation,
        legacy_points_delta=outcome.legacy_points_gained,
        rebirth_count_delta=1,
        soul_marks_delta=-1,
        realm=Realm.QI_1,
        root_type=outcome.next_root_floor,
    )
    await repo.reset_player_for_rebirth(user_id)

    await repo.record_rebirth(
        user_id=user_id,
        rebirth_count=player.rebirth_count + 1,
        previous_realm=player.realm,
        legacy_points_gained=outcome.legacy_points_gained,
        soul_marks_consumed=1,
    )
    await repo.save_legacy_unlocks(
        user_id,
        [unlock.value for unlock in outcome.unlocked_features],
    )
    return RebirthResult(
        legacy_points_gained=outcome.legacy_points_gained,
        unlocked_features=[unlock.value for unlock in outcome.unlocked_features],
        new_root_floor=outcome.next_root_floor.value,
    )
