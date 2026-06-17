from xianbot.domain import Player, Realm, RootType
from xianbot.progression import calculate_rebirth_outcome, can_rebirth


def test_can_rebirth_requires_peak_realm_and_soul_mark() -> None:
    player = Player(
        user_id="1",
        nickname="test",
        root_type=RootType.MORTAL,
        realm=Realm.SPIRIT_4,
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
    assert len(outcome.unlocked_features) >= 4
