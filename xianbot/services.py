from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from xianbot.config import get_settings
from xianbot.domain import (
    Affinity,
    DestinyType,
    MeditationMode,
    MethodGrade,
    MethodStyle,
    MethodType,
    Player,
    Realm,
    RootTemperament,
    RootTrait,
    RootType,
)
from xianbot.progression import calculate_rebirth_outcome, can_rebirth
from xianbot.repository import GameRepository
from xianbot.rules import (
    affinity_method_bias,
    affinity_synergy,
    affinity_specialization_bonus,
    breakthrough_base_chance,
    meditation_mode_breakthrough_bonus,
    meditation_mode_insight_bonus,
    meditation_mode_reward_multiplier,
    method_grade_breakthrough_bonus,
    method_grade_practice_bonus,
    next_realm,
    purity_breakthrough_bonus,
    purity_insight_bonus,
    purity_training_bonus,
    realm_index,
    realm_requirement,
    root_adventure_bonus,
    root_breakthrough_bonus,
    root_purity_range,
    root_training_multiplier,
    temperament_breakthrough_bonus,
    temperament_insight_bonus,
    temperament_training_bonus,
    trait_breakthrough_bonus,
    trait_insight_bonus,
    trait_lifespan_bonus,
    trait_training_bonus,
)


ROOT_ROLL_TABLE: tuple[tuple[int, RootType], ...] = (
    (45, RootType.MORTAL),
    (75, RootType.YELLOW),
    (92, RootType.MYSTIC),
    (99, RootType.EARTH),
    (100, RootType.HEAVEN),
)

ROOT_TYPE_ORDER: tuple[RootType, ...] = (
    RootType.MORTAL,
    RootType.YELLOW,
    RootType.MYSTIC,
    RootType.EARTH,
    RootType.HEAVEN,
)

ROOT_AFFINITY_ROLLS: tuple[tuple[int, Affinity], ...] = (
    (16, Affinity.METAL),
    (32, Affinity.WOOD),
    (48, Affinity.WATER),
    (64, Affinity.FIRE),
    (80, Affinity.EARTH),
    (90, Affinity.WIND),
    (98, Affinity.THUNDER),
    (100, Affinity.VOID),
)

AFFINITY_RARE_OFFSETS: dict[Affinity, int] = {
    Affinity.WIND: 2,
    Affinity.THUNDER: 4,
    Affinity.VOID: 6,
}

ROOT_TEMPERAMENT_ROLLS: tuple[tuple[int, RootTemperament], ...] = (
    (28, RootTemperament.BALANCED),
    (46, RootTemperament.FIERCE),
    (68, RootTemperament.TRANQUIL),
    (85, RootTemperament.NIMBLE),
    (100, RootTemperament.ENLIGHTENED),
)

ROOT_TRAIT_ROLLS: tuple[tuple[int, RootTrait], ...] = (
    (25, RootTrait.GATHERING),
    (43, RootTrait.FLOWING),
    (64, RootTrait.INSIGHTFUL),
    (78, RootTrait.EVERGREEN),
    (92, RootTrait.WANDERING),
    (100, RootTrait.EMBER),
)

DESTINY_ROLLS: tuple[tuple[int, DestinyType], ...] = (
    (22, DestinyType.FORTUNE),
    (42, DestinyType.ALCHEMY),
    (62, DestinyType.BATTLE),
    (80, DestinyType.WISDOM),
    (92, DestinyType.RESILIENT),
    (100, DestinyType.TURNFATE),
)

DESTINY_DESCRIPTIONS: dict[DestinyType, str] = {
    DestinyType.FORTUNE: "更容易得到福缘、签到分红与高段奇遇。",
    DestinyType.ALCHEMY: "炼丹更稳，丹药收益也更高。",
    DestinyType.BATTLE: "斗法与历练更强势，但更偏进攻。",
    DestinyType.WISDOM: "参悟、闭关和功法熟练成长更顺。",
    DestinyType.RESILIENT: "突破与承伤更稳，失败损耗更轻。",
    DestinyType.TURNFATE: "坏运更难压到底，逆风时更容易翻盘。",
}

MASTERY_TITLES: tuple[tuple[int, str], ...] = (
    (0, "初窥"),
    (80, "小成"),
    (180, "大成"),
    (320, "圆融"),
    (520, "通玄"),
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

WORLD_EVENT_POOL: tuple[dict[str, Any], ...] = (
    {
        "event_key": "secret-realm",
        "title": "玄脉秘境开启",
        "description": "群山地脉松动，一处正在成形的秘境裂口显化于世，需众修尽快稳住入口。",
        "objective": "通过历练清剿外围异兽、稳固秘境入口。",
        "focus_actions": ("adventure",),
        "base_target": 20,
        "target_variation": 6,
        "reward_spirit_stones": 180,
        "reward_cultivation": 260,
        "reward_insight": 1,
        "reward_item_id": "spirit-herb",
        "reward_item_quantity": 2,
        "bonus_text": "历练额外获得修为与灵石，适合全群冲进度。",
        "participation_hint": "多用“历练”推进进度。",
        "bonus_values": {
            "adventure_cultivation": 0.12,
            "adventure_spirit": 0.10,
        },
    },
    {
        "event_key": "ruin-echo",
        "title": "残碑道藏出世",
        "description": "古碑虚影自天外坠下，碑文碎片散落四方，正是奇遇频发之时。",
        "objective": "通过奇遇搜集残碑气机，拼合本日道藏。",
        "focus_actions": ("encounter",),
        "base_target": 18,
        "target_variation": 5,
        "reward_spirit_stones": 150,
        "reward_cultivation": 220,
        "reward_insight": 2,
        "reward_item_id": "method-fragment",
        "reward_item_quantity": 1,
        "bonus_text": "奇遇期间更易增福缘与道悟，适合搏一手高波动收益。",
        "participation_hint": "多用“奇遇”搜集残碑气机。",
        "bonus_values": {
            "encounter_fortune": 1,
            "encounter_insight": 1,
        },
    },
    {
        "event_key": "pill-tide",
        "title": "丹炉潮升",
        "description": "天地药性活跃，火候更易相合，诸多丹师都在争抢今日的成丹良机。",
        "objective": "通过炼丹积蓄药潮，催生今日丹脉回响。",
        "focus_actions": ("alchemy",),
        "base_target": 14,
        "target_variation": 4,
        "reward_spirit_stones": 160,
        "reward_cultivation": 180,
        "reward_insight": 1,
        "reward_item_id": "flame-sand",
        "reward_item_quantity": 1,
        "bonus_text": "炼丹成功率更高，成丹后更容易反哺心神。",
        "participation_hint": "多用“炼丹”推进药潮进度。",
        "bonus_values": {
            "alchemy_chance": 7,
            "alchemy_insight": 1,
        },
    },
    {
        "event_key": "doctrine-conclave",
        "title": "论道法会",
        "description": "诸修同观天痕，法会共鸣之下，闭关与参悟都更容易触及关键处。",
        "objective": "通过参悟与参玄闭关积累论道余韵，完成今日法会。",
        "focus_actions": ("insight", "meditation_insight"),
        "base_target": 16,
        "target_variation": 5,
        "reward_spirit_stones": 130,
        "reward_cultivation": 260,
        "reward_insight": 3,
        "reward_item_id": "method-fragment",
        "reward_item_quantity": 1,
        "bonus_text": "参悟熟练增长更快，参玄闭关的道悟产出也更高。",
        "participation_hint": "用“参悟”或“闭关 参玄”共同推进法会。",
        "bonus_values": {
            "contemplate_mastery": 4,
            "meditation_insight": 2,
        },
    },
    {
        "event_key": "demon-incursion",
        "title": "邪修犯境",
        "description": "边境灵脉震荡，群修需以斗法镇压煞气，今日胜负不仅关乎个人颜面。",
        "objective": "通过斗法压制邪氛，守住今日灵脉。",
        "focus_actions": ("duel",),
        "base_target": 12,
        "target_variation": 4,
        "reward_spirit_stones": 220,
        "reward_cultivation": 320,
        "reward_insight": 1,
        "reward_item_id": "essence-pill",
        "reward_item_quantity": 1,
        "bonus_text": "斗法胜者额外获得灵石与修为，适合群里切磋带动事件。",
        "participation_hint": "多用“斗法 @目标”压制邪氛。",
        "bonus_values": {
            "duel_spirit": 40,
            "duel_cultivation": 30,
        },
    },
    {
        "event_key": "heaven-gate",
        "title": "天关共鸣",
        "description": "天地关隘短暂松动，冲关修士与闭关凝练者都能借这一线天机前行。",
        "objective": "通过突破与冲关闭关引动天关共鸣，完成今日天机汇聚。",
        "focus_actions": ("breakthrough", "meditation_breakthrough"),
        "base_target": 12,
        "target_variation": 4,
        "reward_spirit_stones": 180,
        "reward_cultivation": 300,
        "reward_insight": 2,
        "reward_item_id": "essence-pill",
        "reward_item_quantity": 1,
        "bonus_text": "突破成功率更高，冲关闭关更能积蓄底蕴。",
        "participation_hint": "用“突破”或“闭关 冲关”共同引动天关。",
        "bonus_values": {
            "breakthrough_chance": 6,
            "breakthrough_guard": 4,
            "meditation_breakthrough_multiplier": 0.25,
        },
    },
)

ALCHEMY_RECIPES: tuple[dict[str, Any], ...] = (
    {
        "name": "聚气丹",
        "item_id": "qigather",
        "materials": (
            ("spirit-herb", "灵草", 2),
            ("clear-dew", "灵泉水", 1),
        ),
        "base_chance": 84,
        "required_rebirth_count": 0,
        "favored_affinities": (Affinity.WOOD, Affinity.FIRE),
        "favored_styles": (MethodStyle.STEADY, MethodStyle.SURGING),
        "description": "稳定产出修为丹药，适合前中期日常自给。",
    },
    {
        "name": "回灵散",
        "item_id": "restore-powder",
        "materials": (
            ("spirit-herb", "灵草", 1),
            ("clear-dew", "灵泉水", 1),
        ),
        "base_chance": 90,
        "required_rebirth_count": 0,
        "favored_affinities": (Affinity.WOOD, Affinity.WATER),
        "favored_styles": (MethodStyle.STEADY, MethodStyle.INSIGHT),
        "description": "回复体力，适合历练与斗法前后周转。",
    },
    {
        "name": "凝元丹",
        "item_id": "essence-pill",
        "materials": (
            ("spirit-herb", "灵草", 2),
            ("clear-dew", "灵泉水", 1),
            ("flame-sand", "赤焰砂", 1),
        ),
        "base_chance": 72,
        "required_rebirth_count": 0,
        "favored_affinities": (Affinity.FIRE, Affinity.EARTH),
        "favored_styles": (MethodStyle.SURGING, MethodStyle.STEADY),
        "description": "专门为冲关积蓄底蕴，是大境界前的重要储备丹。",
    },
    {
        "name": "悟道丹",
        "item_id": "insight-pill",
        "materials": (
            ("spirit-herb", "灵草", 2),
            ("clear-dew", "灵泉水", 1),
            ("moon-dust", "月华粉", 1),
        ),
        "base_chance": 68,
        "required_rebirth_count": 0,
        "favored_affinities": (Affinity.WATER, Affinity.VOID),
        "favored_styles": (MethodStyle.INSIGHT, MethodStyle.REBIRTH),
        "description": "提升道悟，帮助参玄、参悟与后续构筑功法流派。",
    },
    {
        "name": "洗髓丹",
        "item_id": "marrow-pill",
        "materials": (
            ("clear-dew", "灵泉水", 2),
            ("flame-sand", "赤焰砂", 1),
            ("moon-dust", "月华粉", 1),
            ("marrow-jade", "洗髓玉", 1),
        ),
        "base_chance": 52,
        "required_rebirth_count": 1,
        "favored_affinities": (Affinity.THUNDER, Affinity.VOID),
        "favored_styles": (MethodStyle.REBIRTH, MethodStyle.INSIGHT),
        "description": "转世者专属丹药，用来洗练灵根纯度、性情与特质。",
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
    new_realm_cap: str
    root_brief: str
    destiny_name: str
    destiny_level: int


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
class WorldEventResult:
    event_date: str
    title: str
    description: str
    objective: str
    current_progress: int
    target_progress: int
    completed: bool
    bonus_text: str
    participation_hint: str
    reward_summary: str
    player_contribution: int = 0
    claimed: bool = False


@dataclass(slots=True)
class WorldEventClaimResult:
    title: str
    contribution: int
    reward_spirit_stones: int
    reward_cultivation: int
    reward_insight: int
    reward_item_name: str | None = None
    reward_item_quantity: int = 0


@dataclass(slots=True)
class AncientTrialResult:
    trial_name: str
    roll_value: int
    chance_percent: int
    success: bool
    reward_spirit_stones: int
    reward_cultivation: int
    reward_insight: int
    reward_item_name: str | None
    message: str


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
    insight_delta: int = 0
    lifespan_notice: str | None = None
    event_notice: str | None = None


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
    insight_delta: int = 0
    lifespan_notice: str | None = None
    event_notice: str | None = None


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
    unlocked_methods: list[str] = field(default_factory=list)
    preparation_cost: int = 0
    event_notice: str | None = None


@dataclass(slots=True)
class MeditationResult:
    minutes: int
    reward: int
    until: str
    world_title: str
    method_name: str | None
    mode_name: str
    insight_reward: int = 0
    breakthrough_reward: int = 0


@dataclass(slots=True)
class MeditationClaimResult:
    reward: int
    minutes: int
    still_waiting: bool
    method_name: str | None = None
    mastery_gain: int = 0
    lifespan_notice: str | None = None
    remaining_minutes: int = 0
    mode_name: str | None = None
    insight_gain: int = 0
    breakthrough_ready_gain: int = 0
    event_notice: str | None = None


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
    insight_gain: int = 0
    breakthrough_ready_gain: int = 0
    event_notice: str | None = None


@dataclass(slots=True)
class PrimaryMethodResult:
    method_name: str
    mastery_title: str
    practice_bonus_percent: int
    breakthrough_bonus_percent: int
    insight_bonus_percent: int


@dataclass(slots=True)
class DestinyResult:
    destiny_name: str
    destiny_level: int
    description: str


@dataclass(slots=True)
class AlchemyResult:
    item_name: str
    roll_value: int
    chance_percent: int
    success: bool
    quantity: int
    world_title: str
    message: str
    byproduct_name: str | None = None
    byproduct_quantity: int = 0
    insight_gain: int = 0
    event_notice: str | None = None


@dataclass(slots=True)
class DuelResult:
    attacker_name: str
    defender_name: str
    winner_name: str
    loser_name: str
    attacker_roll: int
    defender_roll: int
    attacker_total: int
    defender_total: int
    world_title: str
    message: str
    winner_spirit_stones_gain: int
    winner_cultivation_gain: int
    winner_insight_gain: int
    loser_cultivation_loss: int
    attacker_stamina_delta: int
    defender_stamina_delta: int
    rounds: list[str] = field(default_factory=list)
    event_notice: str | None = None


def get_repository() -> GameRepository:
    return GameRepository(get_settings().database_url)


def _now() -> datetime:
    return datetime.now()


def _today() -> date:
    return _now().date()


def _root_rank(root_type: RootType) -> int:
    return ROOT_TYPE_ORDER.index(root_type)


def _effective_max_realm(player: Player) -> Realm:
    if player.rebirth_count <= 0:
        return Realm.FOUNDATION_4
    if player.rebirth_count == 1:
        return Realm.CORE_4
    if player.rebirth_count == 2:
        return Realm.NASCENT_4
    return Realm.SPIRIT_4


def _realm_cap_brief(player: Player) -> str:
    return _effective_max_realm(player).value


def _root_rarity_brief(player: Player) -> str:
    rare_bias = AFFINITY_RARE_OFFSETS.get(player.root_affinity, 0)
    if player.root_affinity == Affinity.VOID:
        return "太虚异灵根"
    if player.root_affinity == Affinity.THUNDER:
        return "天雷异灵根"
    if player.root_affinity == Affinity.WIND:
        return "罡风异灵根"
    if rare_bias > 0:
        return "偏异灵根"
    return "五行正灵根"


def _weighted_choice(table: tuple[tuple[int, Any], ...], roll: int | None = None) -> Any:
    value = random.randint(1, 100) if roll is None else roll
    for threshold, result in table:
        if value <= threshold:
            return result
    return table[-1][1]


def _player_with_updates(player: Player, **changes: object) -> Player:
    data = {
        field_name: getattr(player, field_name)
        for field_name in player.__dataclass_fields__
    }
    data.update(changes)
    return Player(**data)


def roll_root_type(root_floor: RootType | None = None) -> RootType:
    rolled = _weighted_choice(ROOT_ROLL_TABLE)
    if root_floor is None:
        return rolled
    if _root_rank(rolled) < _root_rank(root_floor):
        return root_floor
    return rolled


def _roll_root_affinity(rebirth_count: int) -> Affinity:
    roll = random.randint(1, 100)
    if rebirth_count >= 3 and roll >= 93:
        return random.choice([Affinity.THUNDER, Affinity.VOID])
    if rebirth_count >= 2 and roll >= 88:
        return random.choice([Affinity.WIND, Affinity.THUNDER, Affinity.VOID])
    if rebirth_count >= 1 and roll >= 84:
        return random.choice([Affinity.WIND, Affinity.THUNDER])
    return _weighted_choice(ROOT_AFFINITY_ROLLS, roll=roll)


def _roll_root_trait(rebirth_count: int) -> RootTrait:
    if rebirth_count > 0 and random.random() < min(0.45, 0.15 + rebirth_count * 0.08):
        return RootTrait.EMBER
    return _weighted_choice(ROOT_TRAIT_ROLLS)


def _generate_root_profile(
    root_floor: RootType | None = None,
    rebirth_count: int = 0,
) -> dict[str, object]:
    root_type = roll_root_type(root_floor)
    purity_min, purity_max = root_purity_range(root_type)
    if rebirth_count > 0:
        purity_min = min(99, purity_min + min(8, rebirth_count * 2))
        purity_max = min(99, purity_max + min(10, rebirth_count * 3))
    root_purity = min(99, random.randint(purity_min, purity_max) + rebirth_count)
    root_affinity = _roll_root_affinity(rebirth_count)
    root_temperament = _weighted_choice(ROOT_TEMPERAMENT_ROLLS)
    root_trait = _roll_root_trait(rebirth_count)
    return {
        "root_type": root_type,
        "root_affinity": root_affinity,
        "root_purity": root_purity,
        "root_temperament": root_temperament,
        "root_trait": root_trait,
    }


def _generate_destiny_profile(rebirth_count: int, legacy_points: int) -> dict[str, object]:
    if rebirth_count < 2:
        return {"destiny_type": None, "destiny_level": 0}
    destiny_type = _roll_destiny_type(rebirth_count)
    destiny_level = _destiny_level_for_player(rebirth_count, legacy_points)
    return {
        "destiny_type": destiny_type,
        "destiny_level": destiny_level,
    }


def mastery_title(mastery: int) -> str:
    current = MASTERY_TITLES[0][1]
    for threshold, title in MASTERY_TITLES:
        if mastery >= threshold:
            current = title
        else:
            break
    return current


def _mastery_practice_bonus(mastery: int) -> float:
    return min(0.18, (mastery // 60) * 0.03)


def _mastery_breakthrough_bonus(mastery: int) -> int:
    return min(18, (mastery // 60) * 3)


def _mastery_insight_bonus(mastery: int) -> float:
    return min(0.16, (mastery // 70) * 0.03)


def _root_training_bonus(player: Player) -> float:
    bonus = 0.0
    bonus += root_training_multiplier(player.root_type)
    bonus += purity_training_bonus(player.root_purity)
    bonus += temperament_training_bonus(player.root_temperament)
    bonus += trait_training_bonus(player.root_trait)
    bonus += _destiny_training_bonus(player)
    if player.rebirth_count > 0 and player.root_trait == RootTrait.EMBER:
        bonus += min(0.04, player.rebirth_count * 0.01)
    return bonus


def _root_breakthrough_total(player: Player) -> int:
    bonus = 0
    bonus += root_breakthrough_bonus(player.root_type)
    bonus += purity_breakthrough_bonus(player.root_purity)
    bonus += temperament_breakthrough_bonus(player.root_temperament)
    bonus += trait_breakthrough_bonus(player.root_trait)
    bonus += _destiny_breakthrough_bonus(player)
    if player.root_affinity in {Affinity.THUNDER, Affinity.VOID}:
        bonus += 2
    if player.rebirth_count > 0 and player.root_trait == RootTrait.EMBER:
        bonus += min(4, player.rebirth_count)
    return bonus


def _root_insight_total(player: Player) -> float:
    bonus = 0.0
    bonus += purity_insight_bonus(player.root_purity)
    bonus += temperament_insight_bonus(player.root_temperament)
    bonus += trait_insight_bonus(player.root_trait)
    bonus += _destiny_insight_bonus(player)
    if player.root_affinity == Affinity.VOID:
        bonus += 0.05
    elif player.root_affinity == Affinity.THUNDER:
        bonus += 0.03
    return bonus


def _root_adventure_total(player: Player) -> int:
    bonus = root_adventure_bonus(player.root_type)
    bonus += max(0, (player.root_purity - 50) // 12)
    if player.root_trait == RootTrait.WANDERING:
        bonus += 4
    if player.root_temperament == RootTemperament.NIMBLE:
        bonus += 3
    if player.root_temperament == RootTemperament.FIERCE:
        bonus += 2
    bonus += _destiny_adventure_bonus(player)
    return bonus


def _alchemy_affinity_bias(
    player: Player,
    recipe: dict[str, Any],
    method: dict[str, object] | None,
) -> dict[str, int]:
    item_id = str(recipe["item_id"])
    chance = 0
    double = 0
    insight = 0

    if item_id in {"qigather", "restore-powder"}:
        if player.root_affinity == Affinity.WOOD:
            chance += 4
            double += 1
        elif player.root_affinity == Affinity.WATER:
            chance += 3
            insight += 1
        elif player.root_affinity == Affinity.EARTH:
            chance += 2
    elif item_id == "essence-pill":
        if player.root_affinity == Affinity.FIRE:
            chance += 4
            double += 1
        elif player.root_affinity == Affinity.EARTH:
            chance += 4
        elif player.root_affinity == Affinity.METAL:
            chance += 2
            double += 1
    elif item_id == "insight-pill":
        if player.root_affinity == Affinity.WATER:
            chance += 4
            insight += 1
        elif player.root_affinity == Affinity.VOID:
            chance += 5
            double += 1
            insight += 1
        elif player.root_affinity == Affinity.WIND:
            chance += 3
    elif item_id == "marrow-pill":
        if player.root_affinity == Affinity.THUNDER:
            chance += 5
            double += 1
        elif player.root_affinity == Affinity.VOID:
            chance += 6
            insight += 1
        elif player.root_affinity == Affinity.FIRE:
            chance += 2

    if method is not None and Affinity(str(method["affinity"])) == player.root_affinity:
        chance += 2
        if item_id in {"insight-pill", "marrow-pill"}:
            double += 1

    return {
        "chance": chance,
        "double": double,
        "insight": insight,
    }


def _meditation_affinity_bias(player: Player, mode: MeditationMode) -> dict[str, float | int]:
    reward = 0.0
    insight = 0
    breakthrough = 0

    if mode == MeditationMode.BREATH:
        if player.root_affinity == Affinity.WOOD:
            reward += 0.06
        elif player.root_affinity == Affinity.WATER:
            reward += 0.04
            insight += 1
        elif player.root_affinity == Affinity.EARTH:
            reward += 0.05
            breakthrough += 1
    elif mode == MeditationMode.CONDENSE:
        if player.root_affinity == Affinity.EARTH:
            reward += 0.05
            breakthrough += 3
        elif player.root_affinity == Affinity.METAL:
            reward += 0.03
            breakthrough += 2
        elif player.root_affinity == Affinity.FIRE:
            breakthrough += 2
    elif mode == MeditationMode.INSIGHT:
        if player.root_affinity == Affinity.WATER:
            reward += 0.03
            insight += 3
        elif player.root_affinity == Affinity.VOID:
            reward += 0.04
            insight += 4
        elif player.root_affinity == Affinity.WIND:
            reward += 0.02
            insight += 2
    elif mode == MeditationMode.BREAKTHROUGH:
        if player.root_affinity == Affinity.THUNDER:
            breakthrough += 5
        elif player.root_affinity == Affinity.FIRE:
            breakthrough += 4
        elif player.root_affinity == Affinity.METAL:
            breakthrough += 3
        elif player.root_affinity == Affinity.EARTH:
            breakthrough += 2

    if player.root_affinity == Affinity.VOID and mode != MeditationMode.BREAKTHROUGH:
        insight += 1

    return {
        "reward": reward,
        "insight": insight,
        "breakthrough": breakthrough,
    }


def _root_loot_choice(
    player: Player,
    options: list[str] | tuple[str, ...],
) -> str:
    weighted = list(options)
    preferences: dict[Affinity, tuple[str, ...]] = {
        Affinity.WOOD: ("spirit-herb", "clear-dew", "longevity-fruit"),
        Affinity.WATER: ("clear-dew", "moon-dust", "insight-pill"),
        Affinity.FIRE: ("flame-sand", "essence-pill", "qigather"),
        Affinity.EARTH: ("essence-pill", "longevity-fruit", "marrow-jade"),
        Affinity.METAL: ("essence-pill", "method-fragment", "rebirth-mark"),
        Affinity.WIND: ("method-fragment", "clear-dew", "longevity-fruit"),
        Affinity.THUNDER: ("rebirth-mark", "flame-sand", "marrow-jade"),
        Affinity.VOID: ("method-fragment", "moon-dust", "marrow-jade", "rebirth-mark"),
    }
    repeat = 2 + min(2, max(0, player.rebirth_count))
    for preferred in preferences.get(player.root_affinity, ()):
        if preferred in options:
            weighted.extend([preferred] * repeat)
    if player.root_trait == RootTrait.WANDERING and "method-fragment" in options:
        weighted.extend(["method-fragment"] * 2)
    if player.root_trait == RootTrait.EMBER and "rebirth-mark" in options:
        weighted.extend(["rebirth-mark"] * max(1, min(3, player.rebirth_count or 1)))
    if player.root_temperament == RootTemperament.TRANQUIL and "moon-dust" in options:
        weighted.append("moon-dust")
    if player.root_temperament == RootTemperament.FIERCE and "flame-sand" in options:
        weighted.append("flame-sand")
    return random.choice(weighted)


def _root_affinity_duel_bonus(player: Player) -> int:
    if player.root_affinity == Affinity.THUNDER:
        return 6
    if player.root_affinity == Affinity.FIRE:
        return 4
    if player.root_affinity == Affinity.WIND:
        return 3
    if player.root_affinity == Affinity.WATER:
        return 2
    if player.root_affinity == Affinity.METAL:
        return 2
    if player.root_affinity == Affinity.EARTH:
        return 1
    return 0


def _ancient_trial_item_id(player: Player) -> str:
    if player.rebirth_count >= 3:
        return _root_loot_choice(
            player,
            ("rebirth-mark", "marrow-jade", "method-fragment", "longevity-fruit"),
        )
    return _root_loot_choice(
        player,
        ("method-fragment", "moon-dust", "longevity-fruit"),
    )


def _method_style_modifiers(player: Player, method: dict[str, object]) -> dict[str, float | int]:
    style = MethodStyle(str(method["style"]))
    method_type = MethodType(str(method["method_type"]))
    practice = 0.0
    breakthrough = 0
    insight = 0.0
    adventure = 0

    if style == MethodStyle.STEADY:
        practice += 0.03
        if player.root_temperament in {RootTemperament.BALANCED, RootTemperament.TRANQUIL}:
            breakthrough += 1
    elif style == MethodStyle.SURGING:
        breakthrough += 3
        adventure += 4
        if player.root_temperament == RootTemperament.FIERCE:
            practice += 0.02
    elif style == MethodStyle.INSIGHT:
        insight += 0.05
        if player.root_temperament in {RootTemperament.ENLIGHTENED, RootTemperament.TRANQUIL}:
            practice += 0.02
    elif style == MethodStyle.UNFETTERED:
        adventure += 5
        practice += 0.01
        if player.root_trait == RootTrait.WANDERING:
            insight += 0.03
    elif style == MethodStyle.REBIRTH:
        insight += 0.04
        breakthrough += 2
        if player.rebirth_count > 0:
            practice += 0.03
            breakthrough += min(4, player.rebirth_count)
            insight += min(0.06, player.rebirth_count * 0.02)

    if method_type == MethodType.BREATH:
        practice += 0.02
    elif method_type == MethodType.MIND:
        insight += 0.03
    elif method_type == MethodType.BODY:
        breakthrough += 3
    elif method_type == MethodType.BATTLE:
        adventure += 4
        breakthrough += 2
    elif method_type == MethodType.REBIRTH and player.rebirth_count > 0:
        practice += 0.02
        breakthrough += 3
        insight += 0.04

    return {
        "practice": practice,
        "breakthrough": breakthrough,
        "insight": insight,
        "adventure": adventure,
    }


def _method_totals(player: Player, method: dict[str, object]) -> dict[str, float | int]:
    mastery = int(method.get("mastery", 0))
    affinity = Affinity(str(method["affinity"]))
    grade = MethodGrade(str(method["grade"]))
    style_modifiers = _method_style_modifiers(player, method)
    affinity_bias = affinity_method_bias(player.root_affinity, affinity)
    specialization_bonus = affinity_specialization_bonus(player.root_affinity, affinity)
    practice = (
        float(method["practice_bonus"])
        + method_grade_practice_bonus(grade)
        + _mastery_practice_bonus(mastery)
        + affinity_synergy(player.root_affinity, affinity)
        + float(style_modifiers["practice"])
        + float(affinity_bias["practice"])
        + float(specialization_bonus["practice"])
    )
    breakthrough = (
        int(float(method["breakthrough_bonus"]) * 100)
        + method_grade_breakthrough_bonus(grade)
        + _mastery_breakthrough_bonus(mastery)
        + int(affinity_synergy(player.root_affinity, affinity) * 100 / 3)
        + int(style_modifiers["breakthrough"])
        + int(affinity_bias["breakthrough"])
        + int(specialization_bonus["breakthrough"])
    )
    insight = (
        float(method.get("insight_bonus", 0.0))
        + _mastery_insight_bonus(mastery)
        + affinity_synergy(player.root_affinity, affinity) / 2
        + float(style_modifiers["insight"])
        + float(affinity_bias["insight"])
        + float(specialization_bonus["insight"])
    )
    return {
        "practice": practice,
        "breakthrough": breakthrough,
        "insight": insight,
        "adventure": (
            int(style_modifiers["adventure"])
            + int(affinity_bias["adventure"])
            + int(specialization_bonus["adventure"])
        ),
    }


def _enrich_method(player: Player, method: dict[str, object]) -> dict[str, object]:
    enriched = dict(method)
    totals = _method_totals(player, enriched)
    mastery = int(enriched.get("mastery", 0))
    enriched["mastery"] = mastery
    enriched["mastery_title"] = mastery_title(mastery)
    enriched["practice_total"] = round(float(totals["practice"]), 4)
    enriched["breakthrough_total"] = int(totals["breakthrough"])
    enriched["insight_total"] = round(float(totals["insight"]), 4)
    enriched["adventure_bonus"] = int(totals["adventure"])
    enriched["equipped"] = bool(int(enriched.get("equipped", 0)))
    return enriched


def _primary_method(player: Player, methods: list[dict[str, object]]) -> dict[str, object] | None:
    if not methods:
        return None
    if player.primary_method_id is not None:
        exact = next(
            (method for method in methods if str(method["id"]) == player.primary_method_id),
            None,
        )
        if exact is not None:
            return exact
    equipped = next((method for method in methods if bool(method.get("equipped"))), None)
    if equipped is not None:
        return equipped
    return max(
        methods,
        key=lambda method: (
            int(method.get("mastery", 0)),
            int(method.get("breakthrough_total", 0)),
            float(method.get("practice_total", 0.0)),
            float(method.get("insight_total", 0.0)),
        ),
    )


def _major_breakthrough(current: Realm, target: Realm | None) -> bool:
    if target is None:
        return True
    return current.name.endswith("_4") and target.name.endswith("_1")


def _lifespan_for_profile(root_type: RootType, root_trait: RootTrait) -> int:
    return 118 + _root_rank(root_type) * 3 + trait_lifespan_bonus(root_trait)


def _root_brief(player: Player) -> str:
    return f"{player.root_type.value}·{player.root_affinity.value}系·纯度{player.root_purity}·{player.root_temperament.value}/{player.root_trait.value}"


def _root_growth_brief(player: Player) -> str:
    return f"{_root_rarity_brief(player)} | 此生上限 { _realm_cap_brief(player) }"


def _lifespan_reward_multiplier(player: Player) -> float:
    ratio = player.age / max(player.lifespan, 1)
    if ratio >= 0.95:
        return 0.74 if player.root_trait == RootTrait.EVERGREEN else 0.72
    if ratio >= 0.85:
        return 0.84 if player.root_trait == RootTrait.EVERGREEN else 0.82
    if ratio >= 0.75:
        return 0.94 if player.root_trait == RootTrait.EVERGREEN else 0.92
    return 1.0


def _lifespan_breakthrough_penalty(player: Player) -> int:
    ratio = player.age / max(player.lifespan, 1)
    offset = 2 if player.root_trait == RootTrait.EVERGREEN else 0
    if ratio >= 0.95:
        return max(0, 12 - offset)
    if ratio >= 0.85:
        return max(0, 8 - offset)
    if ratio >= 0.75:
        return max(0, 4 - offset)
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


def _training_multiplier(player: Player, method: dict[str, object] | None) -> float:
    bonus = _root_training_bonus(player)
    if method is not None:
        bonus += float(method.get("practice_total", 0.0))
    return bonus


def _insight_multiplier(player: Player, method: dict[str, object] | None) -> float:
    bonus = _root_insight_total(player)
    if method is not None:
        bonus += float(method.get("insight_total", 0.0))
    return bonus


def _roll_destiny_type(rebirth_count: int) -> DestinyType:
    roll = random.randint(1, 100)
    if rebirth_count >= 2 and roll >= 94:
        return random.choice([DestinyType.TURNFATE, DestinyType.WISDOM, DestinyType.ALCHEMY])
    return _weighted_choice(DESTINY_ROLLS, roll=roll)


def _destiny_level_for_player(rebirth_count: int, legacy_points: int) -> int:
    return max(1, min(6, 1 + rebirth_count + legacy_points // 3))


def _destiny_brief(player: Player) -> str:
    if player.destiny_type is None or player.destiny_level <= 0:
        return "命格未显"
    return f"{player.destiny_type.value}·{player.destiny_level}重"


def _destiny_training_bonus(player: Player) -> float:
    if player.destiny_type == DestinyType.WISDOM:
        return 0.03 + player.destiny_level * 0.01
    if player.destiny_type == DestinyType.ALCHEMY:
        return 0.01 + player.destiny_level * 0.005
    return 0.0


def _destiny_insight_bonus(player: Player) -> float:
    if player.destiny_type == DestinyType.WISDOM:
        return 0.04 + player.destiny_level * 0.012
    if player.destiny_type == DestinyType.TURNFATE:
        return 0.015 * player.destiny_level
    return 0.0


def _destiny_breakthrough_bonus(player: Player) -> int:
    if player.destiny_type == DestinyType.RESILIENT:
        return 4 + player.destiny_level * 2
    if player.destiny_type == DestinyType.WISDOM:
        return 1 + player.destiny_level
    return 0


def _destiny_adventure_bonus(player: Player) -> int:
    if player.destiny_type == DestinyType.FORTUNE:
        return 4 + player.destiny_level * 2
    if player.destiny_type == DestinyType.BATTLE:
        return 3 + player.destiny_level * 2
    if player.destiny_type == DestinyType.TURNFATE:
        return 2 + player.destiny_level
    return 0


def _destiny_alchemy_bonus(player: Player) -> int:
    if player.destiny_type == DestinyType.ALCHEMY:
        return 8 + player.destiny_level * 3
    if player.destiny_type == DestinyType.WISDOM:
        return 3 + player.destiny_level
    return 0


def _destiny_duel_bonus(player: Player) -> int:
    if player.destiny_type == DestinyType.BATTLE:
        return 8 + player.destiny_level * 3
    if player.destiny_type == DestinyType.RESILIENT:
        return 3 + player.destiny_level * 2
    if player.destiny_type == DestinyType.TURNFATE:
        return 2 + player.destiny_level
    return 0


def _destiny_fortune_bonus(player: Player) -> int:
    if player.destiny_type == DestinyType.FORTUNE:
        return 5 + player.destiny_level * 2
    if player.destiny_type == DestinyType.TURNFATE:
        return 2 + player.destiny_level
    return 0


def _destiny_failure_guard(player: Player) -> int:
    if player.destiny_type == DestinyType.TURNFATE:
        return 4 + player.destiny_level * 2
    if player.destiny_type == DestinyType.RESILIENT:
        return 3 + player.destiny_level
    return 0


def _destiny_result(player: Player) -> DestinyResult:
    if player.destiny_type is None or player.destiny_level <= 0:
        return DestinyResult(destiny_name="命格未显", destiny_level=0, description="二转后方可真正凝出命格。")
    return DestinyResult(
        destiny_name=player.destiny_type.value,
        destiny_level=player.destiny_level,
        description=DESTINY_DESCRIPTIONS[player.destiny_type],
    )


def _find_alchemy_recipe(recipe_name: str) -> dict[str, Any] | None:
    target = recipe_name.strip()
    for recipe in ALCHEMY_RECIPES:
        if str(recipe["name"]) == target:
            return dict(recipe)
    return None


def _realm_power(player: Player) -> int:
    return realm_index(player.realm) * 18 + max(0, player.cultivation // 140)


def _duel_style_bonus(method: dict[str, object] | None) -> int:
    if method is None:
        return 0
    style = MethodStyle(str(method["style"]))
    method_type = MethodType(str(method["method_type"]))
    bonus = 0
    if style == MethodStyle.SURGING:
        bonus += 8
    elif style == MethodStyle.INSIGHT:
        bonus += 4
    elif style == MethodStyle.REBIRTH:
        bonus += 6
    if method_type == MethodType.BATTLE:
        bonus += 10
    elif method_type == MethodType.BODY:
        bonus += 7
    elif method_type == MethodType.REBIRTH:
        bonus += 5
    return bonus


def _duel_signature(player: Player, method: dict[str, object] | None) -> tuple[str, str]:
    if method is not None:
        style = str(method["style"])
        if MethodStyle(style) == MethodStyle.SURGING:
            return "破势", "迎风而上"
        if MethodStyle(style) == MethodStyle.INSIGHT:
            return "照心", "以静制动"
        if MethodStyle(style) == MethodStyle.REBIRTH:
            return "回轮", "借前尘翻盘"
        if MethodStyle(style) == MethodStyle.UNFETTERED:
            return "游锋", "游走牵制"
    if player.root_affinity == Affinity.THUNDER:
        return "雷势", "一击定音"
    if player.root_affinity == Affinity.WATER:
        return "水势", "缠斗消磨"
    if player.root_affinity == Affinity.FIRE:
        return "火势", "强攻压制"
    if player.root_affinity == Affinity.EARTH:
        return "山势", "稳守反击"
    return "平势", "见机应变"


def _duel_move_table(player: Player, method: dict[str, object] | None) -> list[dict[str, object]]:
    style = None if method is None else MethodStyle(str(method["style"]))
    method_type = None if method is None else MethodType(str(method["method_type"]))
    moves: list[dict[str, object]] = [
        {"name": "运转灵机", "power": 4, "guard": 2, "crit": 0, "heal": 0},
        {"name": "试探一式", "power": 7, "guard": 1, "crit": 5, "heal": 0},
        {"name": "回气守势", "power": 2, "guard": 6, "crit": 0, "heal": 4},
    ]
    if player.root_affinity == Affinity.THUNDER:
        moves[1]["name"] = "雷引一闪"
        moves[1]["power"] = 10
        moves[1]["crit"] = 9
    elif player.root_affinity == Affinity.FIRE:
        moves[1]["name"] = "烈焰直冲"
        moves[1]["power"] = 9
        moves[2]["heal"] = 2
    elif player.root_affinity == Affinity.WATER:
        moves[1]["name"] = "流水卸劲"
        moves[1]["guard"] = 4
        moves[2]["heal"] = 5
    elif player.root_affinity == Affinity.EARTH:
        moves[1]["name"] = "山岳镇压"
        moves[1]["guard"] = 3
        moves[2]["guard"] = 8
    elif player.root_affinity == Affinity.VOID:
        moves[1]["name"] = "虚步藏锋"
        moves[1]["crit"] = 8
        moves[2]["heal"] = 3

    if style == MethodStyle.SURGING:
        moves[1]["power"] = int(moves[1]["power"]) + 2
    elif style == MethodStyle.INSIGHT:
        moves[0]["guard"] = int(moves[0]["guard"]) + 2
        moves[2]["heal"] = int(moves[2]["heal"]) + 1
    elif style == MethodStyle.REBIRTH:
        moves[0]["crit"] = int(moves[0]["crit"]) + 2
        moves[1]["crit"] = int(moves[1]["crit"]) + 2
    elif style == MethodStyle.UNFETTERED:
        moves[1]["guard"] = int(moves[1]["guard"]) + 2

    if method_type == MethodType.BATTLE:
        moves[1]["power"] = int(moves[1]["power"]) + 2
    elif method_type == MethodType.BODY:
        moves[2]["guard"] = int(moves[2]["guard"]) + 2
    elif method_type == MethodType.REBIRTH:
        moves[0]["heal"] = int(moves[0]["heal"]) + 2
        moves[1]["crit"] = int(moves[1]["crit"]) + 1

    if player.rebirth_count > 0:
        moves[1]["crit"] = int(moves[1]["crit"]) + min(4, player.rebirth_count)
    if player.root_trait == RootTrait.EMBER:
        moves[1]["power"] = int(moves[1]["power"]) + 1
    if player.root_trait == RootTrait.WANDERING:
        moves[1]["crit"] = int(moves[1]["crit"]) + 1
    return moves


def _duel_rounds(
    attacker: Player,
    attacker_method: dict[str, object] | None,
    defender: Player,
    defender_method: dict[str, object] | None,
) -> list[str]:
    attacker_signature, attacker_style_hint = _duel_signature(attacker, attacker_method)
    defender_signature, defender_style_hint = _duel_signature(defender, defender_method)
    attacker_moves = _duel_move_table(attacker, attacker_method)
    defender_moves = _duel_move_table(defender, defender_method)
    attacker_hp = 100 + max(0, attacker.cultivation // 120)
    defender_hp = 100 + max(0, defender.cultivation // 120)
    logs: list[str] = []

    for round_no in range(1, 4):
        attacker_move = random.choice(attacker_moves)
        defender_move = random.choice(defender_moves)
        attacker_roll = random.randint(1, 100) + _duel_style_bonus(attacker_method) // 4
        defender_roll = random.randint(1, 100) + _duel_style_bonus(defender_method) // 4

        attacker_attack = (
            attacker_roll
            + int(attacker_move["power"])
            + _root_affinity_duel_bonus(attacker)
            + attacker.rebirth_count * 2
            + min(8, attacker.breakthrough_ready // 10)
        )
        defender_defense = (
            defender_roll
            + int(defender_move["guard"])
            + _root_affinity_duel_bonus(defender)
            + defender.rebirth_count * 2
            + min(8, defender.breakthrough_ready // 10)
        )
        attacker_damage = max(3, attacker_attack - defender_defense // 2)
        defender_damage = max(2, defender_roll + int(defender_move["power"]) - attacker_roll // 2)

        if int(attacker_move["heal"]) > 0:
            attacker_hp += int(attacker_move["heal"]) + max(0, attacker.insight // 30)
        if int(defender_move["heal"]) > 0:
            defender_hp += int(defender_move["heal"]) + max(0, defender.insight // 30)

        if int(attacker_move["crit"]) and attacker_roll + int(attacker_move["crit"]) >= defender_roll + 8:
            attacker_damage += 6 + attacker.rebirth_count
        if int(defender_move["crit"]) and defender_roll + int(defender_move["crit"]) >= attacker_roll + 8:
            defender_damage += 6 + defender.rebirth_count

        defender_hp -= attacker_damage
        attacker_hp -= defender_damage

        logs.append(
            f"第{round_no}回合：{attacker.nickname}【{attacker_move['name']}】↔{defender.nickname}【{defender_move['name']}】"
            f" | {attacker.nickname}-{attacker_damage} / {defender.nickname}-{defender_damage}"
            f" | 余势 {attacker_hp}/{defender_hp}"
        )
        if attacker_hp <= 0 or defender_hp <= 0:
            break

    logs.append(f"{attacker.nickname}以{attacker_signature}对{defender_signature}，{attacker_style_hint}；{defender_style_hint}。")
    return logs


def _duel_total(player: Player, method: dict[str, object] | None, roll_value: int) -> int:
    total = roll_value
    total += _realm_power(player)
    total += _root_breakthrough_total(player)
    total += _root_adventure_total(player) // 2
    total += _destiny_duel_bonus(player)
    total += min(20, player.comprehension // 2)
    total += min(24, player.insight // 2)
    total += min(15, player.fortune // 5)
    total += min(10, player.breakthrough_ready // 6)
    total += player.rebirth_count * 4
    total += _duel_style_bonus(method)
    if method is not None:
        total += min(24, int(method.get("breakthrough_total", 0)))
        total += min(18, int(float(method.get("practice_total", 0.0)) * 100 // 2))
        total += min(12, int(float(method.get("insight_total", 0.0)) * 100 // 3))
        total += min(14, int(method.get("mastery", 0)) // 18)
    total += _root_affinity_duel_bonus(player)
    if player.root_affinity in {Affinity.THUNDER, Affinity.FIRE}:
        total += 4
    if player.root_trait == RootTrait.EMBER:
        total += 5
    if player.root_trait == RootTrait.WANDERING:
        total += 3
    return total


async def _resolve_player_target(target: str) -> Player | None:
    repo = get_repository()
    normalized = target.strip()
    if not normalized:
        return None
    direct = await repo.get_player(normalized)
    if direct is not None:
        return direct
    if normalized.startswith("@"):
        normalized = normalized[1:]
    return await repo.get_player_by_nickname(normalized)


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


def _meditation_age_progress(
    player: Player,
    minutes: int,
    world_state: WorldStateResult,
    mode: MeditationMode,
) -> int:
    settings = get_settings()
    base_steps = max(0, (minutes + 59) // 60)
    progress = base_steps * settings.lifespan_progress_per_60_meditation_minutes
    progress += world_state.lifespan_bonus
    if mode == MeditationMode.BREAKTHROUGH:
        progress += 1
    if player.root_trait == RootTrait.EVERGREEN:
        progress -= 1
    return max(0, progress)


def _encounter_cost() -> int:
    return max(10, get_settings().adventure_stamina_cost - 5)


def _generate_world_state(state_date: str) -> dict[str, Any]:
    rng = random.Random(f"qxian-world-{state_date}")
    return dict(rng.choice(WORLD_STATE_POOL))


def _generate_world_event(state_date: str) -> dict[str, Any]:
    rng = random.Random(f"qxian-event-{state_date}")
    template = dict(rng.choice(WORLD_EVENT_POOL))
    variation = int(template["target_variation"])
    target_progress = int(template["base_target"]) + rng.randint(0, variation)
    return {
        "event_key": template["event_key"],
        "title": template["title"],
        "description": template["description"],
        "objective": template["objective"],
        "target_progress": target_progress,
        "current_progress": 0,
        "reward_spirit_stones": int(template["reward_spirit_stones"]),
        "reward_cultivation": int(template["reward_cultivation"]),
        "reward_insight": int(template["reward_insight"]),
        "reward_item_id": template["reward_item_id"],
        "reward_item_quantity": int(template["reward_item_quantity"]),
        "bonus_text": template["bonus_text"],
        "participation_hint": template["participation_hint"],
    }


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


async def _get_today_world_event() -> dict[str, Any]:
    repo = get_repository()
    event_date = _today().isoformat()
    event = await repo.get_world_event(event_date)
    if event is None:
        event = _generate_world_event(event_date)
        await repo.save_world_event(
            event_date=event_date,
            event_key=str(event["event_key"]),
            title=str(event["title"]),
            description=str(event["description"]),
            objective=str(event["objective"]),
            target_progress=int(event["target_progress"]),
            current_progress=int(event["current_progress"]),
            reward_spirit_stones=int(event["reward_spirit_stones"]),
            reward_cultivation=int(event["reward_cultivation"]),
            reward_insight=int(event["reward_insight"]),
            reward_item_id=None if event["reward_item_id"] is None else str(event["reward_item_id"]),
            reward_item_quantity=int(event["reward_item_quantity"]),
            bonus_text=str(event["bonus_text"]),
            participation_hint=str(event["participation_hint"]),
        )
    return event


def _world_event_template(event_key: str) -> dict[str, Any]:
    for template in WORLD_EVENT_POOL:
        if str(template["event_key"]) == event_key:
            return dict(template)
    return {}


def _world_event_bonus_values(event_key: str) -> dict[str, Any]:
    template = _world_event_template(event_key)
    return dict(template.get("bonus_values", {}))


def _world_event_matches_action(event_key: str, action_type: str) -> bool:
    template = _world_event_template(event_key)
    focus_actions = tuple(str(item) for item in template.get("focus_actions", ()))
    return action_type in focus_actions


def _world_event_contribution_amount(
    player: Player,
    action_type: str,
    *,
    success: bool = True,
    quantity: int = 1,
) -> int:
    base_map = {
        "adventure": 2,
        "encounter": 2,
        "alchemy": 2 if success else 1,
        "insight": 2,
        "meditation_insight": 2,
        "meditation_breakthrough": 2,
        "duel": 2,
        "breakthrough": 2 if success else 1,
    }
    contribution = base_map.get(action_type, 1)
    contribution += min(2, player.rebirth_count // 2)
    if action_type == "alchemy" and quantity >= 2:
        contribution += 1
    if action_type == "breakthrough" and success:
        contribution += 1
    return max(1, contribution)


async def _world_event_reward_summary(
    repo: GameRepository,
    event: dict[str, Any],
) -> str:
    parts: list[str] = []
    if int(event["reward_spirit_stones"]) > 0:
        parts.append(f"灵石 {int(event['reward_spirit_stones'])}")
    if int(event["reward_cultivation"]) > 0:
        parts.append(f"修为 {int(event['reward_cultivation'])}")
    if int(event["reward_insight"]) > 0:
        parts.append(f"道悟 {int(event['reward_insight'])}")
    reward_item_id = event.get("reward_item_id")
    reward_item_quantity = int(event.get("reward_item_quantity", 0))
    if reward_item_id is not None and reward_item_quantity > 0:
        item = await repo.get_item_by_id(str(reward_item_id))
        item_name = str(reward_item_id) if item is None else str(item["name"])
        parts.append(f"{item_name} x{reward_item_quantity}")
    return " / ".join(parts) if parts else "暂无奖励"


async def _record_world_event_progress(
    player: Player,
    action_type: str,
    *,
    success: bool = True,
    quantity: int = 1,
) -> str | None:
    repo = get_repository()
    event = await _get_today_world_event()
    event_key = str(event["event_key"])
    if not _world_event_matches_action(event_key, action_type):
        return None
    contribution = _world_event_contribution_amount(
        player,
        action_type,
        success=success,
        quantity=quantity,
    )
    progress = await repo.contribute_world_event(
        event_date=_today().isoformat(),
        user_id=player.user_id,
        contribution=contribution,
    )
    if progress is None:
        return None
    notice = (
        f"世界事件《{event['title']}》推进 +{contribution}，"
        f"当前 {int(progress['current_progress'])}/{int(progress['target_progress'])}。"
    )
    if bool(progress["completed"]):
        notice += " 今日事件已完成，可发送“领取事件”结算。"
    return notice


async def _load_methods(repo: GameRepository, player: Player) -> list[dict[str, object]]:
    raw_methods = await repo.get_player_methods(player.user_id)
    return [_enrich_method(player, method) for method in raw_methods]


async def _grant_new_sect_methods(
    repo: GameRepository,
    player: Player,
    target_realm: Realm,
) -> list[str]:
    if player.sect_id is None:
        return []
    owned = set(player.method_ids)
    granted: list[str] = []
    sect_methods = await repo.get_sect_methods(player.sect_id, player.rebirth_count)
    for method in sect_methods:
        method_id = str(method["id"])
        required_realm = Realm(str(method["realm_requirement"]))
        if method_id in owned:
            continue
        if realm_index(required_realm) > realm_index(target_realm):
            continue
        if await repo.grant_player_method(player.user_id, method_id):
            granted.append(str(method["name"]))
            owned.add(method_id)
    return granted


def _parse_meditation_mode(mode: str | MeditationMode | None) -> MeditationMode:
    if mode is None:
        return MeditationMode.BREATH
    if isinstance(mode, MeditationMode):
        return mode
    text = mode.strip()
    alias_map = {
        "吐纳": MeditationMode.BREATH,
        "闭关": MeditationMode.BREATH,
        "凝练": MeditationMode.CONDENSE,
        "稳固": MeditationMode.CONDENSE,
        "参玄": MeditationMode.INSIGHT,
        "参悟": MeditationMode.INSIGHT,
        "冲关": MeditationMode.BREAKTHROUGH,
        "破境": MeditationMode.BREAKTHROUGH,
    }
    result = alias_map.get(text)
    if result is None:
        raise GameError("invalid_meditation_mode")
    return result


async def create_player_if_missing(user_id: str, nickname: str) -> tuple[Player, bool]:
    repo = get_repository()
    existing = await repo.get_player(user_id)
    if existing is not None:
        return existing, False

    profile = _generate_root_profile()
    root_type = profile["root_type"]
    root_trait = profile["root_trait"]
    comprehension = random.randint(8, 14) + _root_rank(root_type) + int(
        trait_insight_bonus(root_trait) * 20  # type: ignore[arg-type]
    )
    if profile["root_temperament"] == RootTemperament.ENLIGHTENED:
        comprehension += 2
    if profile["root_temperament"] == RootTemperament.TRANQUIL:
        comprehension += 1
    fortune = random.randint(5, 15)
    if root_trait == RootTrait.WANDERING:
        fortune += 3
    elif root_trait == RootTrait.EMBER:
        fortune += 2
    destiny = _generate_destiny_profile(0, 0)

    player = Player(
        user_id=user_id,
        nickname=nickname,
        root_type=root_type,  # type: ignore[arg-type]
        root_affinity=profile["root_affinity"],  # type: ignore[arg-type]
        root_purity=profile["root_purity"],  # type: ignore[arg-type]
        root_temperament=profile["root_temperament"],  # type: ignore[arg-type]
        root_trait=root_trait,  # type: ignore[arg-type]
        lifespan=_lifespan_for_profile(root_type, root_trait),  # type: ignore[arg-type]
        spirit_stones=300,
        fortune=fortune,
        comprehension=comprehension,
        stamina=100,
        destiny_type=destiny["destiny_type"],  # type: ignore[arg-type]
        destiny_level=destiny["destiny_level"],  # type: ignore[arg-type]
    )
    created = await repo.create_player_with_starter_items(
        player,
        [
            ("qigather", 2),
            ("spirit-herb", 3),
            ("clear-dew", 2),
        ],
    )
    latest = await repo.get_player(user_id)
    if latest is not None:
        return latest, created
    return player, created


async def get_player_status(user_id: str) -> Player | None:
    return await get_repository().get_player(user_id)


async def get_destiny_status(user_id: str) -> DestinyResult:
    player = await get_repository().get_player(user_id)
    if player is None:
        raise GameError("player_not_found")
    return _destiny_result(player)


async def get_today_world_state() -> WorldStateResult:
    return await _get_today_world_state()


async def get_today_world_event(user_id: str | None = None) -> WorldEventResult:
    repo = get_repository()
    event = await _get_today_world_event()
    player = None if user_id is None else await repo.get_player(user_id)
    contribution = 0
    claimed = False
    if player is not None:
        row = await repo.get_world_event_contribution(_today().isoformat(), user_id)
        if row is not None:
            contribution = int(row["contribution"])
            claimed = int(row["claimed"]) == 1
    return WorldEventResult(
        event_date=_today().isoformat(),
        title=str(event["title"]),
        description=str(event["description"]),
        objective=str(event["objective"]),
        current_progress=int(event["current_progress"]),
        target_progress=int(event["target_progress"]),
        completed=bool(event.get("completed_at")),
        bonus_text=str(event["bonus_text"]),
        participation_hint=str(event["participation_hint"]),
        reward_summary=await _world_event_reward_summary(repo, event),
        player_contribution=contribution,
        claimed=claimed,
    )


async def claim_today_world_event_reward(user_id: str) -> WorldEventClaimResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")
    event_date = _today().isoformat()
    claimed = await repo.claim_world_event_reward(event_date=event_date, user_id=user_id)
    if claimed is None:
        raise GameError("world_event_not_completed")
    reason = claimed.get("reason")
    if reason is not None:
        raise GameError(str(reason))

    reward_item_name: str | None = None
    reward_item_id = claimed.get("reward_item_id")
    reward_item_quantity = int(claimed.get("reward_item_quantity", 0))
    if reward_item_id is not None and reward_item_quantity > 0:
        item = await repo.get_item_by_id(str(reward_item_id))
        reward_item_name = str(reward_item_id) if item is None else str(item["name"])

    return WorldEventClaimResult(
        title=str(claimed["title"]),
        contribution=int(claimed["contribution"]),
        reward_spirit_stones=int(claimed["reward_spirit_stones"]),
        reward_cultivation=int(claimed["reward_cultivation"]),
        reward_insight=int(claimed["reward_insight"]),
        reward_item_name=reward_item_name,
        reward_item_quantity=reward_item_quantity,
    )


async def list_sects_for_player(user_id: str) -> list[dict[str, object]]:
    repo = get_repository()
    player = await repo.get_player(user_id)
    rebirth_count = 0 if player is None else player.rebirth_count
    return await repo.list_accessible_sects(rebirth_count)


async def get_player_methods(user_id: str) -> list[dict[str, object]]:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        return []
    return await _load_methods(repo, player)


async def list_inventory(user_id: str) -> list[dict[str, object]]:
    return await get_repository().list_inventory(user_id)


async def sign_in(user_id: str) -> SignInResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")

    sign_date = _today().isoformat()
    world_state = await _get_today_world_state()
    settings = get_settings()
    base_reward = random.randint(
        settings.sign_in_base_min + player.fortune + _destiny_fortune_bonus(player),
        settings.sign_in_base_max + player.fortune + _destiny_fortune_bonus(player),
    )
    cultivation_gain = random.randint(
        settings.sign_in_cultivation_min + player.comprehension,
        settings.sign_in_cultivation_max + player.comprehension,
    )
    fortune_roll = min(
        100,
        random.randint(1, 100) + world_state.fortune_bonus + _destiny_fortune_bonus(player),
    )
    pool_reward = await repo.claim_signin(
        user_id,
        sign_date,
        base_reward=base_reward,
        cultivation_gain=cultivation_gain,
        fortune_roll=fortune_roll,
        pool_release_rate=settings.daily_pool_release_rate,
        stamina_delta=12,
    )
    if pool_reward is None:
        raise GameError("already_signed")

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
        await repo.set_primary_method(user_id, str(starter["id"]))

    return JoinSectResult(sect_name=str(sect["name"]), method_name=granted_method_name)


async def set_primary_method(user_id: str, method_name: str) -> PrimaryMethodResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")
    method = await repo.get_player_method_by_name(user_id, method_name)
    if method is None:
        raise GameError("method_not_found")
    await repo.set_primary_method(user_id, str(method["id"]))
    player = await repo.get_player(user_id)
    assert player is not None
    player = _player_with_updates(player, primary_method_id=str(method["id"]))
    enriched = _enrich_method(player, dict(method))
    return PrimaryMethodResult(
        method_name=str(enriched["name"]),
        mastery_title=str(enriched["mastery_title"]),
        practice_bonus_percent=int(float(enriched["practice_total"]) * 100),
        breakthrough_bonus_percent=int(enriched["breakthrough_total"]),
        insight_bonus_percent=int(float(enriched["insight_total"]) * 100),
    )


async def adventure(user_id: str) -> AdventureResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")

    settings = get_settings()
    if player.stamina < settings.adventure_stamina_cost:
        raise GameError("not_enough_stamina")

    methods = await _load_methods(repo, player)
    world_state = await _get_today_world_state()
    world_event = await _get_today_world_event()
    event_bonus_values = _world_event_bonus_values(str(world_event["event_key"]))
    primary_method = _primary_method(player, methods)
    roll_value = (
        random.randint(1, 100)
        + _root_adventure_total(player)
        + (player.fortune + _destiny_fortune_bonus(player)) // 12
        + world_state.adventure_bonus // 3
        + min(8, player.rebirth_count * 2)
        + (0 if primary_method is None else int(primary_method.get("adventure_bonus", 0)))
    )

    cultivation_gain = 0
    spirit_stones_gain = 0
    stamina_delta = -settings.adventure_stamina_cost
    item_id: str | None = None
    item_name: str | None = None
    insight_delta = 0
    message: str

    if roll_value <= 18:
        cultivation_gain = -max(18, int(max(player.cultivation, 120) * 0.04))
        spirit_stones_gain = random.randint(8, 24)
        message = "历练途中误入凶地，虽侥幸脱身，但心神受损。"
    elif roll_value <= 54:
        cultivation_gain = random.randint(90, 150)
        spirit_stones_gain = random.randint(40, 90)
        message = "你在山野间搜寻机缘，收获了一批灵石与修为。"
    elif roll_value <= 88:
        cultivation_gain = random.randint(150, 240)
        spirit_stones_gain = random.randint(80, 150)
        insight_delta = 1 if random.random() < 0.35 else 0
        message = "你在历练中斩获颇丰，灵气流转颇为顺畅。"
        if random.random() < 0.35:
            item_id = _root_loot_choice(player, ("spirit-herb", "clear-dew"))
    elif roll_value <= 103:
        cultivation_gain = random.randint(200, 340)
        spirit_stones_gain = random.randint(130, 240)
        insight_delta = random.randint(1, 3)
        message = "你撞上了一次大机缘，洞府残痕中留有前人遗泽。"
        luck_draw = random.random()
        if luck_draw < 0.18:
            item_id = "rebirth-mark"
        elif luck_draw < 0.52:
            item_id = "method-fragment"
        elif luck_draw < 0.76:
            item_id = "longevity-fruit"
        elif luck_draw < 0.90:
            item_id = _root_loot_choice(player, ("flame-sand", "moon-dust"))
        else:
            item_id = "qigather"
    else:
        cultivation_gain = random.randint(260, 430)
        spirit_stones_gain = random.randint(180, 300)
        insight_delta = random.randint(2, 4)
        if player.rebirth_count >= 1:
            message = "你闯入了一处轮回者才可感知的遗迹夹层，古老气息扑面而来。"
        else:
            message = "你仰见星芒坠落，顺着灵机追索而去，竟得一桩超常机缘。"
        item_id = "method-fragment" if player.rebirth_count < 2 else _root_loot_choice(
            player,
            ("method-fragment", "longevity-fruit", "rebirth-mark", "marrow-jade"),
        )

    reward_multiplier = _lifespan_reward_multiplier(player)
    if cultivation_gain > 0:
        cultivation_gain = int(cultivation_gain * reward_multiplier)
        cultivation_gain = int(
            cultivation_gain * (1 + _training_multiplier(player, primary_method))
        )
        cultivation_gain += int(cultivation_gain * float(event_bonus_values.get("adventure_cultivation", 0.0)))
    if spirit_stones_gain > 0:
        spirit_stones_gain = int(spirit_stones_gain * reward_multiplier)
        spirit_stones_gain += int(spirit_stones_gain * float(event_bonus_values.get("adventure_spirit", 0.0)))

    if insight_delta > 0:
        insight_delta = max(
            1,
            int(insight_delta * (1 + _insight_multiplier(player, primary_method) / 2)),
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
        insight_delta=insight_delta,
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
    event_notice = await _record_world_event_progress(player, "adventure")

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
        insight_delta=insight_delta,
        lifespan_notice=lifespan_notice,
        event_notice=event_notice,
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
    methods = await _load_methods(repo, player)
    primary_method = _primary_method(player, methods)
    world_state = await _get_today_world_state()
    world_event = await _get_today_world_event()
    event_bonus_values = _world_event_bonus_values(str(world_event["event_key"]))
    roll_value = (
        random.randint(1, 100)
        + (player.fortune + _destiny_fortune_bonus(player)) // 8
        + world_state.encounter_bonus
        + min(12, player.rebirth_count * 3)
        + max(0, _root_adventure_total(player) // 2)
    )

    cultivation_gain = 0
    spirit_stones_gain = 0
    fortune_delta = 0
    stamina_delta = -stamina_cost
    item_id: str | None = None
    item_name: str | None = None
    insight_delta = 0
    message: str

    if roll_value <= 15:
        cultivation_gain = -max(20, int(max(player.cultivation, 120) * 0.05))
        spirit_stones_gain = random.randint(0, 20)
        message = "你误触残阵，幻象缠身，险些在奇遇中折损根基。"
    elif roll_value <= 48:
        cultivation_gain = random.randint(70, 130)
        spirit_stones_gain = random.randint(25, 55)
        fortune_delta = 1
        insight_delta = 1
        message = "你在偏僻石壁后发现一缕灵脉余温，虽不惊艳，却也受益匪浅。"
    elif roll_value <= 82:
        cultivation_gain = random.randint(110, 190)
        spirit_stones_gain = random.randint(60, 110)
        fortune_delta = 1
        insight_delta = random.randint(1, 2)
        item_id = random.choice(["qigather", "spirit-herb", "clear-dew"])
        message = "你撞见了一场恰到好处的机缘，灵材与感悟一并入手。"
    elif roll_value <= 100:
        cultivation_gain = random.randint(170, 280)
        spirit_stones_gain = random.randint(90, 170)
        fortune_delta = 2
        insight_delta = random.randint(2, 4)
        if player.rebirth_count >= 1:
            item_id = random.choice(["method-fragment", "longevity-fruit", "moon-dust"])
            message = "你在轮回残响中看见古修遗刻，心神一震，收获远超寻常。"
        else:
            item_id = random.choice(["method-fragment", "qigather", "flame-sand"])
            message = "你偶得一段前人传音，字句不多，却足够你在仙途上再进一步。"
    else:
        cultivation_gain = random.randint(240, 380)
        spirit_stones_gain = random.randint(150, 260)
        fortune_delta = 3
        insight_delta = random.randint(3, 6)
        if player.rebirth_count >= 2:
            item_id = random.choice(["rebirth-mark", "longevity-fruit", "method-fragment", "marrow-jade"])
            message = "虚市裂缝在你面前一闪而过，你从中换得了一件极罕见的东西。"
        else:
            item_id = random.choice(["longevity-fruit", "method-fragment", "moon-dust"])
            message = "天穹星辉忽然倾泻，你在片刻失神后，竟捧回了一桩大机缘。"

    reward_multiplier = _lifespan_reward_multiplier(player)
    if cultivation_gain > 0:
        cultivation_gain = int(cultivation_gain * reward_multiplier)
        cultivation_gain = int(
            cultivation_gain * (1 + _training_multiplier(player, primary_method))
        )
    if spirit_stones_gain > 0:
        spirit_stones_gain = int(spirit_stones_gain * reward_multiplier)
    if insight_delta > 0:
        insight_delta = max(
            1,
            int(insight_delta * (1 + _insight_multiplier(player, primary_method))),
        )
    fortune_delta += int(event_bonus_values.get("encounter_fortune", 0))
    insight_delta += int(event_bonus_values.get("encounter_insight", 0))

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
        insight_delta=insight_delta,
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
    event_notice = await _record_world_event_progress(player, "encounter")

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
        insight_delta=insight_delta,
        lifespan_notice=lifespan_notice,
        event_notice=event_notice,
    )


async def start_meditation(
    user_id: str,
    minutes: int | None = None,
    mode: str | MeditationMode | None = None,
) -> MeditationResult:
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

    meditation_mode = _parse_meditation_mode(mode)
    methods = await _load_methods(repo, player)
    primary_method = _primary_method(player, methods)
    world_state = await _get_today_world_state()
    world_event = await _get_today_world_event()
    event_bonus_values = _world_event_bonus_values(str(world_event["event_key"]))

    base_reward = minutes * (6 + player.comprehension / 4 + player.insight / 20)
    reward = int(
        base_reward
        * (
            1
            + _training_multiplier(player, primary_method)
            + world_state.meditation_bonus
        )
        * meditation_mode_reward_multiplier(meditation_mode)
        * _lifespan_reward_multiplier(player)
    )

    insight_reward = 0
    breakthrough_reward = 0
    insight_factor = _insight_multiplier(player, primary_method)
    breakthrough_factor = _root_breakthrough_total(player) + (
        0 if primary_method is None else int(primary_method.get("breakthrough_total", 0))
    )
    affinity_bias = _meditation_affinity_bias(player, meditation_mode)
    reward = int(reward * (1 + float(affinity_bias["reward"])))

    if meditation_mode == MeditationMode.BREATH:
        insight_reward = max(0, minutes // 90)
        breakthrough_reward = max(0, minutes // 120)
    elif meditation_mode == MeditationMode.CONDENSE:
        insight_reward = max(1, int(minutes / 45 * (1 + insight_factor)))
        breakthrough_reward = max(4, int(minutes / 12 * (1 + breakthrough_factor / 60)))
    elif meditation_mode == MeditationMode.INSIGHT:
        insight_reward = max(2, int(minutes / 10 * (1 + insight_factor)))
        breakthrough_reward = max(1, int(minutes / 70 * (1 + breakthrough_factor / 100)))
    elif meditation_mode == MeditationMode.BREAKTHROUGH:
        insight_reward = max(1, int(minutes / 30 * (1 + insight_factor / 2)))
        breakthrough_reward = max(8, int(minutes / 8 * (1 + breakthrough_factor / 55)))

    insight_reward += max(0, int(meditation_mode_insight_bonus(meditation_mode) * 10))
    breakthrough_reward += meditation_mode_breakthrough_bonus(meditation_mode) // 3
    if meditation_mode == MeditationMode.INSIGHT:
        insight_reward += int(event_bonus_values.get("meditation_insight", 0))
    if meditation_mode == MeditationMode.BREAKTHROUGH:
        breakthrough_reward += int(
            breakthrough_reward * float(event_bonus_values.get("meditation_breakthrough_multiplier", 0.0))
        )
    insight_reward += int(affinity_bias["insight"])
    breakthrough_reward += int(affinity_bias["breakthrough"])

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
        mode=meditation_mode,
        insight_reward=insight_reward,
        breakthrough_reward=breakthrough_reward,
    )
    return MeditationResult(
        minutes=minutes,
        reward=max(10, reward),
        until=until.strftime("%H:%M"),
        world_title=world_state.title,
        method_name=None if primary_method is None else str(primary_method["name"]),
        mode_name=meditation_mode.value,
        insight_reward=insight_reward,
        breakthrough_reward=breakthrough_reward,
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
            methods = await _load_methods(repo, player)
            current_method = next(
                (method for method in methods if str(method["id"]) == player.meditation_method_id),
                None,
            )
            method_name = None if current_method is None else str(current_method["name"])
        return MeditationClaimResult(
            reward=player.meditation_reward,
            minutes=player.meditation_minutes,
            still_waiting=True,
            method_name=method_name,
            remaining_minutes=max(1, remaining),
            mode_name=None if player.meditation_mode is None else player.meditation_mode.value,
        )

    methods = await _load_methods(repo, player)
    method = next(
        (method for method in methods if str(method["id"]) == player.meditation_method_id),
        None,
    )
    mode = player.meditation_mode or MeditationMode.BREATH
    mastery_gain = get_settings().method_mastery_meditation_gain + max(
        0,
        player.meditation_minutes // 60 - 1,
    )
    if mode == MeditationMode.INSIGHT:
        mastery_gain += 2
    elif mode == MeditationMode.CONDENSE:
        mastery_gain += 1
    elif mode == MeditationMode.BREAKTHROUGH:
        mastery_gain += 1
    method_name, applied_mastery = await _apply_method_mastery(repo, user_id, method, mastery_gain)
    await repo.update_player_stats(
        user_id,
        cultivation_delta=player.meditation_reward,
        insight_delta=player.meditation_insight_reward,
        breakthrough_ready_delta=player.meditation_breakthrough_reward,
    )
    await repo.clear_player_meditation(user_id)

    world_state = await _get_today_world_state()
    refreshed_player = await repo.get_player(user_id)
    assert refreshed_player is not None
    _, lifespan_notice = await _apply_lifespan_progress(
        repo,
        refreshed_player,
        _meditation_age_progress(player, player.meditation_minutes, world_state, mode),
    )
    event_notice = await _record_world_event_progress(
        refreshed_player,
        "meditation_breakthrough" if mode == MeditationMode.BREAKTHROUGH else (
            "meditation_insight" if mode == MeditationMode.INSIGHT else ""
        ),
    ) if mode in {MeditationMode.BREAKTHROUGH, MeditationMode.INSIGHT} else None

    return MeditationClaimResult(
        reward=player.meditation_reward,
        minutes=player.meditation_minutes,
        still_waiting=False,
        method_name=method_name,
        mastery_gain=applied_mastery,
        lifespan_notice=lifespan_notice,
        mode_name=mode.value,
        insight_gain=player.meditation_insight_reward,
        breakthrough_ready_gain=player.meditation_breakthrough_reward,
        event_notice=event_notice,
    )


async def breakthrough(user_id: str) -> BreakthroughResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")

    methods = await _load_methods(repo, player)
    primary_method = _primary_method(player, methods)
    world_state = await _get_today_world_state()
    world_event = await _get_today_world_event()
    event_bonus_values = _world_event_bonus_values(str(world_event["event_key"]))
    event_failure_guard = int(event_bonus_values.get("breakthrough_guard", 0))
    target = next_realm(player.realm)
    realm_cap = _effective_max_realm(player)

    if target is None or realm_index(target) > realm_index(realm_cap):
        if player.realm != realm_cap:
            raise GameError("realm_maxed")
        if player.realm != Realm.SPIRIT_4:
            raise GameError("realm_maxed")
        if player.cultivation < realm_requirement(player.realm):
            raise GameError("not_enough_cultivation")
        if player.breakthrough_ready < 24:
            raise GameError("not_enough_preparation")

        failure_guard = _destiny_failure_guard(player) + event_failure_guard
        chance = 65
        chance += player.fortune // 8
        chance += world_state.fortune_bonus
        chance += _root_breakthrough_total(player) // 2
        chance += 0 if primary_method is None else int(primary_method.get("breakthrough_total", 0)) // 3
        chance += min(8, player.insight // 4)
        chance += min(12, player.breakthrough_ready // 5)
        chance += failure_guard
        chance += int(event_bonus_values.get("breakthrough_chance", 0))
        chance -= _lifespan_breakthrough_penalty(player)
        chance = max(18, min(chance, 98))

        roll_value = random.randint(1, 100)
        preparation_cost = min(player.breakthrough_ready, 18)
        insight_cost = min(player.insight, 5)
        soul_mark_gained = roll_value <= chance

        if soul_mark_gained:
            await repo.update_player_stats(
                user_id,
                soul_marks_delta=1,
                breakthrough_ready_delta=-preparation_cost,
                insight_delta=-insight_cost,
            )
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
                preparation_cost=preparation_cost,
                event_notice=await _record_world_event_progress(player, "breakthrough", success=True),
            )

        penalty_rate = max(
            0.08,
            get_settings().breakthrough_fail_penalty_rate - failure_guard * 0.01,
        )
        penalty = -max(20, int(player.cultivation * penalty_rate))
        await repo.update_player_stats(
            user_id,
            cultivation_delta=penalty,
            breakthrough_ready_delta=-preparation_cost,
            insight_delta=-min(player.insight, max(0, 2 - failure_guard // 6)),
        )
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
            preparation_cost=preparation_cost,
            event_notice=await _record_world_event_progress(player, "breakthrough", success=False),
        )

    required = realm_requirement(target)
    if player.cultivation < required:
        raise GameError("not_enough_cultivation")

    major = _major_breakthrough(player.realm, target)
    preparation_needed = 18 if major else 0
    if player.breakthrough_ready < preparation_needed:
        raise GameError("not_enough_preparation")

    failure_guard = _destiny_failure_guard(player) + event_failure_guard
    chance = breakthrough_base_chance(player.realm)
    chance += _root_breakthrough_total(player)
    chance += min(12, player.fortune // 10)
    chance += min(10, player.comprehension // 3)
    chance += min(8, player.insight // 4)
    chance += min(14, player.breakthrough_ready // 5)
    chance += world_state.fortune_bonus
    chance += 0 if primary_method is None else int(primary_method.get("breakthrough_total", 0))
    chance += failure_guard
    chance += int(event_bonus_values.get("breakthrough_chance", 0))
    chance -= _lifespan_breakthrough_penalty(player)
    if major:
        chance -= 6
    chance = max(18, min(chance, 98))

    roll_value = random.randint(1, 100)
    preparation_cost = min(player.breakthrough_ready, 12 if major else 8)
    insight_cost = min(player.insight, 3 if major else 2)
    if roll_value <= chance:
        await repo.update_player_stats(
            user_id,
            realm=target,
            breakthrough_ready_delta=-preparation_cost,
            insight_delta=-insight_cost,
        )
        unlocked_methods = await _grant_new_sect_methods(repo, player, target)
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
            unlocked_methods=unlocked_methods,
            preparation_cost=preparation_cost,
            event_notice=await _record_world_event_progress(player, "breakthrough", success=True),
        )

    penalty_rate = get_settings().breakthrough_fail_penalty_rate * (1.2 if major else 1.0)
    penalty = -max(
        18 if not major else 24,
        int(required * penalty_rate) - failure_guard * 18,
    )
    await repo.update_player_stats(
        user_id,
        cultivation_delta=penalty,
        breakthrough_ready_delta=-preparation_cost,
        insight_delta=-min(player.insight, max(0, (1 if major else 0) - failure_guard // 8)),
    )
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
        preparation_cost=preparation_cost,
        event_notice=await _record_world_event_progress(player, "breakthrough", success=False),
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
    if item_id not in {
        "qigather",
        "restore-powder",
        "longevity-fruit",
        "essence-pill",
        "insight-pill",
        "marrow-pill",
    }:
        raise GameError("item_not_consumable")
    if not await repo.remove_inventory_item(user_id, item_id, 1):
        raise GameError("not_enough_items")

    if item_id == "qigather":
        cultivation_delta = random.randint(120, 190) + player.comprehension * 3
        cultivation_delta = int(cultivation_delta * (1 + _root_training_bonus(player) / 2))
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
    if item_id == "essence-pill":
        breakthrough_delta = random.randint(8, 14) + max(0, player.comprehension // 6)
        cultivation_delta = random.randint(70, 120)
        await repo.update_player_stats(
            user_id,
            cultivation_delta=cultivation_delta,
            breakthrough_ready_delta=breakthrough_delta,
        )
        return ConsumeItemResult(
            item_name=str(item["name"]),
            message=f"丹气沉入气海，你的冲关底蕴提升了 {breakthrough_delta} 点。",
            cultivation_delta=cultivation_delta,
        )
    if item_id == "insight-pill":
        insight_delta = random.randint(3, 6) + max(0, player.comprehension // 8)
        cultivation_delta = random.randint(40, 90)
        await repo.update_player_stats(
            user_id,
            cultivation_delta=cultivation_delta,
            insight_delta=insight_delta,
        )
        return ConsumeItemResult(
            item_name=str(item["name"]),
            message=f"灵台一清，你的道悟增长了 {insight_delta} 点。",
            cultivation_delta=cultivation_delta,
        )
    if item_id == "marrow-pill":
        if player.rebirth_count <= 0:
            await repo.add_inventory_item(user_id, item_id, 1)
            raise GameError("rebirth_required")
        updated_fields: dict[str, object] = {}
        message_parts = ["药力贯通百脉，你的根骨被重新洗练。"]
        purity_gain = random.randint(2, 6)
        new_purity = min(99, player.root_purity + purity_gain)
        updated_fields["root_purity"] = new_purity
        message_parts.append(f"纯度 +{new_purity - player.root_purity}")
        if random.random() < 0.55:
            temperament = _weighted_choice(ROOT_TEMPERAMENT_ROLLS)
            updated_fields["root_temperament"] = temperament
            message_parts.append(f"性情转为 {temperament.value}")
        if random.random() < min(0.75, 0.35 + player.rebirth_count * 0.12):
            trait = _roll_root_trait(player.rebirth_count + 1)
            updated_fields["root_trait"] = trait
            message_parts.append(f"特质显化为 {trait.value}")
        if random.random() < min(0.42, 0.16 + player.rebirth_count * 0.08):
            affinity = _roll_root_affinity(player.rebirth_count + 1)
            updated_fields["root_affinity"] = affinity
            message_parts.append(f"主属性偏转为 {affinity.value}")
        await repo.update_player_stats(user_id, **updated_fields)
        return ConsumeItemResult(
            item_name=str(item["name"]),
            message="，".join(message_parts),
        )
    raise GameError("item_not_consumable")


async def craft_elixir(user_id: str, recipe_name: str) -> AlchemyResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")

    recipe = _find_alchemy_recipe(recipe_name)
    if recipe is None:
        raise GameError("recipe_not_found")
    if player.rebirth_count < int(recipe["required_rebirth_count"]):
        raise GameError("recipe_locked")

    methods = await _load_methods(repo, player)
    primary_method = _primary_method(player, methods)
    materials = tuple(recipe["materials"])
    if any(player.inventory.get(str(item_id), 0) < int(quantity) for item_id, _, quantity in materials):
        raise GameError("not_enough_materials")

    removed = await repo.consume_inventory_items(
        user_id,
        [(str(item_id), int(quantity)) for item_id, _, quantity in materials],
    )
    if not removed:
        raise GameError("not_enough_materials")

    world_state = await _get_today_world_state()
    world_event = await _get_today_world_event()
    event_bonus_values = _world_event_bonus_values(str(world_event["event_key"]))
    chance = int(recipe["base_chance"])
    chance += min(12, player.comprehension // 2)
    chance += min(8, player.insight // 6)
    chance += min(6, player.rebirth_count * 2)
    alchemy_bonus = _destiny_alchemy_bonus(player)
    chance += alchemy_bonus
    chance += int(event_bonus_values.get("alchemy_chance", 0))
    affinity_bias = _alchemy_affinity_bias(player, recipe, primary_method)
    chance += int(affinity_bias["chance"])
    if primary_method is not None:
        chance += min(8, int(float(primary_method.get("insight_total", 0.0)) * 100 // 4))
        chance += min(6, int(primary_method.get("mastery", 0)) // 40)
        if MethodStyle(str(primary_method["style"])) in tuple(recipe["favored_styles"]):
            chance += 4
    if player.root_affinity in tuple(recipe["favored_affinities"]):
        chance += 5
    if player.root_temperament == RootTemperament.TRANQUIL:
        chance += 3
    if player.root_temperament == RootTemperament.ENLIGHTENED:
        chance += 4
    if player.root_trait == RootTrait.INSIGHTFUL:
        chance += 4
    if world_state.title == "星辉潮":
        chance += 5
    elif world_state.title == "流火天":
        chance += 3
    chance = max(35, min(chance, 97))

    roll_value = random.randint(1, 100)
    item_id = str(recipe["item_id"])
    item = await repo.get_item_by_id(item_id)
    assert item is not None

    if roll_value <= chance:
        quantity = 1
        insight_gain = 0
        double_threshold = max(8, chance // 6) + int(affinity_bias["double"]) * 2
        if player.destiny_type == DestinyType.ALCHEMY:
            double_threshold += max(1, player.destiny_level // 2)
        elif player.destiny_type == DestinyType.WISDOM:
            double_threshold += 1
        if roll_value <= min(24, double_threshold):
            quantity = 2
            insight_gain = 1 + int(event_bonus_values.get("alchemy_insight", 0))
            insight_gain += int(affinity_bias["insight"])
        await repo.add_inventory_item(user_id, item_id, quantity)
        if insight_gain:
            await repo.update_player_stats(user_id, insight_delta=insight_gain)
        event_notice = await _record_world_event_progress(player, "alchemy", success=True, quantity=quantity)
        return AlchemyResult(
            item_name=str(item["name"]),
            roll_value=roll_value,
            chance_percent=chance,
            success=True,
            quantity=quantity,
            world_title=world_state.title,
            message="丹炉一震，丹香四散，这一炉炼成了。",
            insight_gain=insight_gain,
            event_notice=event_notice,
        )

    byproduct_quantity = 1 if roll_value <= chance + 18 else 2
    await repo.add_inventory_item(user_id, "pill-dregs", byproduct_quantity)
    event_notice = await _record_world_event_progress(player, "alchemy", success=False)
    return AlchemyResult(
        item_name=str(item["name"]),
        roll_value=roll_value,
        chance_percent=chance,
        success=False,
        quantity=0,
        world_title=world_state.title,
        message="火候失衡，药性散乱，这一炉化作了丹渣。",
        byproduct_name="丹渣",
        byproduct_quantity=byproduct_quantity,
        event_notice=event_notice,
    )


async def duel(user_id: str, target: str) -> DuelResult:
    repo = get_repository()
    attacker = await repo.get_player(user_id)
    if attacker is None:
        raise GameError("player_not_found")
    defender = await _resolve_player_target(target)
    if defender is None:
        raise GameError("target_not_found")
    if defender.user_id == attacker.user_id:
        raise GameError("cannot_duel_self")

    stamina_cost = get_settings().duel_stamina_cost
    if attacker.stamina < stamina_cost or defender.stamina < stamina_cost:
        raise GameError("not_enough_stamina")

    world_state = await _get_today_world_state()
    world_event = await _get_today_world_event()
    event_bonus_values = _world_event_bonus_values(str(world_event["event_key"]))
    attacker_methods = await _load_methods(repo, attacker)
    defender_methods = await _load_methods(repo, defender)
    attacker_primary = _primary_method(attacker, attacker_methods)
    defender_primary = _primary_method(defender, defender_methods)
    duel_rounds = _duel_rounds(attacker, attacker_primary, defender, defender_primary)

    attacker_roll = random.randint(1, 100) + world_state.adventure_bonus // 3
    defender_roll = random.randint(1, 100) + world_state.encounter_bonus // 3
    attacker_total = _duel_total(attacker, attacker_primary, attacker_roll)
    defender_total = _duel_total(defender, defender_primary, defender_roll)

    if attacker_total == defender_total:
        if attacker.fortune >= defender.fortune:
            attacker_total += 1
        else:
            defender_total += 1

    winner = attacker if attacker_total > defender_total else defender
    loser = defender if winner.user_id == attacker.user_id else attacker
    winner_method = attacker_primary if winner.user_id == attacker.user_id else defender_primary
    reward_spirit = random.randint(
        get_settings().duel_daily_reward_spirit_stones_min,
        get_settings().duel_daily_reward_spirit_stones_max,
    ) + max(0, _realm_power(loser) // 8) + int(event_bonus_values.get("duel_spirit", 0))
    reward_cultivation = 40 + max(0, abs(attacker_total - defender_total) // 2) + int(
        event_bonus_values.get("duel_cultivation", 0)
    )
    reward_insight = 1 if abs(attacker_total - defender_total) >= 18 else 0
    loser_cultivation_loss = -max(20, reward_cultivation // 2)

    if winner.user_id == attacker.user_id:
        await repo.update_player_stats(
            attacker.user_id,
            spirit_stones_delta=reward_spirit,
            cultivation_delta=reward_cultivation,
            insight_delta=reward_insight,
            stamina_delta=-stamina_cost,
        )
        await repo.update_player_stats(
            defender.user_id,
            cultivation_delta=loser_cultivation_loss,
            stamina_delta=-stamina_cost,
        )
    else:
        await repo.update_player_stats(
            defender.user_id,
            spirit_stones_delta=reward_spirit,
            cultivation_delta=reward_cultivation,
            insight_delta=reward_insight,
            stamina_delta=-stamina_cost,
        )
        await repo.update_player_stats(
            attacker.user_id,
            cultivation_delta=loser_cultivation_loss,
            stamina_delta=-stamina_cost,
        )

    mastery_gain = 2 + (1 if abs(attacker_total - defender_total) >= 22 else 0)
    await _apply_method_mastery(repo, winner.user_id, winner_method, mastery_gain)
    await repo.record_adventure(
        winner.user_id,
        action_type="duel",
        roll_value=max(attacker_roll, defender_roll),
        outcome=f"{winner.nickname}斗法胜过{loser.nickname}",
        reward_spirit_stones=reward_spirit,
        reward_cultivation=reward_cultivation,
        reward_item_id=None,
    )
    event_notice = await _record_world_event_progress(winner, "duel")

    return DuelResult(
        attacker_name=attacker.nickname,
        defender_name=defender.nickname,
        winner_name=winner.nickname,
        loser_name=loser.nickname,
        attacker_roll=attacker_roll,
        defender_roll=defender_roll,
        attacker_total=attacker_total,
        defender_total=defender_total,
        world_title=world_state.title,
        message="灵机交锋，胜负在一息之间见了分晓。",
        winner_spirit_stones_gain=reward_spirit,
        winner_cultivation_gain=reward_cultivation,
        winner_insight_gain=reward_insight,
        loser_cultivation_loss=loser_cultivation_loss,
        attacker_stamina_delta=-stamina_cost,
        defender_stamina_delta=-stamina_cost,
        rounds=duel_rounds,
        event_notice=event_notice,
    )


async def contemplate_method(user_id: str, method_name: str | None = None) -> MethodInsightResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")

    methods = await _load_methods(repo, player)
    if not methods:
        raise GameError("method_not_found")

    if not await repo.remove_inventory_item(user_id, "method-fragment", 1):
        raise GameError("not_enough_fragments")

    if method_name:
        raw_method = await repo.get_player_method_by_name(user_id, method_name)
        method = None if raw_method is None else _enrich_method(player, dict(raw_method))
    else:
        method = _primary_method(player, methods)
    if method is None:
        await repo.add_inventory_item(user_id, "method-fragment", 1)
        raise GameError("method_not_found")

    world_state = await _get_today_world_state()
    world_event = await _get_today_world_event()
    event_bonus_values = _world_event_bonus_values(str(world_event["event_key"]))
    insight_factor = _insight_multiplier(player, method)
    mastery_gain = (
        random.randint(10, 18)
        + player.comprehension // 5
        + player.rebirth_count * 2
        + max(0, world_state.encounter_bonus // 6)
        + int(insight_factor * 12)
    )
    if player.destiny_type == DestinyType.WISDOM:
        mastery_gain += 2 + player.destiny_level
    elif player.destiny_type == DestinyType.TURNFATE:
        mastery_gain += 1 + player.destiny_level // 2
    mastery_gain += int(event_bonus_values.get("contemplate_mastery", 0))
    cultivation_gain = 60 + mastery_gain * 4
    insight_gain = max(2, int(1 + mastery_gain / 8))
    breakthrough_gain = 0
    if MethodStyle(str(method["style"])) in {MethodStyle.REBIRTH, MethodStyle.SURGING}:
        breakthrough_gain = max(1, mastery_gain // 12)

    await repo.add_method_mastery(user_id, str(method["id"]), mastery_gain)
    await repo.update_player_stats(
        user_id,
        cultivation_delta=cultivation_gain,
        stamina_delta=-8,
        insight_delta=insight_gain,
        breakthrough_ready_delta=breakthrough_gain,
    )
    refreshed = await repo.get_player_method_by_name(user_id, str(method["name"]))
    assert refreshed is not None
    event_notice = await _record_world_event_progress(player, "insight")
    return MethodInsightResult(
        method_name=str(method["name"]),
        mastery_gain=mastery_gain,
        new_mastery=int(refreshed["mastery"]),
        cultivation_gain=cultivation_gain,
        world_title=world_state.title,
        insight_gain=insight_gain,
        breakthrough_ready_gain=breakthrough_gain,
        event_notice=event_notice,
    )


async def explore_ancient_trial(user_id: str) -> AncientTrialResult:
    repo = get_repository()
    player = await repo.get_player(user_id)
    if player is None:
        raise GameError("player_not_found")
    if player.rebirth_count < 2:
        raise GameError("ancient_trial_locked")
    if player.stamina < 18:
        raise GameError("not_enough_stamina")

    methods = await _load_methods(repo, player)
    primary_method = _primary_method(player, methods)
    world_state = await _get_today_world_state()

    chance = 42
    chance += min(12, player.rebirth_count * 3)
    chance += min(10, player.insight // 4)
    chance += min(8, player.comprehension // 3)
    chance += min(8, player.breakthrough_ready // 8)
    chance += _root_breakthrough_total(player) // 2
    chance += int(_insight_multiplier(player, primary_method) * 20)
    if primary_method is not None and MethodStyle(str(primary_method["style"])) == MethodStyle.REBIRTH:
        chance += 8
    if player.root_affinity in {Affinity.VOID, Affinity.THUNDER}:
        chance += 6
    chance += world_state.encounter_bonus // 2
    chance = max(28, min(chance, 94))

    roll_value = random.randint(1, 100)
    reward_spirit = 0
    reward_cultivation = 0
    reward_insight = 0
    reward_item_name: str | None = None

    if roll_value <= chance:
        reward_spirit = random.randint(90, 170) + player.rebirth_count * 20
        reward_cultivation = random.randint(180, 320)
        reward_cultivation = int(reward_cultivation * (1 + _training_multiplier(player, primary_method)))
        reward_insight = random.randint(2, 4) + max(1, player.rebirth_count - 1)
        item_id = _ancient_trial_item_id(player)
        item = await repo.get_item_by_id(item_id)
        if item is not None:
            reward_item_name = str(item["name"])
            await repo.add_inventory_item(user_id, item_id, 1)
        await repo.update_player_stats(
            user_id,
            spirit_stones_delta=reward_spirit,
            cultivation_delta=reward_cultivation,
            insight_delta=reward_insight,
            stamina_delta=-18,
        )
        message = "你在太虚古藏的残壁间稳住了神识，接住了一缕前尘回响。"
        return AncientTrialResult(
            trial_name="太虚古藏试炼",
            roll_value=roll_value,
            chance_percent=chance,
            success=True,
            reward_spirit_stones=reward_spirit,
            reward_cultivation=reward_cultivation,
            reward_insight=reward_insight,
            reward_item_name=reward_item_name,
            message=message,
        )

    cultivation_loss = -max(40, int(max(player.cultivation, 600) * 0.06))
    await repo.update_player_stats(
        user_id,
        cultivation_delta=cultivation_loss,
        stamina_delta=-18,
    )
    return AncientTrialResult(
        trial_name="太虚古藏试炼",
        roll_value=roll_value,
        chance_percent=chance,
        success=False,
        reward_spirit_stones=0,
        reward_cultivation=cultivation_loss,
        reward_insight=0,
        reward_item_name=None,
        message="古藏残响反噬心神，你强行退了出来，只留下一身余震。",
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
    listing_id = await repo.create_market_listing_from_inventory(
        user_id,
        str(item["id"]),
        quantity,
        unit_price,
    )
    if listing_id is None:
        raise GameError("not_enough_items")
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
    purchase = await repo.purchase_market_listing(
        user_id,
        listing_id,
        get_settings().market_fee_rate,
    )
    if purchase is None:
        raise GameError("listing_not_found")
    reason = purchase.get("reason")
    if reason is not None:
        raise GameError(str(reason))

    return MarketBuyResult(
        listing_id=int(purchase["listing_id"]),
        item_name=str(purchase["item_name"]),
        quantity=int(purchase["quantity"]),
        total_price=int(purchase["total_price"]),
        fee=int(purchase["fee"]),
        seller_name=str(purchase["seller_name"]),
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
    next_rebirth_count = player.rebirth_count + 1
    next_legacy_points = player.legacy_points + outcome.legacy_points_gained
    profile = _generate_root_profile(outcome.next_root_floor, player.rebirth_count + 1)
    destiny = _generate_destiny_profile(next_rebirth_count, next_legacy_points)
    new_lifespan = _lifespan_for_profile(
        profile["root_type"],  # type: ignore[arg-type]
        profile["root_trait"],  # type: ignore[arg-type]
    )
    update_fields: dict[str, object] = {
        "cultivation_delta": -player.cultivation,
        "legacy_points_delta": outcome.legacy_points_gained,
        "rebirth_count_delta": 1,
        "soul_marks_delta": -1,
        "lifespan_delta": new_lifespan - player.lifespan,
        "realm": Realm.QI_1,
        "root_type": profile["root_type"],  # type: ignore[dict-item]
        "root_affinity": profile["root_affinity"],  # type: ignore[dict-item]
        "root_purity": profile["root_purity"],  # type: ignore[dict-item]
        "root_temperament": profile["root_temperament"],  # type: ignore[dict-item]
        "root_trait": profile["root_trait"],  # type: ignore[dict-item]
        "insight_delta": -player.insight,
        "breakthrough_ready_delta": -player.breakthrough_ready,
        "destiny_level_delta": int(destiny["destiny_level"]) - player.destiny_level,
    }
    if destiny["destiny_type"] is not None:
        update_fields["destiny_type"] = destiny["destiny_type"]
    await repo.update_player_stats(
        user_id,
        **update_fields,
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
    refreshed = await repo.get_player(user_id)
    assert refreshed is not None
    destiny_result = _destiny_result(refreshed)
    return RebirthResult(
        legacy_points_gained=outcome.legacy_points_gained,
        unlocked_features=[unlock.value for unlock in outcome.unlocked_features],
        new_root_floor=outcome.next_root_floor.value,
        new_realm_cap=outcome.next_realm_cap.value,
        root_brief=_root_brief(refreshed),
        destiny_name=destiny_result.destiny_name,
        destiny_level=destiny_result.destiny_level,
    )
