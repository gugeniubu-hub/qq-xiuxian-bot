from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime

from xianbot.config import get_settings
from xianbot.domain import Player, Realm, RootType
from xianbot.progression import calculate_rebirth_outcome, can_rebirth
from xianbot.repository import GameRepository


ROOT_ROLL_TABLE: tuple[tuple[int, RootType], ...] = (
    (45, RootType.MORTAL),
    (75, RootType.YELLOW),
    (92, RootType.MYSTIC),
    (99, RootType.EARTH),
    (100, RootType.HEAVEN),
)


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


def get_repository() -> GameRepository:
    return GameRepository(get_settings().database_url)


def roll_root_type() -> RootType:
    roll = random.randint(1, 100)
    for threshold, root_type in ROOT_ROLL_TABLE:
        if roll <= threshold:
            return root_type
    return RootType.MORTAL


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
    )
    await repo.create_player(player)
    return player, True


async def get_player_status(user_id: str) -> Player | None:
    return await get_repository().get_player(user_id)


async def list_sects_for_player(user_id: str) -> list[dict[str, object]]:
    repo = get_repository()
    player = await repo.get_player(user_id)
    rebirth_count = 0 if player is None else player.rebirth_count
    return await repo.list_accessible_sects(rebirth_count)


async def sign_in(user_id: str) -> SignInResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise ValueError("player_not_found")

    sign_date = datetime.now().date().isoformat()
    if await repo.get_today_signin(user_id, sign_date):
        raise ValueError("already_signed")

    settings = get_settings()
    base_reward = random.randint(120, 180)
    cultivation_gain = random.randint(40, 80)
    fortune_roll = random.randint(1, 100)

    current_pool = await repo.get_fortune_pool_amount()
    releasable = int(current_pool * settings.daily_pool_release_rate)
    pool_reward = 0
    if releasable > 0:
        bonus_factor = 1.0
        if fortune_roll >= 96:
            bonus_factor = 0.60
        elif fortune_roll >= 80:
            bonus_factor = 0.35
        elif fortune_roll >= 50:
            bonus_factor = 0.20
        else:
            bonus_factor = 0.10
        pool_reward = max(1, int(releasable * bonus_factor))
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


async def rebirth(user_id: str) -> RebirthResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise ValueError("player_not_found")
    if not can_rebirth(player):
        raise ValueError("rebirth_locked")

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
