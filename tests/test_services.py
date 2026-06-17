import asyncio

from xianbot.config import get_settings
from xianbot.database import initialize_database
from xianbot.domain import MeditationMode, Realm
from xianbot.repository import GameRepository
from xianbot.services import (
    adventure,
    breakthrough,
    contemplate_method,
    create_market_listing,
    create_player_if_missing,
    encounter,
    end_meditation,
    get_player_methods,
    get_player_status,
    get_today_world_state,
    join_sect,
    list_inventory,
    set_primary_method,
    sign_in,
    start_meditation,
)


def test_create_player_and_sign_in(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        player, created = await create_player_if_missing("10001", "tester")
        assert created is True
        assert player.user_id == "10001"
        assert player.root_affinity.value
        assert player.root_purity >= 32

        result = await sign_in("10001")
        assert result.base_reward >= 120

        updated = await get_player_status("10001")
        assert updated is not None
        assert updated.spirit_stones >= 420

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_join_sect_inventory_primary_method_and_listing(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian2.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("10002", "tester2")
        result = await join_sect("10002", "青岚宗")
        assert result.sect_name == "青岚宗"
        assert result.method_name == "吐纳诀"

        methods = await get_player_methods("10002")
        assert any(bool(method.get("equipped")) for method in methods)

        switched = await set_primary_method("10002", "吐纳诀")
        assert switched.method_name == "吐纳诀"
        assert switched.practice_bonus_percent >= 10

        bag = await list_inventory("10002")
        assert len(bag) >= 1

        await adventure("10002")
        listing = await create_market_listing("10002", "灵草", 20, 1)
        assert listing.listing_id > 0

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_world_state_encounter_and_method_growth(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian3.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("10003", "tester3")
        await join_sect("10003", "青岚宗")

        world = await get_today_world_state()
        assert world.title

        oddity = await encounter("10003")
        assert oddity.world_title == world.title

        player = await get_player_status("10003")
        assert player is not None

        methods = await list_inventory("10003")
        assert methods is not None

        repo = GameRepository(get_settings().database_url)
        await repo.add_inventory_item("10003", "method-fragment", 1)
        insight = await contemplate_method("10003")
        assert insight.mastery_gain > 0
        assert insight.new_mastery >= insight.mastery_gain
        assert insight.insight_gain > 0

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_meditation_modes_and_breakthrough_preparation(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian4.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("10004", "tester4")
        await join_sect("10004", "青岚宗")
        result = await start_meditation("10004", 30, MeditationMode.BREAKTHROUGH)
        assert result.mode_name == "冲关"
        assert result.breakthrough_reward > 0

        repo = GameRepository(get_settings().database_url)
        player = await repo.get_player("10004")
        assert player is not None
        past_until = "2000-01-01T00:00:00"
        await repo.set_player_meditation(
            "10004",
            started_at="2000-01-01T00:00:00",
            until=past_until,
            minutes=30,
            reward=player.meditation_reward,
            method_id=player.meditation_method_id,
            mode=MeditationMode.BREAKTHROUGH,
            insight_reward=player.meditation_insight_reward or 2,
            breakthrough_reward=player.meditation_breakthrough_reward or 10,
        )

        claimed = await end_meditation("10004")
        assert claimed.still_waiting is False
        assert claimed.breakthrough_ready_gain > 0

        updated = await get_player_status("10004")
        assert updated is not None
        assert updated.breakthrough_ready >= claimed.breakthrough_ready_gain

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_breakthrough_unlocks_sect_method(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian5.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("10005", "tester5")
        await join_sect("10005", "青岚宗")
        repo = GameRepository(get_settings().database_url)
        await repo.update_player_stats(
            "10005",
            realm=Realm.QI_4,
            cultivation_delta=800,
            breakthrough_ready_delta=50,
            insight_delta=20,
            fortune_delta=50,
        )

        result = await breakthrough("10005")
        assert result.success is True
        assert result.next_realm == Realm.FOUNDATION_1.value
        assert "青岚养心篇" in result.unlocked_methods

        methods = await get_player_methods("10005")
        assert any(method["name"] == "青岚养心篇" for method in methods)

    asyncio.run(scenario())
    get_settings.cache_clear()
