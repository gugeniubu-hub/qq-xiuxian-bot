import asyncio
from collections import Counter

from xianbot.config import get_settings
from xianbot.database import initialize_database
from xianbot.domain import Affinity, DestinyType, MeditationMode, Realm, RootTemperament, RootTrait, RootType
from xianbot.repository import GameRepository
from xianbot.services import (
    GameError,
    _effective_max_realm,
    adventure,
    breakthrough,
    buy_market_listing,
    claim_today_world_event_reward,
    contemplate_method,
    craft_elixir,
    create_market_listing,
    create_player_if_missing,
    duel,
    equip_artifact,
    encounter,
    end_meditation,
    explore_ancient_trial,
    explore_map_area,
    get_method_detail_panel,
    get_attribute_panel,
    get_destiny_status,
    get_player_panel,
    get_player_methods,
    get_recent_actions,
    get_player_status,
    get_today_world_event,
    get_today_world_state,
    join_sect,
    list_sect_method_options,
    list_maps_for_player,
    list_artifacts,
    rebirth,
    list_inventory,
    consume_item,
    request_sect_method,
    reroll_root_profile,
    set_primary_method,
    sign_in,
    start_meditation,
)


def test_repository_maintenance_cleans_old_records_but_keeps_recent_guardrails(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian_maintenance.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        repo = GameRepository(get_settings().database_url)
        await create_player_if_missing("91001", "janitor")

        async with repo._connect() as db:
            await db.executemany(
                """
                INSERT INTO adventure_logs (
                  user_id, action_type, roll_value, outcome,
                  reward_spirit_stones, reward_cultivation, reward_item_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("91001", "adventure", 10, "old-1", 0, 0, None, "2024-01-01 00:00:00"),
                    ("91001", "adventure", 20, "old-2", 0, 0, None, "2024-01-02 00:00:00"),
                    ("91001", "adventure", 30, "new-1", 0, 0, None, "2099-01-01 00:00:00"),
                    ("91001", "adventure", 40, "new-2", 0, 0, None, "2099-01-02 00:00:00"),
                ],
            )
            await db.execute(
                """
                INSERT INTO daily_signins (user_id, sign_date, base_reward, pool_reward, fortune_roll)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("91001", "2024-01-01", 1, 0, 1),
            )
            await db.execute(
                """
                INSERT INTO market_listings (
                  seller_user_id, item_id, quantity, unit_price, status, buyer_user_id, created_at, sold_at
                ) VALUES (?, ?, ?, ?, 'sold', ?, ?, ?)
                """,
                ("91001", "spirit-herb", 1, 10, "91002", "2024-01-01 00:00:00", "2024-01-03 00:00:00"),
            )
            await db.execute(
                """
                INSERT INTO world_states (
                  state_date, title, description, adventure_bonus, meditation_bonus,
                  encounter_bonus, fortune_bonus, lifespan_bonus
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("2024-01-01", "old state", "old", 0, 0, 0, 0, 0),
            )
            await db.execute(
                """
                INSERT INTO world_events (
                  event_date, event_key, title, description, objective,
                  target_progress, current_progress, reward_spirit_stones,
                  reward_cultivation, reward_insight, reward_item_id, reward_item_quantity,
                  bonus_text, participation_hint, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "2024-01-01",
                    "legacy-event",
                    "old event",
                    "old desc",
                    "old objective",
                    10,
                    10,
                    0,
                    0,
                    0,
                    None,
                    0,
                    "",
                    "",
                    "2024-01-01 00:00:00",
                ),
            )
            await db.execute(
                """
                INSERT INTO world_event_contributions (event_date, user_id, contribution, claimed, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("2024-01-01", "91001", 3, 1, "2024-01-01 00:00:00"),
            )
            await db.execute(
                """
                INSERT INTO player_action_cooldowns (user_id, action_type, available_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                ("91001", "adventure", "2024-01-01 00:00:00", "2024-01-01 00:00:00"),
            )
            await db.execute(
                """
                INSERT INTO rebirth_logs (
                  user_id, rebirth_count, previous_realm, legacy_points_gained,
                  soul_marks_consumed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("91001", 1, Realm.FOUNDATION_4.value, 2, 1, "2024-01-01 00:00:00"),
            )
            await db.commit()

        stats = await repo.run_maintenance(
            action_log_days=30,
            action_log_keep_latest_per_user=2,
            signin_days=60,
            sold_market_days=30,
            world_days=45,
            cooldown_grace_days=3,
            rebirth_log_days=365,
        )

        assert stats["adventure_logs_deleted"] == 2
        assert stats["daily_signins_deleted"] == 1
        assert stats["market_listings_deleted"] == 1
        assert stats["world_states_deleted"] == 1
        assert stats["world_events_deleted"] == 1
        assert stats["world_event_contributions_deleted"] == 1
        assert stats["cooldowns_deleted"] == 1
        assert stats["rebirth_logs_deleted"] == 1

        async with repo._connect() as db:
            remaining_logs = await repo._fetchall(
                db,
                "SELECT outcome FROM adventure_logs WHERE user_id = ? ORDER BY id ASC",
                ("91001",),
            )
            remaining_outcomes = [str(row["outcome"]) for row in remaining_logs]
            assert remaining_outcomes == ["new-1", "new-2"]

            signin_count = await repo._fetchone(db, "SELECT COUNT(*) AS cnt FROM daily_signins", ())
            market_count = await repo._fetchone(db, "SELECT COUNT(*) AS cnt FROM market_listings", ())
            state_count = await repo._fetchone(db, "SELECT COUNT(*) AS cnt FROM world_states", ())
            event_count = await repo._fetchone(db, "SELECT COUNT(*) AS cnt FROM world_events", ())
            contribution_count = await repo._fetchone(
                db,
                "SELECT COUNT(*) AS cnt FROM world_event_contributions",
                (),
            )
            cooldown_count = await repo._fetchone(
                db,
                "SELECT COUNT(*) AS cnt FROM player_action_cooldowns",
                (),
            )
            rebirth_count = await repo._fetchone(db, "SELECT COUNT(*) AS cnt FROM rebirth_logs", ())

            assert int(signin_count["cnt"]) == 0
            assert int(market_count["cnt"]) == 0
            assert int(state_count["cnt"]) == 0
            assert int(event_count["cnt"]) == 0
            assert int(contribution_count["cnt"]) == 0
            assert int(cooldown_count["cnt"]) == 0
            assert int(rebirth_count["cnt"]) == 0

    asyncio.run(scenario())
    get_settings.cache_clear()


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


def test_initial_realm_cap_blocks_higher_breakthrough(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian15.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("80001", "capper")
        repo = GameRepository(get_settings().database_url)
        await repo.update_player_stats(
            "80001",
            realm=Realm.FOUNDATION_4,
            cultivation_delta=2600,
            breakthrough_ready_delta=80,
            insight_delta=30,
            fortune_delta=30,
        )
        player = await get_player_status("80001")
        assert player is not None
        assert _effective_max_realm(player) == Realm.FOUNDATION_4

        try:
            await breakthrough("80001")
        except ValueError as exc:
            assert str(exc) == "realm_maxed"
        else:
            raise AssertionError("initial realm cap should block further breakthrough")

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_rebirth_raises_realm_cap_and_root_rarity(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian16.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("80002", "reborncap")
        repo = GameRepository(get_settings().database_url)
        await repo.update_player_stats(
            "80002",
            realm=Realm.FOUNDATION_4,
            cultivation_delta=3200,
            insight_delta=120,
            breakthrough_ready_delta=80,
            soul_marks_delta=1,
            legacy_points_delta=3,
        )

        result = await rebirth("80002")
        assert result.new_realm_cap == Realm.CORE_4.value

        player = await get_player_status("80002")
        assert player is not None
        assert player.rebirth_count == 1
        assert _effective_max_realm(player) == Realm.CORE_4
        assert player.root_purity >= 33
        assert player.root_affinity.value

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_root_affinity_bias_strengthens_matching_methods(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian17.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("80003", "fire-matcher")
        await create_player_if_missing("80004", "water-contrast")
        repo = GameRepository(get_settings().database_url)
        for user_id, affinity in (("80003", Affinity.FIRE), ("80004", Affinity.WATER)):
            await join_sect(user_id, "赤霄门")
            await repo.update_player_stats(
                user_id,
                root_type=RootType.HEAVEN,
                root_affinity=affinity,
                root_purity=92,
                root_temperament=RootTemperament.FIERCE,
                root_trait=RootTrait.EMBER,
                rebirth_count_delta=2,
            )

        fire_methods = await get_player_methods("80003")
        water_methods = await get_player_methods("80004")
        fire_match = next((item for item in fire_methods if str(item["affinity"]) == Affinity.FIRE.value), None)
        water_match = next((item for item in water_methods if str(item["affinity"]) == Affinity.FIRE.value), None)

        assert fire_match is not None
        assert water_match is not None
        assert str(fire_match["id"]) == str(water_match["id"])
        assert float(fire_match["practice_total"]) > float(water_match["practice_total"])
        assert int(fire_match["breakthrough_total"]) > int(water_match["breakthrough_total"])

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_meditation_and_alchemy_gain_root_specific_bias(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian18.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("80005", "void-pill")
        await create_player_if_missing("80006", "earth-core")
        repo = GameRepository(get_settings().database_url)

        await repo.update_player_stats(
            "80005",
            root_type=RootType.HEAVEN,
            root_affinity=Affinity.VOID,
            root_purity=94,
            root_temperament=RootTemperament.ENLIGHTENED,
            root_trait=RootTrait.INSIGHTFUL,
            rebirth_count_delta=2,
        )
        await repo.update_player_stats(
            "80006",
            root_type=RootType.HEAVEN,
            root_affinity=Affinity.EARTH,
            root_purity=93,
            root_temperament=RootTemperament.TRANQUIL,
            root_trait=RootTrait.GATHERING,
            rebirth_count_delta=1,
        )

        await join_sect("80005", "青岚宗")
        await join_sect("80006", "赤霄门")
        await repo.grant_player_method("80005", "mist-heart")
        await repo.grant_player_method("80006", "flame-body")
        await set_primary_method("80005", "青岚养心篇")
        await set_primary_method("80006", "离火锻骨篇")

        await repo.add_inventory_item("80005", "spirit-herb", 2)
        await repo.add_inventory_item("80005", "clear-dew", 1)
        await repo.add_inventory_item("80005", "moon-dust", 1)

        import xianbot.services as services

        original_randint = services.random.randint
        services.random.randint = lambda a, b: 8
        try:
            insight_alchemy = await craft_elixir("80005", "悟道丹")
        finally:
            services.random.randint = original_randint

        assert insight_alchemy.success is True
        assert insight_alchemy.quantity == 2
        assert insight_alchemy.insight_gain >= 2

        insight_meditation = await start_meditation("80005", 30, MeditationMode.INSIGHT)
        breakthrough_meditation = await start_meditation("80006", 30, MeditationMode.BREAKTHROUGH)

        assert insight_meditation.insight_reward > breakthrough_meditation.insight_reward
        assert breakthrough_meditation.breakthrough_reward > insight_meditation.breakthrough_reward

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_consumables_are_single_purpose_and_respect_caps(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian21.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("92001", "pilltester")
        repo = GameRepository(get_settings().database_url)
        await repo.add_inventory_item("92001", "essence-pill", 1)
        await repo.add_inventory_item("92001", "insight-pill", 1)
        await repo.add_inventory_item("92001", "restore-powder", 1)
        await repo.update_player_stats(
            "92001",
            stamina_delta=-40,
            breakthrough_ready_delta=91,
        )

        import xianbot.services as services

        original_randint = services.random.randint
        sequence = iter([12, 5, 33])
        services.random.randint = lambda a, b: next(sequence)
        try:
            essence_result = await consume_item("92001", "凝元丹")
            insight_result = await consume_item("92001", "悟道丹")
            restore_result = await consume_item("92001", "回灵散")
        finally:
            services.random.randint = original_randint

        assert essence_result.cultivation_delta == 0
        assert essence_result.breakthrough_ready_delta == 9
        assert insight_result.cultivation_delta == 0
        assert insight_result.insight_delta >= 5
        assert restore_result.stamina_delta == 33

        player = await get_player_status("92001")
        assert player is not None
        assert player.breakthrough_ready == 100
        assert player.insight == insight_result.insight_delta
        assert player.stamina == 93

        await repo.add_inventory_item("92001", "essence-pill", 1)
        await repo.add_inventory_item("92001", "restore-powder", 1)
        essence_before = next(
            item["quantity"] for item in await list_inventory("92001") if item["item_id"] == "essence-pill"
        )
        restore_before = next(
            item["quantity"] for item in await list_inventory("92001") if item["item_id"] == "restore-powder"
        )

        try:
            await consume_item("92001", "凝元丹")
        except GameError as exc:
            assert str(exc) == "breakthrough_full"
        else:
            raise AssertionError("full breakthrough readiness should block essence pill use")

        await repo.update_player_stats("92001", stamina_delta=7)
        try:
            await consume_item("92001", "回灵散")
        except GameError as exc:
            assert str(exc) == "stamina_full"
        else:
            raise AssertionError("full stamina should block restore powder use")

        bag = await list_inventory("92001")
        assert next(item["quantity"] for item in bag if item["item_id"] == "essence-pill") == essence_before
        assert next(item["quantity"] for item in bag if item["item_id"] == "restore-powder") == restore_before

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
        assert first.reward_item_name == "悟道札记"

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


def test_stamina_recovers_lazily_on_player_load(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian_stamina.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("72001", "stamina")
        repo = GameRepository(get_settings().database_url)
        async with repo._connect() as db:
            await db.execute(
                """
                UPDATE players
                SET stamina = 50, stamina_recovered_at = '2000-01-01T00:00:00+00:00'
                WHERE user_id = ?
                """,
                ("72001",),
            )
            await db.commit()

        recovered = await get_player_status("72001")
        assert recovered is not None
        assert recovered.stamina == 100

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_concurrent_method_request_charges_once(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian_request_method.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("72002", "requester")
        await join_sect("72002", "青岚宗")
        repo = GameRepository(get_settings().database_url)
        before = await get_player_status("72002")
        assert before is not None
        await repo.update_player_stats(
            "72002",
            realm=Realm.FOUNDATION_1,
            spirit_stones_delta=1000,
            insight_delta=30,
        )

        options = await list_sect_method_options("72002")
        option = next(item for item in options if item.method_name == "青岚养心篇")
        results = await asyncio.gather(
            request_sect_method("72002", "青岚养心篇"),
            request_sect_method("72002", "青岚养心篇"),
            return_exceptions=True,
        )
        successes = [item for item in results if not isinstance(item, Exception)]
        failures = [item for item in results if isinstance(item, Exception)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert str(failures[0]) in {"already_owned", "method_already_owned"}

        after = await get_player_status("72002")
        assert after is not None
        assert after.spirit_stones == before.spirit_stones + 1000 - option.spirit_stones_cost
        assert after.insight == 30 - option.insight_cost
        methods = await get_player_methods("72002")
        assert [method["name"] for method in methods].count("青岚养心篇") == 1

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_adventure_event_can_injure_and_award_wild_method(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian_adventure_event.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("72003", "wildling")
        repo = GameRepository(get_settings().database_url)
        await repo.update_player_stats(
            "72003",
            realm=Realm.FOUNDATION_4,
            cultivation_delta=1800,
            spirit_stones_delta=400,
        )
        before = await get_player_status("72003")
        assert before is not None

        import xianbot.services as services

        original_event = services._adventure_event_result
        original_discover = services._maybe_discover_adventure_method
        original_randint = services.random.randint
        services.random.randint = lambda a, b: b

        def fake_event(player, method, roll_value):
            return {
                "event_name": "妖兽王游猎",
                "event_type": "野怪",
                "danger": "高",
                "outcome": "lose",
                "roll": 1,
                "total": 1,
                "threshold": 100,
                "message": "妖兽王一撞如山崩，你几乎被震断气海。",
                "cultivation_delta": -60,
                "spirit_delta": -20,
                "stamina_delta": -3,
                "lifespan_delta": -1,
                "injury_notice": "受伤，额外体力 -3。",
                "death_triggered": False,
            }

        async def fake_discover(repo, player, roll_value, event_result):
            granted = await repo.grant_player_method(player.user_id, "beast-body-wild")
            return "万兽炼体经" if granted else None

        services._adventure_event_result = fake_event
        services._maybe_discover_adventure_method = fake_discover
        try:
            result = await adventure("72003")
        finally:
            services._adventure_event_result = original_event
            services._maybe_discover_adventure_method = original_discover
            services.random.randint = original_randint

        assert result.event_type == "野怪"
        assert result.danger_level == "高"
        assert result.injury_notice == "受伤，额外体力 -3。"
        assert result.reward_method_name == "万兽炼体经"
        assert result.stamina_delta == -15

        player = await get_player_status("72003")
        assert player is not None
        assert player.stamina == 85
        assert player.lifespan == before.lifespan - 1
        methods = await get_player_methods("72003")
        assert any(method["name"] == "万兽炼体经" for method in methods)

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_method_detail_and_root_reroll(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian_method_detail.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("72004", "viewer")
        await join_sect("72004", "青岚宗")
        repo = GameRepository(get_settings().database_url)
        await repo.update_player_stats("72004", spirit_stones_delta=500)

        overview = await get_method_detail_panel("72004")
        overview_text = "\n".join(overview.lines)
        assert "野外稀有传承" in overview_text
        assert "玄霜封魂录" in overview_text

        detail = await get_method_detail_panel("72004", "吐纳诀")
        detail_text = "\n".join(detail.lines)
        assert "【功法详情】《吐纳诀》" in detail_text
        assert "当前:" in detail_text

        before = await get_player_status("72004")
        assert before is not None
        rerolled = await reroll_root_profile("72004")
        assert rerolled.spirit_stones_cost == 220
        assert rerolled.remaining_stamina == before.stamina - 8
        assert rerolled.old_root_brief != ""
        assert rerolled.new_root_brief != ""

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
        assert all(result.rounds for result in results)
        assert any("第1回合" in line for result in results for line in result.rounds)

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
            realm=Realm.CORE_4,
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
        await repo.update_player_stats(
            "60001",
            rebirth_count_delta=1,
            root_affinity=Affinity.WOOD,
            root_temperament=RootTemperament.BALANCED,
            root_trait=RootTrait.GATHERING,
        )
        await repo.add_inventory_item("60001", "clear-dew", 4)
        await repo.add_inventory_item("60001", "flame-sand", 2)
        await repo.add_inventory_item("60001", "moon-dust", 2)
        await repo.add_inventory_item("60001", "marrow-jade", 2)

        import xianbot.services as services

        original_randint = services.random.randint
        services.random.randint = lambda a, b: 80
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
            services.random.randint = lambda a, b: 80
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

        sequence = iter([60, 42, 58, 45, 62, 40, 88, 36, 52])
        duel_randint = services.random.randint
        duel_choice = services.random.choice
        services.random.randint = lambda a, b: next(sequence, 52)
        services.random.choice = lambda seq: seq[1]
        try:
            baseline_duel = await duel("60002", "60003")
        finally:
            services.random.randint = duel_randint
            services.random.choice = duel_choice

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

        sequence = iter([60, 42, 58, 45, 62, 40, 88, 36, 52])
        duel_randint = services.random.randint
        duel_choice = services.random.choice
        services.random.randint = lambda a, b: next(sequence, 52)
        services.random.choice = lambda seq: seq[1]
        try:
            empowered_duel = await duel("60002", "60003")
        finally:
            services.random.randint = duel_randint
            services.random.choice = duel_choice

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


def test_ancient_trial_requires_rebirth_and_rewards_rebirth_players(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian19.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("90001", "trialer")
        repo = GameRepository(get_settings().database_url)

        try:
            await explore_ancient_trial("90001")
        except ValueError as exc:
            assert str(exc) == "ancient_trial_locked"
        else:
            raise AssertionError("ancient trial should require at least two rebirths")

        await repo.update_player_stats(
            "90001",
            rebirth_count_delta=2,
            root_type=RootType.HEAVEN,
            root_affinity=Affinity.VOID,
            root_purity=95,
            root_temperament=RootTemperament.ENLIGHTENED,
            root_trait=RootTrait.EMBER,
            insight_delta=40,
            breakthrough_ready_delta=40,
        )
        await join_sect("90001", "太虚观")
        await repo.grant_player_method("90001", "void-scripture")
        await set_primary_method("90001", "太虚轮回经")

        import xianbot.services as services

        original_randint = services.random.randint
        services.random.randint = lambda a, b: 12
        try:
            result = await explore_ancient_trial("90001")
        finally:
            services.random.randint = original_randint

        assert result.success is True
        assert result.reward_spirit_stones > 0
        assert result.reward_cultivation > 0
        assert result.reward_insight > 0
        assert result.reward_item_name is not None

        player = await get_player_status("90001")
        assert player is not None
        assert player.stamina <= 82

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

        import xianbot.services as services

        original_randint = services.random.randint
        services.random.randint = lambda a, b: 1
        try:
            result = await breakthrough("10005")
        finally:
            services.random.randint = original_randint
        assert result.success is True
        assert result.next_realm == Realm.FOUNDATION_1.value
        assert "青岚养心篇" in result.unlocked_methods

        methods = await get_player_methods("10005")
        assert all(method["name"] != "青岚养心篇" for method in methods)

        options = await list_sect_method_options("10005")
        requestable = next(option for option in options if option.method_name == "青岚养心篇")
        assert requestable.available is True
        acquired = await request_sect_method("10005", "青岚养心篇")
        assert acquired.method_name == "青岚养心篇"

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

        sequence = iter([60, 42, 58, 45, 62, 40, 88, 36, 52])
        duel_randint = services.random.randint
        services.random.randint = lambda a, b: next(sequence, 52)
        try:
            duel_result = await duel("10006", "10007")
        finally:
            services.random.randint = duel_randint

        assert duel_result.winner_name == "tester6"
        assert duel_result.winner_spirit_stones_gain >= 52
        assert len(duel_result.rounds) >= 2
        assert any("回合" in line for line in duel_result.rounds)

        winner = await get_player_status("10006")
        loser = await get_player_status("10007")
        assert winner is not None
        assert loser is not None
        assert winner.spirit_stones >= 300 + duel_result.winner_spirit_stones_gain
        assert loser.cultivation >= 0
        assert loser.stamina < 100

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_duel_moves_can_trigger_status_effect_logs(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian20.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("91001", "voidwalker")
        await create_player_if_missing("91002", "flameguard")

        repo = GameRepository(get_settings().database_url)
        await repo.update_player_stats(
            "91001",
            rebirth_count_delta=1,
            realm=Realm.CORE_1,
            root_affinity=Affinity.VOID,
            root_trait=RootTrait.EMBER,
            cultivation_delta=3200,
            insight_delta=30,
            breakthrough_ready_delta=35,
            fortune_delta=12,
        )
        await repo.update_player_stats(
            "91002",
            realm=Realm.FOUNDATION_3,
            root_affinity=Affinity.FIRE,
            root_trait=RootTrait.EVERGREEN,
            cultivation_delta=2400,
            insight_delta=20,
            breakthrough_ready_delta=24,
            fortune_delta=8,
        )
        await join_sect("91001", "太虚观")
        await join_sect("91002", "赤霄门")
        await repo.grant_player_method("91001", "void-scripture")
        await repo.set_primary_method("91001", "void-scripture")
        await repo.grant_player_method("91002", "scarlet-soul")
        await repo.set_primary_method("91002", "scarlet-soul")

        import xianbot.services as services

        original_choice = services.random.choice
        original_randint = services.random.randint

        def choose_first(seq):
            return seq[0]

        sequence = iter([66, 48, 70, 44, 82, 40, 88, 35, 60])
        services.random.choice = choose_first
        services.random.randint = lambda a, b: next(sequence, 60)
        try:
            result = await duel("91001", "91002")
        finally:
            services.random.choice = original_choice
            services.random.randint = original_randint

        text = "\n".join(result.rounds)
        assert "第1回合" in text
        assert "触发：" in text
        assert any(tag in text for tag in ("echo+", "burn+", "regen+", "focus+", "entropy-"))

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_artifact_equipment_panel_and_duel_bonus(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian21.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("92001", "artifactor")
        await create_player_if_missing("92002", "sparring")
        await join_sect("92001", "赤霄门")
        await join_sect("92002", "青岚宗")

        repo = GameRepository(get_settings().database_url)
        await repo.update_player_stats(
            "92001",
            rebirth_count_delta=1,
            realm=Realm.CORE_1,
            root_affinity=Affinity.FIRE,
            cultivation_delta=3000,
            insight_delta=28,
            breakthrough_ready_delta=30,
            fortune_delta=10,
        )
        await repo.update_player_stats(
            "92002",
            realm=Realm.FOUNDATION_3,
            root_affinity=Affinity.WATER,
            cultivation_delta=2200,
            insight_delta=18,
            breakthrough_ready_delta=18,
            fortune_delta=6,
        )

        await repo.add_inventory_item("92001", "artifact-flame-seal", 1)
        artifacts = await list_artifacts("92001")
        assert any(artifact["name"] == "赤焰印" for artifact in artifacts)

        equipped = await equip_artifact("92001", "赤焰印")
        assert equipped.artifact_name == "赤焰印"

        panel = await get_player_panel("92001")
        panel_text = "\n".join(panel.lines)
        assert "法宝: 赤焰印" in panel_text
        assert "火灵根" in panel_text or "灵根:" in panel_text

        import xianbot.services as services

        duel_choice = services.random.choice
        duel_randint = services.random.randint
        services.random.choice = lambda seq: seq[1]
        sequence = iter([60, 42, 58, 45, 62, 40, 88, 36, 52])
        services.random.randint = lambda a, b: next(sequence, 52)
        try:
            duel_result = await duel("92001", "92002")
        finally:
            services.random.choice = duel_choice
            services.random.randint = duel_randint

        assert duel_result.winner_name == "artifactor"
        assert any("burn+" in line or "攻势暴涨" in line for line in duel_result.rounds)

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_panel_recent_actions_and_action_cooldowns(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian22.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("QXIAN_ACTION_COOLDOWN_ADVENTURE_SECONDS", "30")
    monkeypatch.setenv("QXIAN_ACTION_COOLDOWN_ENCOUNTER_SECONDS", "30")
    monkeypatch.setenv("QXIAN_ACTION_COOLDOWN_DUEL_SECONDS", "30")
    monkeypatch.setenv("QXIAN_ACTION_COOLDOWN_TRIAL_SECONDS", "30")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("93001", "routefinder")
        await create_player_if_missing("93002", "sparmate")
        repo = GameRepository(get_settings().database_url)

        panel = await get_player_panel("93001")
        panel_text = "\n".join(panel.lines)
        assert "下一步建议:" in panel_text
        assert "宗门列表" in panel_text

        await join_sect("93001", "青岚宗")
        panel_after_join = await get_player_panel("93001")
        assert any("下一步建议:" in line for line in panel_after_join.lines)

        import xianbot.services as services

        original_randint = services.random.randint
        services.random.randint = lambda a, b: 60
        try:
            result = await adventure("93001")
            assert result.roll_value >= 60
            try:
                await adventure("93001")
            except GameError as exc:
                assert str(exc).startswith("action_cooldown:adventure:")
            else:
                raise AssertionError("adventure cooldown should block immediate repeat")
        finally:
            services.random.randint = original_randint

        recent = await get_recent_actions("93001")
        recent_text = "\n".join(recent.lines)
        assert "最近记录:" in recent_text
        assert "历练" in recent_text

        await repo.update_player_stats(
            "93001",
            realm=Realm.FOUNDATION_2,
            cultivation_delta=1800,
            insight_delta=18,
            breakthrough_ready_delta=25,
            fortune_delta=8,
        )
        await repo.update_player_stats(
            "93002",
            realm=Realm.QI_4,
            cultivation_delta=700,
            insight_delta=6,
            breakthrough_ready_delta=12,
            fortune_delta=3,
        )

        sequence = iter([62, 38, 58, 40, 65, 36, 72, 34, 50])
        services.random.randint = lambda a, b: next(sequence, 50)
        try:
            duel_result = await duel("93001", "93002")
            assert duel_result.rounds
            try:
                await duel("93001", "93002")
            except GameError as exc:
                assert str(exc).startswith("action_cooldown:duel:")
            else:
                raise AssertionError("duel cooldown should block immediate repeat")
        finally:
            services.random.randint = original_randint

        recent_again = await get_recent_actions("93001")
        assert any("斗法" in line for line in recent_again.lines)

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_custom_dao_name_attributes_and_map_exploration(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian23.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("QXIAN_ACTION_COOLDOWN_ADVENTURE_SECONDS", "0")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        player, created = await create_player_if_missing("94001", "青玄", strict_name=True)
        assert created is True
        assert player.nickname == "青玄"

        try:
            await create_player_if_missing("94002", "青玄", strict_name=True)
        except GameError as exc:
            assert str(exc) == "dao_name_taken"
        else:
            raise AssertionError("duplicate custom dao name should be rejected")

        other, other_created = await create_player_if_missing("94002", "bad name with spaces", strict_name=False)
        assert other_created is True
        assert other.nickname.startswith("道友")

        panel = await get_player_panel("94001")
        panel_text = "\n".join(panel.lines)
        assert "【道友面板】青玄" in panel_text
        assert "【属性】" in panel_text
        assert "用途: 悟性影响修炼/炼丹/参悟" in panel_text
        assert "灵根" in panel_text

        attributes = await get_attribute_panel("94001")
        attribute_text = "\n".join(attributes.lines)
        assert "【人物属性】青玄" in attribute_text
        assert "物攻" in attribute_text
        assert "丹道" in attribute_text

        maps = await list_maps_for_player("94001")
        map_text = "\n".join(maps.lines)
        assert "青岚山 [可探索]" in map_text
        assert "雷泽 [未解锁: 需 1 转]" in map_text

        repo = GameRepository(get_settings().database_url)
        await join_sect("94001", "青岚宗")
        await repo.update_player_stats(
            "94001",
            root_affinity=Affinity.WOOD,
            cultivation_delta=400,
            insight_delta=6,
            breakthrough_ready_delta=8,
            fortune_delta=5,
        )

        import xianbot.services as services

        original_randint = services.random.randint
        original_random = services.random.random
        services.random.randint = lambda a, b: b
        services.random.random = lambda: 0.2
        try:
            result = await explore_map_area("94001", "青岚山")
        finally:
            services.random.randint = original_randint
            services.random.random = original_random

        assert result.area_name == "青岚山"
        assert result.roll_value > 100
        assert result.cultivation_delta > 0
        assert result.stamina_delta == -8
        assert result.attribute_used == "悟性"
        assert result.root_bonus > 0

        refreshed = await get_player_status("94001")
        assert refreshed is not None
        assert refreshed.stamina == 92
        assert refreshed.cultivation >= player.cultivation + result.cultivation_delta

        other_refreshed = await get_player_status("94002")
        assert other_refreshed is not None
        assert other_refreshed.stamina == 100
        assert other_refreshed.cultivation == 0

        recent = await get_recent_actions("94001")
        recent_text = "\n".join(recent.lines)
        assert "地图探索" in recent_text
        assert "青岚山" in recent_text

        try:
            await explore_map_area("94001", "雷泽")
        except GameError as exc:
            assert str(exc).startswith("map_locked:")
        else:
            raise AssertionError("locked map should reject low rebirth player")

    asyncio.run(scenario())
    get_settings.cache_clear()
