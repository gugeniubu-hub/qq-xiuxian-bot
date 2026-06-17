from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional


class RootType(StrEnum):
    MORTAL = "凡灵根"
    YELLOW = "黄灵根"
    MYSTIC = "玄灵根"
    EARTH = "地灵根"
    HEAVEN = "天灵根"


class Realm(StrEnum):
    QI_1 = "炼气前期"
    QI_2 = "炼气中期"
    QI_3 = "炼气后期"
    QI_4 = "炼气圆满"
    FOUNDATION_1 = "筑基前期"
    FOUNDATION_2 = "筑基中期"
    FOUNDATION_3 = "筑基后期"
    FOUNDATION_4 = "筑基圆满"
    CORE_1 = "金丹前期"
    CORE_2 = "金丹中期"
    CORE_3 = "金丹后期"
    CORE_4 = "金丹圆满"
    NASCENT_1 = "元婴前期"
    NASCENT_2 = "元婴中期"
    NASCENT_3 = "元婴后期"
    NASCENT_4 = "元婴圆满"
    SPIRIT_1 = "化神前期"
    SPIRIT_2 = "化神中期"
    SPIRIT_3 = "化神后期"
    SPIRIT_4 = "化神圆满"


class RebirthUnlock(StrEnum):
    HIDDEN_SECTS = "隐藏宗门"
    DESTINY_SYSTEM = "命格系统"
    ANCIENT_METHODS = "古传承"
    VOID_MARKET = "虚市交易位"
    HIGHER_ROOT_FLOOR = "高阶灵根保底"


@dataclass(slots=True)
class CultivationMethod:
    id: str
    name: str
    realm_requirement: Realm
    practice_bonus: float
    breakthrough_bonus: float
    source_sect_id: Optional[str] = None
    required_rebirth_count: int = 0


@dataclass(slots=True)
class Sect:
    id: str
    name: str
    theme: str
    description: str
    required_rebirth_count: int = 0
    method_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Player:
    user_id: str
    nickname: str
    root_type: RootType
    realm: Realm = Realm.QI_1
    cultivation: int = 0
    age: int = 16
    age_progress: int = 0
    lifespan: int = 120
    spirit_stones: int = 0
    fortune: int = 0
    stamina: int = 100
    comprehension: int = 10
    rebirth_count: int = 0
    soul_marks: int = 0
    legacy_points: int = 0
    sect_id: Optional[str] = None
    meditation_started_at: Optional[str] = None
    meditation_until: Optional[str] = None
    meditation_minutes: int = 0
    meditation_reward: int = 0
    meditation_method_id: Optional[str] = None
    method_ids: list[str] = field(default_factory=list)
    inventory: dict[str, int] = field(default_factory=dict)
