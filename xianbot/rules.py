from __future__ import annotations

from xianbot.domain import (
    Affinity,
    MeditationMode,
    MethodGrade,
    RootTemperament,
    RootTrait,
    Realm,
    RootType,
)


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

ROOT_PURITY_MULTIPLIER: dict[RootType, tuple[int, int]] = {
    RootType.MORTAL: (32, 58),
    RootType.YELLOW: (48, 68),
    RootType.MYSTIC: (60, 80),
    RootType.EARTH: (72, 90),
    RootType.HEAVEN: (82, 98),
}

TEMPERAMENT_TRAINING_BONUS: dict[RootTemperament, float] = {
    RootTemperament.BALANCED: 0.03,
    RootTemperament.FIERCE: 0.01,
    RootTemperament.TRANQUIL: 0.05,
    RootTemperament.NIMBLE: 0.02,
    RootTemperament.ENLIGHTENED: 0.04,
}

TEMPERAMENT_BREAKTHROUGH_BONUS: dict[RootTemperament, int] = {
    RootTemperament.BALANCED: 2,
    RootTemperament.FIERCE: 5,
    RootTemperament.TRANQUIL: 1,
    RootTemperament.NIMBLE: 3,
    RootTemperament.ENLIGHTENED: 4,
}

TEMPERAMENT_INSIGHT_BONUS: dict[RootTemperament, float] = {
    RootTemperament.BALANCED: 0.02,
    RootTemperament.FIERCE: 0.00,
    RootTemperament.TRANQUIL: 0.03,
    RootTemperament.NIMBLE: 0.01,
    RootTemperament.ENLIGHTENED: 0.05,
}

TRAIT_TRAINING_BONUS: dict[RootTrait, float] = {
    RootTrait.GATHERING: 0.05,
    RootTrait.FLOWING: 0.02,
    RootTrait.INSIGHTFUL: 0.01,
    RootTrait.EVERGREEN: 0.00,
    RootTrait.WANDERING: 0.01,
    RootTrait.EMBER: 0.03,
}

TRAIT_BREAKTHROUGH_BONUS: dict[RootTrait, int] = {
    RootTrait.GATHERING: 1,
    RootTrait.FLOWING: 4,
    RootTrait.INSIGHTFUL: 2,
    RootTrait.EVERGREEN: 1,
    RootTrait.WANDERING: 2,
    RootTrait.EMBER: 5,
}

TRAIT_INSIGHT_BONUS: dict[RootTrait, float] = {
    RootTrait.GATHERING: 0.01,
    RootTrait.FLOWING: 0.00,
    RootTrait.INSIGHTFUL: 0.06,
    RootTrait.EVERGREEN: 0.01,
    RootTrait.WANDERING: 0.02,
    RootTrait.EMBER: 0.03,
}

TRAIT_LIFESPAN_BONUS: dict[RootTrait, int] = {
    RootTrait.GATHERING: 0,
    RootTrait.FLOWING: 0,
    RootTrait.INSIGHTFUL: 0,
    RootTrait.EVERGREEN: 10,
    RootTrait.WANDERING: 0,
    RootTrait.EMBER: 4,
}

METHOD_GRADE_PRACTICE_BONUS: dict[MethodGrade, float] = {
    MethodGrade.COMMON: 0.00,
    MethodGrade.YELLOW: 0.03,
    MethodGrade.MYSTIC: 0.06,
    MethodGrade.EARTH: 0.09,
    MethodGrade.HEAVEN: 0.12,
    MethodGrade.ANCIENT: 0.15,
}

METHOD_GRADE_BREAKTHROUGH_BONUS: dict[MethodGrade, int] = {
    MethodGrade.COMMON: 0,
    MethodGrade.YELLOW: 2,
    MethodGrade.MYSTIC: 4,
    MethodGrade.EARTH: 7,
    MethodGrade.HEAVEN: 10,
    MethodGrade.ANCIENT: 12,
}

MEDITATION_MODE_REWARD_MULTIPLIER: dict[MeditationMode, float] = {
    MeditationMode.BREATH: 1.00,
    MeditationMode.CONDENSE: 0.88,
    MeditationMode.INSIGHT: 0.72,
    MeditationMode.BREAKTHROUGH: 0.62,
}

MEDITATION_MODE_INSIGHT_BONUS: dict[MeditationMode, float] = {
    MeditationMode.BREATH: 0.00,
    MeditationMode.CONDENSE: 0.03,
    MeditationMode.INSIGHT: 0.12,
    MeditationMode.BREAKTHROUGH: 0.06,
}

MEDITATION_MODE_BREAKTHROUGH_BONUS: dict[MeditationMode, int] = {
    MeditationMode.BREATH: 0,
    MeditationMode.CONDENSE: 6,
    MeditationMode.INSIGHT: 3,
    MeditationMode.BREAKTHROUGH: 14,
}

AFFINITY_CYCLE: tuple[Affinity, ...] = (
    Affinity.METAL,
    Affinity.WATER,
    Affinity.WOOD,
    Affinity.FIRE,
    Affinity.EARTH,
)


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


def root_purity_range(root_type: RootType) -> tuple[int, int]:
    return ROOT_PURITY_MULTIPLIER[root_type]


def purity_training_bonus(root_purity: int) -> float:
    return max(0.0, min(0.22, (root_purity - 40) / 250))


def purity_breakthrough_bonus(root_purity: int) -> int:
    return max(0, min(12, (root_purity - 40) // 6))


def purity_insight_bonus(root_purity: int) -> float:
    return max(0.0, min(0.18, (root_purity - 40) / 320))


def temperament_training_bonus(temperament: RootTemperament) -> float:
    return TEMPERAMENT_TRAINING_BONUS[temperament]


def temperament_breakthrough_bonus(temperament: RootTemperament) -> int:
    return TEMPERAMENT_BREAKTHROUGH_BONUS[temperament]


def temperament_insight_bonus(temperament: RootTemperament) -> float:
    return TEMPERAMENT_INSIGHT_BONUS[temperament]


def trait_training_bonus(trait: RootTrait) -> float:
    return TRAIT_TRAINING_BONUS[trait]


def trait_breakthrough_bonus(trait: RootTrait) -> int:
    return TRAIT_BREAKTHROUGH_BONUS[trait]


def trait_insight_bonus(trait: RootTrait) -> float:
    return TRAIT_INSIGHT_BONUS[trait]


def trait_lifespan_bonus(trait: RootTrait) -> int:
    return TRAIT_LIFESPAN_BONUS[trait]


def method_grade_practice_bonus(grade: MethodGrade) -> float:
    return METHOD_GRADE_PRACTICE_BONUS[grade]


def method_grade_breakthrough_bonus(grade: MethodGrade) -> int:
    return METHOD_GRADE_BREAKTHROUGH_BONUS[grade]


def meditation_mode_reward_multiplier(mode: MeditationMode) -> float:
    return MEDITATION_MODE_REWARD_MULTIPLIER[mode]


def meditation_mode_insight_bonus(mode: MeditationMode) -> float:
    return MEDITATION_MODE_INSIGHT_BONUS[mode]


def meditation_mode_breakthrough_bonus(mode: MeditationMode) -> int:
    return MEDITATION_MODE_BREAKTHROUGH_BONUS[mode]


def affinity_synergy(root_affinity: Affinity, method_affinity: Affinity) -> float:
    if root_affinity == method_affinity:
        return 0.12
    if method_affinity == Affinity.VOID or root_affinity == Affinity.VOID:
        return 0.05
    if method_affinity == Affinity.WIND or root_affinity == Affinity.WIND:
        return 0.04
    if method_affinity == Affinity.THUNDER or root_affinity == Affinity.THUNDER:
        return 0.06
    try:
        root_index = AFFINITY_CYCLE.index(root_affinity)
        method_index = AFFINITY_CYCLE.index(method_affinity)
    except ValueError:
        return 0.0
    if (root_index + 1) % len(AFFINITY_CYCLE) == method_index:
        return 0.05
    if (method_index + 1) % len(AFFINITY_CYCLE) == root_index:
        return 0.02
    return 0.0


def affinity_specialization_bonus(root_affinity: Affinity, method_affinity: Affinity) -> dict[str, float | int]:
    if root_affinity == method_affinity:
        return {
            "practice": 0.04,
            "breakthrough": 3,
            "insight": 0.02,
            "adventure": 2,
        }
    if root_affinity == Affinity.THUNDER:
        if method_affinity in {Affinity.THUNDER, Affinity.FIRE, Affinity.WIND}:
            return {
                "practice": 0.02,
                "breakthrough": 4,
                "insight": 0.00,
                "adventure": 4,
            }
    if root_affinity == Affinity.VOID:
        if method_affinity in {Affinity.VOID, Affinity.WATER, Affinity.WIND}:
            return {
                "practice": 0.01,
                "breakthrough": 1,
                "insight": 0.05,
                "adventure": 1,
            }
    if root_affinity == Affinity.WIND:
        if method_affinity in {Affinity.WIND, Affinity.WOOD, Affinity.WATER}:
            return {
                "practice": 0.02,
                "breakthrough": 1,
                "insight": 0.01,
                "adventure": 4,
            }
    if root_affinity == Affinity.FIRE:
        if method_affinity in {Affinity.FIRE, Affinity.THUNDER, Affinity.EARTH}:
            return {
                "practice": 0.02,
                "breakthrough": 3,
                "insight": 0.00,
                "adventure": 3,
            }
    if root_affinity == Affinity.WATER:
        if method_affinity in {Affinity.WATER, Affinity.WOOD, Affinity.VOID}:
            return {
                "practice": 0.01,
                "breakthrough": 1,
                "insight": 0.03,
                "adventure": 1,
            }
    if root_affinity == Affinity.WOOD:
        if method_affinity in {Affinity.WOOD, Affinity.WATER, Affinity.WIND}:
            return {
                "practice": 0.03,
                "breakthrough": 1,
                "insight": 0.02,
                "adventure": 1,
            }
    if root_affinity == Affinity.EARTH:
        if method_affinity in {Affinity.EARTH, Affinity.METAL, Affinity.FIRE}:
            return {
                "practice": 0.02,
                "breakthrough": 3,
                "insight": 0.01,
                "adventure": 0,
            }
    if root_affinity == Affinity.METAL:
        if method_affinity in {Affinity.METAL, Affinity.EARTH, Affinity.WATER}:
            return {
                "practice": 0.02,
                "breakthrough": 2,
                "insight": 0.01,
                "adventure": 2,
            }
    return {
        "practice": 0.0,
        "breakthrough": 0,
        "insight": 0.0,
        "adventure": 0,
    }


def affinity_method_bias(root_affinity: Affinity, method_affinity: Affinity) -> dict[str, float | int]:
    if root_affinity == Affinity.THUNDER and method_affinity in {Affinity.THUNDER, Affinity.FIRE}:
        return {"practice": 0.03, "breakthrough": 4, "insight": 0.0, "adventure": 3}
    if root_affinity == Affinity.VOID and method_affinity in {Affinity.VOID, Affinity.WATER}:
        return {"practice": 0.02, "breakthrough": 1, "insight": 0.04, "adventure": 1}
    if root_affinity == Affinity.WIND and method_affinity in {Affinity.WIND, Affinity.WOOD}:
        return {"practice": 0.03, "breakthrough": 2, "insight": 0.02, "adventure": 3}
    if root_affinity == Affinity.FIRE and method_affinity in {Affinity.FIRE, Affinity.EARTH}:
        return {"practice": 0.02, "breakthrough": 3, "insight": 0.0, "adventure": 2}
    if root_affinity == Affinity.WATER and method_affinity in {Affinity.WATER, Affinity.WOOD}:
        return {"practice": 0.03, "breakthrough": 1, "insight": 0.03, "adventure": 1}
    if root_affinity == Affinity.METAL and method_affinity in {Affinity.METAL, Affinity.EARTH}:
        return {"practice": 0.02, "breakthrough": 2, "insight": 0.01, "adventure": 2}
    if root_affinity == Affinity.EARTH and method_affinity in {Affinity.EARTH, Affinity.FIRE}:
        return {"practice": 0.02, "breakthrough": 2, "insight": 0.01, "adventure": 0}
    if root_affinity == Affinity.WOOD and method_affinity in {Affinity.WOOD, Affinity.WATER}:
        return {"practice": 0.03, "breakthrough": 1, "insight": 0.02, "adventure": 1}
    return {"practice": 0.0, "breakthrough": 0, "insight": 0.0, "adventure": 0}
