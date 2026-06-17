import asyncio
from collections import Counter

from xianbot.config import get_settings
from xianbot.database import initialize_database
from xianbot.domain import MeditationMode, Realm
from xianbot.repository import GameRepository
from xianbot.services import (
    adventure,
    breakthrough,
    buy_market_listing,
    contemplate_method,
    craft_elixir,
    create_market_listing,
    create_player_if_missing,
    duel,
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


def test_multi_user_concurrency_and_storage_integrity(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian7.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        ids = [f"200{i:02d}" for i in range(1, 13)]

        created = await asyncio.gather(
            *(create_player_if_missing(user_id, f"user{index}") for index, user_id in enumerate(ids, start=1))
        )
        assert all(result[0].user_id in ids for result in created)
        assert sum(1 for _, was_created in created if was_created) == len(ids)

        duplicated = await asyncio.gather(
            *(create_player_if_missing(ids[0], "same-user") for _ in range(6))
        )
        assert sum(1 for _, was_created in duplicated if was_created) == 0

        sign_results = await asyncio.gather(*(sign_in(user_id) for user_id in ids))
        assert len(sign_results) == len(ids)
        assert all(result.total_spirit_stones >= 420 for result in sign_results)

        persisted = await asyncio.gather(*(get_player_status(user_id) for user_id in ids))
        assert all(player is not None for player in persisted)
        assert len({player.user_id for player in persisted if player is not None}) == len(ids)

        repo = GameRepository(get_settings().database_url)
        one = await repo.get_player(ids[0])
        assert one is not None
        assert one.inventory["qigather"] >= 2
        assert one.inventory["spirit-herb"] >= 3
        assert one.inventory["clear-dew"] >= 2

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_market_purchase_is_atomic_under_concurrency(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian8.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("30001", "seller")
        await create_player_if_missing("30002", "buyer1")
        await create_player_if_missing("30003", "buyer2")

        listing = await create_market_listing("30001", "灵草", 40, 1)

        async def try_buy(user_id: str) -> str:
            try:
                result = await buy_market_listing(user_id, listing.listing_id)
                return f"ok:{result.seller_name}"
            except Exception as exc:  # noqa: BLE001
                return str(exc)

        results = await asyncio.gather(
            try_buy("30002"),
            try_buy("30003"),
        )
        counter = Counter(results)
        assert sum(1 for item in results if item.startswith("ok:")) == 1, results
        assert counter["listing_unavailable"] == 1, results

        repo = GameRepository(get_settings().database_url)
        sold = await repo.get_market_listing(listing.listing_id)
        assert sold is not None
        assert sold["status"] == "sold"

        buyers = [await get_player_status("30002"), await get_player_status("30003")]
        inventories = [await list_inventory("30002"), await list_inventory("30003")]
        bought_counts = [
            next((item["quantity"] for item in bag if item["name"] == "灵草"), 0)
            for bag in inventories
        ]
        assert sorted(bought_counts) == [3, 4]
        assert all(player is not None for player in buyers)

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_duel_randomness_and_influences_are_applied(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian9.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("40001", "stronger")
        await create_player_if_missing("40002", "weaker")
        await join_sect("40001", "赤霄门")
        await join_sect("40002", "青岚宗")

        repo = GameRepository(get_settings().database_url)
        await repo.update_player_stats(
            "40001",
            realm=Realm.FOUNDATION_3,
            cultivation_delta=2200,
            insight_delta=30,
            breakthrough_ready_delta=40,
            fortune_delta=20,
        )
        await repo.update_player_stats(
            "40002",
            realm=Realm.QI_3,
            cultivation_delta=250,
            insight_delta=2,
            breakthrough_ready_delta=2,
            fortune_delta=1,
        )

        results = []
        for _ in range(12):
            duel_result = await duel("40001", "40002")
            results.append(duel_result)
            await repo.update_player_stats("40001", stamina_delta=100)
            await repo.update_player_stats("40002", stamina_delta=100)

        assert any(result.attacker_roll != result.defender_roll for result in results)
        assert any(result.attacker_total != result.defender_total for result in results)
        assert all(result.winner_name == "stronger" for result in results)
        assert all(result.attacker_total > result.defender_total for result in results)

        stronger = await get_player_status("40001")
        weaker = await get_player_status("40002")
        assert stronger is not None
        assert weaker is not None
        assert stronger.spirit_stones > weaker.spirit_stones
        assert weaker.cultivation >= 0

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


def test_alchemy_and_duel_gameplay(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian6.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("10006", "tester6")
        await create_player_if_missing("10007", "tester7")
        await join_sect("10006", "赤霄门")
        await join_sect("10007", "青岚宗")

        repo = GameRepository(get_settings().database_url)
        await repo.add_inventory_item("10006", "spirit-herb", 3)
        await repo.add_inventory_item("10006", "clear-dew", 2)
        await repo.add_inventory_item("10006", "flame-sand", 1)

        import xianbot.services as services

        alchemy_randint = services.random.randint
        services.random.randint = lambda a, b: 7
        try:
            alchemy = await craft_elixir("10006", "凝元丹")
        finally:
            services.random.randint = alchemy_randint

        assert alchemy.success is True
        assert alchemy.item_name == "凝元丹"
        bag = await list_inventory("10006")
        assert any(item["name"] == "凝元丹" for item in bag)

        await repo.update_player_stats(
            "10006",
            realm=Realm.FOUNDATION_2,
            cultivation_delta=1500,
            insight_delta=24,
            breakthrough_ready_delta=35,
            fortune_delta=18,
        )
        await repo.update_player_stats(
            "10007",
            realm=Realm.QI_4,
            cultivation_delta=600,
            insight_delta=6,
            breakthrough_ready_delta=8,
            fortune_delta=5,
        )

        sequence = iter([88, 36, 52])
        duel_randint = services.random.randint
        services.random.randint = lambda a, b: next(sequence)
        try:
            duel_result = await duel("10006", "10007")
        finally:
            services.random.randint = duel_randint

        assert duel_result.winner_name == "tester6"
        assert duel_result.winner_spirit_stones_gain >= 52

        winner = await get_player_status("10006")
        loser = await get_player_status("10007")
        assert winner is not None
        assert loser is not None
        assert winner.spirit_stones >= 300 + duel_result.winner_spirit_stones_gain
        assert loser.cultivation >= 0
        assert loser.stamina < 100

    asyncio.run(scenario())
    get_settings.cache_clear()
