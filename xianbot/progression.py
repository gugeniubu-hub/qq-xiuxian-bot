from __future__ import annotations

from dataclasses import dataclass

from xianbot.domain import Player, RebirthUnlock, Realm, RootType


REBIRTH_REALM_REQUIREMENT = Realm.SPIRIT_4
REBIRTH_REALM_CAPS: tuple[Realm, ...] = (
    Realm.FOUNDATION_4,
    Realm.CORE_4,
    Realm.NASCENT_4,
    Realm.SPIRIT_4,
)


@dataclass(slots=True)
class RebirthOutcome:
    next_root_floor: RootType
    next_realm_cap: Realm
    legacy_points_gained: int
    unlocked_features: list[RebirthUnlock]


def can_rebirth(player: Player) -> bool:
    return player.realm == realm_cap_for_rebirth_count(player.rebirth_count) and player.soul_marks >= 1


def realm_cap_for_rebirth_count(rebirth_count: int) -> Realm:
    index = max(0, min(rebirth_count, len(REBIRTH_REALM_CAPS) - 1))
    return REBIRTH_REALM_CAPS[index]


def unlocks_for_rebirth_count(rebirth_count: int) -> list[RebirthUnlock]:
    unlocks: list[RebirthUnlock] = []
    if rebirth_count >= 1:
        unlocks.extend(
            [
                RebirthUnlock.HIDDEN_SECTS,
                RebirthUnlock.ANCIENT_METHODS,
            ]
        )
    if rebirth_count >= 2:
        unlocks.extend(
            [
                RebirthUnlock.DESTINY_SYSTEM,
                RebirthUnlock.VOID_MARKET,
            ]
        )
    if rebirth_count >= 3:
        unlocks.append(RebirthUnlock.HIGHER_ROOT_FLOOR)
    return unlocks


def calculate_rebirth_outcome(player: Player) -> RebirthOutcome:
    next_count = player.rebirth_count + 1
    if next_count >= 5:
        next_root_floor = RootType.HEAVEN
    elif next_count >= 4:
        next_root_floor = RootType.EARTH
    elif next_count >= 3:
        next_root_floor = RootType.MYSTIC
    elif next_count >= 2:
        next_root_floor = RootType.YELLOW
    else:
        next_root_floor = RootType.MORTAL
    return RebirthOutcome(
        next_root_floor=next_root_floor,
        next_realm_cap=realm_cap_for_rebirth_count(next_count),
        legacy_points_gained=1 + max(0, next_count - 1),
        unlocked_features=unlocks_for_rebirth_count(next_count),
    )
