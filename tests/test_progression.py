from xianbot.domain import Player, Realm, RootType
from xianbot.progression import calculate_rebirth_outcome, can_rebirth, realm_cap_for_rebirth_count


def test_can_rebirth_requires_peak_realm_and_soul_mark() -> None:
    player = Player(
        user_id="1",
        nickname="test",
        root_type=RootType.MORTAL,
        realm=Realm.FOUNDATION_4,
        soul_marks=1,
    )
    assert can_rebirth(player) is True


def test_calculate_rebirth_outcome_unlocks_more_features_over_time() -> None:
    player = Player(
        user_id="1",
        nickname="test",
        root_type=RootType.MORTAL,
        rebirth_count=1,
    )
    outcome = calculate_rebirth_outcome(player)
    assert outcome.legacy_points_gained == 2
    assert outcome.next_root_floor == RootType.YELLOW
    assert outcome.next_realm_cap == Realm.NASCENT_4
    assert len(outcome.unlocked_features) >= 4


def test_realm_cap_rises_with_rebirth_count() -> None:
    assert realm_cap_for_rebirth_count(0) == Realm.FOUNDATION_4
    assert realm_cap_for_rebirth_count(1) == Realm.CORE_4
    assert realm_cap_for_rebirth_count(2) == Realm.NASCENT_4
    assert realm_cap_for_rebirth_count(3) == Realm.SPIRIT_4
