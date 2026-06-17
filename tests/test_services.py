import asyncio
from collections import Counter

from xianbot.config import get_settings
from xianbot.database import initialize_database
from xianbot.domain import DestinyType, MeditationMode, Realm
from xianbot.repository import GameRepository
from xianbot.services import (
    adventure,
    breakthrough,
    buy_market_listing,
    claim_today_world_event_reward,
    contemplate_method,
    craft_elixir,
    create_market_listing,
    create_player_if_missing,
    duel,
    encounter,
    end_meditation,
    get_destiny_status,
    get_player_methods,
    get_player_status,
    get_today_world_event,
    get_today_world_state,
    join_sect,
    rebirth,
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
        assert updated.destiny_type is None
        destiny = await get_destiny_status("10001")
        assert destiny.destiny_name == "命格未显"

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_world_event_generation_progress_and_claim(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian12.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("70001", "eventer")
        repo = GameRepository(get_settings().database_url)

        generated = await get_today_world_event("70001")
        assert generated.title
        assert generated.target_progress > 0
        assert generated.player_contribution == 0
        assert generated.claimed is False

        await repo.save_world_event(
            event_date=generated.event_date,
            event_key="secret-realm",
            title="玄脉秘境开启",
            description="群友协力稳固秘境入口。",
            objective="通过历练清剿外围异兽。",
            target_progress=6,
            current_progress=0,
            reward_spirit_stones=180,
            reward_cultivation=260,
            reward_insight=1,
            reward_item_id="spirit-herb",
            reward_item_quantity=2,
            bonus_text="历练额外获得收益。",
            participation_hint="多用“历练”推进。",
            completed_at=None,
        )

        result = await adventure("70001")
        assert result.event_notice is not None
        assert "世界事件" in result.event_notice

        progressed = await get_today_world_event("70001")
        assert progressed.current_progress > 0
        assert progressed.player_contribution > 0
        assert progressed.claimed is False

        await repo.save_world_event(
            event_date=generated.event_date,
            event_key="secret-realm",
            title="玄脉秘境开启",
            description="群友协力稳固秘境入口。",
            objective="通过历练清剿外围异兽。",
            target_progress=progressed.target_progress,
            current_progress=progressed.target_progress,
            reward_spirit_stones=180,
            reward_cultivation=260,
            reward_insight=1,
            reward_item_id="spirit-herb",
            reward_item_quantity=2,
            bonus_text="历练额外获得收益。",
            participation_hint="多用“历练”推进。",
            completed_at="2026-06-18T12:00:00",
        )

        before = await get_player_status("70001")
        assert before is not None
        reward = await claim_today_world_event_reward("70001")
        assert reward.title == "玄脉秘境开启"
        assert reward.contribution == progressed.player_contribution
        assert reward.reward_spirit_stones == 180
        assert reward.reward_cultivation == 260
        assert reward.reward_insight == 1
        assert reward.reward_item_name == "灵草"
        assert reward.reward_item_quantity == 2

        after = await get_player_status("70001")
        assert after is not None
        assert after.spirit_stones >= before.spirit_stones + 180
        assert after.cultivation >= before.cultivation + 260
        assert after.insight >= before.insight + 1

        claimed = await get_today_world_event("70001")
        assert claimed.claimed is True

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_world_event_claim_rejects_repeat_claim(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian13.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("70002", "claimer")
        repo = GameRepository(get_settings().database_url)
        event_date = (await get_today_world_event("70002")).event_date

        await repo.save_world_event(
            event_date=event_date,
            event_key="ruin-echo",
            title="残碑道藏出世",
            description="古碑虚影散落四方。",
            objective="通过奇遇搜集残碑气机。",
            target_progress=5,
            current_progress=5,
            reward_spirit_stones=150,
            reward_cultivation=220,
            reward_insight=2,
            reward_item_id="method-fragment",
            reward_item_quantity=1,
            bonus_text="奇遇更易增益。",
            participation_hint="多用“奇遇”推进。",
            completed_at="2026-06-18T08:00:00",
        )
        await repo.contribute_world_event(
            event_date=event_date,
            user_id="70002",
            contribution=3,
        )

        first = await claim_today_world_event_reward("70002")
        assert first.reward_item_name == "吐纳残篇"

        try:
            await claim_today_world_event_reward("70002")
        except ValueError as exc:
            assert str(exc) == "already_claimed"
        else:
            raise AssertionError("second claim should fail")

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_world_event_concurrency_is_atomic(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian14.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        ids = [f"7100{i}" for i in range(1, 7)]
        await asyncio.gather(*(create_player_if_missing(user_id, user_id) for user_id in ids))

        repo = GameRepository(get_settings().database_url)
        event_date = (await get_today_world_event(ids[0])).event_date
        await repo.save_world_event(
            event_date=event_date,
            event_key="secret-realm",
            title="玄脉秘境开启",
            description="群友协力稳固秘境入口。",
            objective="通过历练清剿外围异兽。",
            target_progress=12,
            current_progress=0,
            reward_spirit_stones=180,
            reward_cultivation=260,
            reward_insight=1,
            reward_item_id="spirit-herb",
            reward_item_quantity=2,
            bonus_text="历练额外获得收益。",
            participation_hint="多用“历练”推进。",
            completed_at=None,
        )

        results = await asyncio.gather(*(adventure(user_id) for user_id in ids))
        assert all(result.event_notice for result in results)

        event = await get_today_world_event(ids[0])
        contributions = await asyncio.gather(
            *(repo.get_world_event_contribution(event_date, user_id) for user_id in ids)
        )
        total_contribution = sum(int(row["contribution"]) for row in contributions if row is not None)

        assert event.current_progress == event.target_progress
        assert event.completed is True
        assert total_contribution >= event.target_progress
        assert all(row is not None and int(row["contribution"]) > 0 for row in contributions)

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


def test_rebirth_unlocks_destiny_and_persists(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian10.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("50001", "reborn")
        repo = GameRepository(get_settings().database_url)
        await repo.update_player_stats(
            "50001",
            rebirth_count_delta=1,
            realm=Realm.SPIRIT_4,
            cultivation_delta=12000,
            insight_delta=120,
            breakthrough_ready_delta=80,
            soul_marks_delta=1,
            legacy_points_delta=6,
        )

        result = await rebirth("50001")
        assert result.destiny_name != "命格未显"
        assert result.destiny_level >= 1

        player = await get_player_status("50001")
        assert player is not None
        assert player.rebirth_count == 2
        assert player.destiny_type is not None
        assert player.destiny_level == result.destiny_level
        destiny = await get_destiny_status("50001")
        assert destiny.destiny_name == result.destiny_name
        assert destiny.destiny_level == result.destiny_level

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_destiny_improves_alchemy_and_duel(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian11.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("60001", "alchemist")
        await create_player_if_missing("60002", "fighter")
        await create_player_if_missing("60003", "target")
        await join_sect("60001", "赤霄门")
        await join_sect("60002", "赤霄门")
        await join_sect("60003", "青岚宗")

        repo = GameRepository(get_settings().database_url)
        await repo.update_player_stats("60001", rebirth_count_delta=1)
        await repo.add_inventory_item("60001", "clear-dew", 4)
        await repo.add_inventory_item("60001", "flame-sand", 2)
        await repo.add_inventory_item("60001", "moon-dust", 2)
        await repo.add_inventory_item("60001", "marrow-jade", 2)

        import xianbot.services as services

        original_randint = services.random.randint
        services.random.randint = lambda a, b: 82
        try:
            baseline_alchemy = await craft_elixir("60001", "洗髓丹")
        finally:
            services.random.randint = original_randint
        assert baseline_alchemy.success is False

        await repo.update_player_stats(
            "60001",
            rebirth_count_delta=1,
            legacy_points_delta=6,
            destiny_type=DestinyType.ALCHEMY,
            destiny_level_delta=4,
        )
        try:
            services.random.randint = lambda a, b: 82
            empowered_alchemy = await craft_elixir("60001", "洗髓丹")
        finally:
            services.random.randint = original_randint
        assert empowered_alchemy.success is True
        assert empowered_alchemy.chance_percent > baseline_alchemy.chance_percent

        await repo.update_player_stats(
            "60002",
            realm=Realm.FOUNDATION_2,
            cultivation_delta=1500,
            insight_delta=24,
            breakthrough_ready_delta=35,
            fortune_delta=18,
        )
        await repo.update_player_stats(
            "60003",
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
            baseline_duel = await duel("60002", "60003")
        finally:
            services.random.randint = duel_randint

        await repo.update_player_stats(
            "60002",
            cultivation_delta=-baseline_duel.winner_cultivation_gain,
            stamina_delta=100,
        )
        await repo.update_player_stats(
            "60003",
            cultivation_delta=-baseline_duel.loser_cultivation_loss,
            stamina_delta=100,
        )
        await repo.update_player_stats(
            "60002",
            destiny_type=DestinyType.BATTLE,
            destiny_level_delta=4,
        )

        sequence = iter([88, 36, 52])
        duel_randint = services.random.randint
        services.random.randint = lambda a, b: next(sequence)
        try:
            empowered_duel = await duel("60002", "60003")
        finally:
            services.random.randint = duel_randint

        assert baseline_duel.winner_name == "fighter"
        assert empowered_duel.winner_name == "fighter"
        assert empowered_duel.attacker_total > baseline_duel.attacker_total

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
