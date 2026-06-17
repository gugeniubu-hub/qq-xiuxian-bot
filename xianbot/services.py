from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

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


class GameError(ValueError):
    pass


@dataclass(slots=True)
class SignInResult:
    base_reward: int
    pool_reward: int
    fortune_roll: int
    total_spirit_stones: int
    total_cultivation: int


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
class AdventureResult:
    roll_value: int
    message: str
    spirit_stones_delta: int
    cultivation_delta: int
    stamina_delta: int
    reward_item_name: str | None


@dataclass(slots=True)
class BreakthroughResult:
    roll_value: int
    success: bool
    current_realm: str
    next_realm: str | None
    cultivation_delta: int
    soul_mark_gained: bool = False


@dataclass(slots=True)
class MeditationResult:
    minutes: int
    reward: int
    until: str


@dataclass(slots=True)
class MeditationClaimResult:
    reward: int
    minutes: int
    still_waiting: bool
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


def _method_breakthrough_bonus(methods: list[dict[str, object]]) -> int:
    if not methods:
        return 0
    return int(max(float(method["breakthrough_bonus"]) for method in methods) * 100)


def _method_practice_bonus(methods: list[dict[str, object]]) -> float:
    if not methods:
        return 0.0
    return max(float(method["practice_bonus"]) for method in methods)


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

    sign_date = _now().date().isoformat()
    if await repo.get_today_signin(user_id, sign_date):
        raise GameError("already_signed")

    settings = get_settings()
    base_reward = random.randint(
        settings.sign_in_base_min + player.fortune,
        settings.sign_in_base_max + player.fortune,
    )
    cultivation_gain = random.randint(
        settings.sign_in_cultivation_min + player.comprehension,
        settings.sign_in_cultivation_max + player.comprehension,
    )
    fortune_roll = random.randint(1, 100)

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
    roll_value = random.randint(1, 100) + root_adventure_bonus(player.root_type) + player.fortune // 12
    cultivation_gain = 0
    spirit_stones_gain = 0
    stamina_delta = -settings.adventure_stamina_cost
    item_id: str | None = None
    item_name: str | None = None
    message: str

    if roll_value <= 18:
        cultivation_gain = -max(10, int(player.cultivation * 0.03))
        spirit_stones_gain = random.randint(8, 24)
        message = "历练途中误入凶地，虽侥幸脱身，但心神受损。"
    elif roll_value <= 58:
        cultivation_gain = random.randint(80, 140)
        spirit_stones_gain = random.randint(35, 80)
        message = "你在山野间搜寻机缘，收获了一批灵石与修为。"
    elif roll_value <= 88:
        cultivation_gain = random.randint(130, 220)
        spirit_stones_gain = random.randint(70, 130)
        message = "你在历练中斩获颇丰，灵气流转颇为顺畅。"
        if random.random() < 0.35:
            item_id = "spirit-herb"
    else:
        cultivation_gain = random.randint(180, 320)
        spirit_stones_gain = random.randint(120, 220)
        message = "你撞上了一次大机缘，洞府残痕中留有前人遗泽。"
        luck_draw = random.random()
        if luck_draw < 0.15:
            item_id = "rebirth-mark"
        elif luck_draw < 0.45:
            item_id = "method-fragment"
        else:
            item_id = "qigather"

    if methods:
        cultivation_gain = int(cultivation_gain * (1 + _method_practice_bonus(methods)))
    cultivation_gain = int(cultivation_gain * (1 + root_training_multiplier(player.root_type)))

    if item_id is not None:
        item = await repo.get_item_by_id(item_id)
        if item is not None:
            item_name = str(item["name"])
            await repo.add_inventory_item(user_id, item_id, 1)

    await repo.update_player_stats(
        user_id,
        spirit_stones_delta=spirit_stones_gain,
        cultivation_delta=cultivation_gain,
        stamina_delta=stamina_delta,
    )
    await repo.record_adventure(
        user_id,
        roll_value=roll_value,
        outcome=message,
        reward_spirit_stones=spirit_stones_gain,
        reward_cultivation=cultivation_gain,
        reward_item_id=item_id,
    )

    return AdventureResult(
        roll_value=roll_value,
        message=message,
        spirit_stones_delta=spirit_stones_gain,
        cultivation_delta=cultivation_gain,
        stamina_delta=stamina_delta,
        reward_item_name=item_name,
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
    practice_bonus = _method_practice_bonus(methods)
    reward = int(
        minutes
        * (6 + player.comprehension / 4)
        * (1 + root_training_multiplier(player.root_type) + practice_bonus)
    )
    started_at = _now()
    until = started_at + timedelta(minutes=minutes)
    method_id = str(methods[0]["id"]) if methods else None
    await repo.set_player_meditation(
        user_id,
        started_at=started_at.isoformat(),
        until=until.isoformat(),
        minutes=minutes,
        reward=reward,
        method_id=method_id,
    )
    return MeditationResult(minutes=minutes, reward=reward, until=until.strftime("%H:%M"))


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
        return MeditationClaimResult(
            reward=player.meditation_reward,
            minutes=player.meditation_minutes,
            still_waiting=True,
            remaining_minutes=max(1, remaining),
        )

    await repo.update_player_stats(user_id, cultivation_delta=player.meditation_reward)
    await repo.clear_player_meditation(user_id)
    return MeditationClaimResult(
        reward=player.meditation_reward,
        minutes=player.meditation_minutes,
        still_waiting=False,
    )


async def breakthrough(user_id: str) -> BreakthroughResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")

    target = next_realm(player.realm)
    if target is None:
        if player.realm == Realm.SPIRIT_4:
            if player.cultivation < realm_requirement(player.realm):
                raise GameError("not_enough_cultivation")
            roll_value = random.randint(1, 100)
            soul_mark_gained = roll_value + player.fortune // 8 >= 65
            if soul_mark_gained:
                await repo.update_player_stats(user_id, soul_marks_delta=1)
                return BreakthroughResult(
                    roll_value=roll_value,
                    success=True,
                    current_realm=player.realm.value,
                    next_realm=None,
                    cultivation_delta=0,
                    soul_mark_gained=True,
                )
            penalty = -max(50, int(player.cultivation * get_settings().breakthrough_fail_penalty_rate))
            await repo.update_player_stats(user_id, cultivation_delta=penalty)
            return BreakthroughResult(
                roll_value=roll_value,
                success=False,
                current_realm=player.realm.value,
                next_realm=None,
                cultivation_delta=penalty,
                soul_mark_gained=False,
            )
        raise GameError("realm_maxed")

    required = realm_requirement(target)
    if player.cultivation < required:
        raise GameError("not_enough_cultivation")

    methods = await repo.get_player_methods(user_id)
    chance = breakthrough_base_chance(player.realm)
    chance += root_breakthrough_bonus(player.root_type)
    chance += min(12, player.fortune // 10)
    chance += min(10, player.comprehension // 3)
    chance += _method_breakthrough_bonus(methods)
    chance = min(chance, 98)

    roll_value = random.randint(1, 100)
    if roll_value <= chance:
        await repo.update_player_stats(user_id, realm=target)
        return BreakthroughResult(
            roll_value=roll_value,
            success=True,
            current_realm=player.realm.value,
            next_realm=target.value,
            cultivation_delta=0,
        )

    penalty = -max(30, int(required * get_settings().breakthrough_fail_penalty_rate))
    await repo.update_player_stats(user_id, cultivation_delta=penalty)
    return BreakthroughResult(
        roll_value=roll_value,
        success=False,
        current_realm=player.realm.value,
        next_realm=None,
        cultivation_delta=penalty,
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
