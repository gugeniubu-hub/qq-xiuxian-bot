from __future__ import annotations

from xianbot.domain import Realm, RootType


REALM_ORDER: list[Realm] = [
    Realm.QI_1,
    Realm.QI_2,
    Realm.QI_3,
    Realm.QI_4,
    Realm.FOUNDATION_1,
    Realm.FOUNDATION_2,
    Realm.FOUNDATION_3,
    Realm.FOUNDATION_4,
    Realm.CORE_1,
    Realm.CORE_2,
    Realm.CORE_3,
    Realm.CORE_4,
    Realm.NASCENT_1,
    Realm.NASCENT_2,
    Realm.NASCENT_3,
    Realm.NASCENT_4,
    Realm.SPIRIT_1,
    Realm.SPIRIT_2,
    Realm.SPIRIT_3,
    Realm.SPIRIT_4,
]

REALM_REQUIREMENTS: dict[Realm, int] = {
    Realm.QI_1: 0,
    Realm.QI_2: 120,
    Realm.QI_3: 220,
    Realm.QI_4: 360,
    Realm.FOUNDATION_1: 560,
    Realm.FOUNDATION_2: 820,
    Realm.FOUNDATION_3: 1120,
    Realm.FOUNDATION_4: 1470,
    Realm.CORE_1: 1880,
    Realm.CORE_2: 2360,
    Realm.CORE_3: 2900,
    Realm.CORE_4: 3520,
    Realm.NASCENT_1: 4220,
    Realm.NASCENT_2: 5000,
    Realm.NASCENT_3: 5860,
    Realm.NASCENT_4: 6800,
    Realm.SPIRIT_1: 7820,
    Realm.SPIRIT_2: 8920,
    Realm.SPIRIT_3: 10120,
    Realm.SPIRIT_4: 11420,
}

REALM_BREAKTHROUGH_BASE: dict[Realm, int] = {
    Realm.QI_1: 94,
    Realm.QI_2: 90,
    Realm.QI_3: 86,
    Realm.QI_4: 82,
    Realm.FOUNDATION_1: 80,
    Realm.FOUNDATION_2: 76,
    Realm.FOUNDATION_3: 72,
    Realm.FOUNDATION_4: 68,
    Realm.CORE_1: 64,
    Realm.CORE_2: 60,
    Realm.CORE_3: 56,
    Realm.CORE_4: 52,
    Realm.NASCENT_1: 48,
    Realm.NASCENT_2: 45,
    Realm.NASCENT_3: 42,
    Realm.NASCENT_4: 39,
    Realm.SPIRIT_1: 36,
    Realm.SPIRIT_2: 33,
    Realm.SPIRIT_3: 30,
    Realm.SPIRIT_4: 28,
}

ROOT_TRAINING_BONUS: dict[RootType, float] = {
    RootType.MORTAL: 0.00,
    RootType.YELLOW: 0.05,
    RootType.MYSTIC: 0.10,
    RootType.EARTH: 0.16,
    RootType.HEAVEN: 0.24,
}

ROOT_BREAKTHROUGH_BONUS: dict[RootType, int] = {
    RootType.MORTAL: 0,
    RootType.YELLOW: 2,
    RootType.MYSTIC: 5,
    RootType.EARTH: 8,
    RootType.HEAVEN: 12,
}

ROOT_ADVENTURE_BONUS: dict[RootType, int] = {
    RootType.MORTAL: 0,
    RootType.YELLOW: 1,
    RootType.MYSTIC: 2,
    RootType.EARTH: 4,
    RootType.HEAVEN: 6,
}


def realm_index(realm: Realm) -> int:
    return REALM_ORDER.index(realm)


def next_realm(realm: Realm) -> Realm | None:
    index = realm_index(realm)
    if index + 1 >= len(REALM_ORDER):
        return None
    return REALM_ORDER[index + 1]


def realm_requirement(realm: Realm) -> int:
    return REALM_REQUIREMENTS[realm]


def breakthrough_base_chance(realm: Realm) -> int:
    return REALM_BREAKTHROUGH_BASE[realm]


def root_training_multiplier(root_type: RootType) -> float:
    return ROOT_TRAINING_BONUS[root_type]


def root_breakthrough_bonus(root_type: RootType) -> int:
    return ROOT_BREAKTHROUGH_BONUS[root_type]


def root_adventure_bonus(root_type: RootType) -> int:
    return ROOT_ADVENTURE_BONUS[root_type]
