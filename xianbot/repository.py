from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
from typing import Any

import aiosqlite

from xianbot.database import resolve_sqlite_path
from xianbot.domain import (
    Affinity,
    DestinyType,
    MeditationMode,
    Player,
    Realm,
    RootTemperament,
    RootTrait,
    RootType,
)


class GameRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.db_path = resolve_sqlite_path(database_url)

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        connection = await aiosqlite.connect(self.db_path, timeout=30)
        connection.row_factory = aiosqlite.Row
        await connection.execute("PRAGMA foreign_keys=ON")
        await connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
        finally:
            await connection.close()

    def _player_insert_params(self, player: Player) -> tuple[Any, ...]:
        return (
            player.user_id,
            player.nickname,
            player.root_type.value,
            player.root_affinity.value,
            player.root_purity,
            player.root_temperament.value,
            player.root_trait.value,
            player.realm.value,
            player.cultivation,
            player.age,
            player.age_progress,
            player.lifespan,
            player.spirit_stones,
            player.fortune,
            player.stamina,
            player.comprehension,
            player.insight,
            player.breakthrough_ready,
            player.rebirth_count,
            player.soul_marks,
            player.legacy_points,
            None if player.destiny_type is None else player.destiny_type.value,
            player.destiny_level,
            player.sect_id,
            player.primary_method_id,
            player.equipped_artifact_id,
            player.meditation_started_at,
            player.meditation_until,
            player.meditation_minutes,
            player.meditation_reward,
            player.meditation_method_id,
            None if player.meditation_mode is None else player.meditation_mode.value,
            player.meditation_insight_reward,
            player.meditation_breakthrough_reward,
        )

    async def _fetchone(
        self,
        db: aiosqlite.Connection,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> aiosqlite.Row | None:
        cursor = await db.execute(query, params)
        return await cursor.fetchone()

    async def _fetchall(
        self,
        db: aiosqlite.Connection,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> list[aiosqlite.Row]:
        cursor = await db.execute(query, params)
        return await cursor.fetchall()

    async def _get_player_method_ids(
        self,
        db: aiosqlite.Connection,
        user_id: str,
    ) -> list[str]:
        rows = await self._fetchall(
            db,
            """
            SELECT method_id
            FROM player_methods
            WHERE user_id = ?
            ORDER BY acquired_at
            """,
            (user_id,),
        )
        return [str(row["method_id"]) for row in rows]

    async def _get_player_inventory_map(
        self,
        db: aiosqlite.Connection,
        user_id: str,
    ) -> dict[str, int]:
        rows = await self._fetchall(
            db,
            """
            SELECT item_id, quantity
            FROM inventories
            WHERE user_id = ? AND quantity > 0
            """,
            (user_id,),
        )
        return {str(row["item_id"]): int(row["quantity"]) for row in rows}

    async def get_player(self, user_id: str) -> Player | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT
                  user_id, nickname, root_type, root_affinity, root_purity, root_temperament,
                  root_trait, realm, cultivation, age, age_progress, lifespan,
                  spirit_stones, fortune, stamina, comprehension, insight, breakthrough_ready,
                  rebirth_count, soul_marks, legacy_points, destiny_type, destiny_level, sect_id, primary_method_id,
                  equipped_artifact_id,
                  meditation_started_at, meditation_until, meditation_minutes, meditation_reward,
                  meditation_method_id, meditation_mode, meditation_insight_reward,
                  meditation_breakthrough_reward
                FROM players
                WHERE user_id = ?
                """,
                (user_id,),
            )
            if row is None:
                return None
            method_ids = await self._get_player_method_ids(db, user_id)
            inventory = await self._get_player_inventory_map(db, user_id)

        return Player(
            user_id=row["user_id"],
            nickname=row["nickname"],
            root_type=RootType(row["root_type"]),
            root_affinity=Affinity(row["root_affinity"]),
            root_purity=int(row["root_purity"]),
            root_temperament=RootTemperament(row["root_temperament"]),
            root_trait=RootTrait(row["root_trait"]),
            realm=Realm(row["realm"]),
            cultivation=int(row["cultivation"]),
            age=int(row["age"]),
            age_progress=int(row["age_progress"]),
            lifespan=int(row["lifespan"]),
            spirit_stones=int(row["spirit_stones"]),
            fortune=int(row["fortune"]),
            stamina=int(row["stamina"]),
            comprehension=int(row["comprehension"]),
            insight=int(row["insight"]),
            breakthrough_ready=int(row["breakthrough_ready"]),
            rebirth_count=int(row["rebirth_count"]),
            soul_marks=int(row["soul_marks"]),
            legacy_points=int(row["legacy_points"]),
            destiny_type=None if row["destiny_type"] is None else DestinyType(row["destiny_type"]),
            destiny_level=int(row["destiny_level"]),
            sect_id=row["sect_id"],
            primary_method_id=row["primary_method_id"],
            equipped_artifact_id=row["equipped_artifact_id"],
            meditation_started_at=row["meditation_started_at"],
            meditation_until=row["meditation_until"],
            meditation_minutes=int(row["meditation_minutes"]),
            meditation_reward=int(row["meditation_reward"]),
            meditation_method_id=row["meditation_method_id"],
            meditation_mode=None
            if row["meditation_mode"] is None
            else MeditationMode(row["meditation_mode"]),
            meditation_insight_reward=int(row["meditation_insight_reward"]),
            meditation_breakthrough_reward=int(row["meditation_breakthrough_reward"]),
            method_ids=method_ids,
            inventory=inventory,
        )

    async def get_player_by_nickname(self, nickname: str) -> Player | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT user_id
                FROM players
                WHERE nickname = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (nickname,),
            )
        if row is None:
            return None
        return await self.get_player(str(row["user_id"]))

    async def create_player(self, player: Player) -> Player:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO players (
                  user_id, nickname, root_type, root_affinity, root_purity, root_temperament,
                  root_trait, realm, cultivation, age, age_progress, lifespan,
                  spirit_stones, fortune, stamina, comprehension, insight, breakthrough_ready,
                  rebirth_count, soul_marks, legacy_points, destiny_type, destiny_level, sect_id, primary_method_id,
                  equipped_artifact_id,
                  meditation_started_at, meditation_until, meditation_minutes, meditation_reward,
                  meditation_method_id, meditation_mode, meditation_insight_reward,
                  meditation_breakthrough_reward
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._player_insert_params(player),
            )
            await db.commit()
        return player

    async def create_player_with_starter_items(
        self,
        player: Player,
        starter_items: list[tuple[str, int]],
    ) -> bool:
        async with self._connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                cursor = await db.execute(
                    """
                INSERT OR IGNORE INTO players (
                  user_id, nickname, root_type, root_affinity, root_purity, root_temperament,
                  root_trait, realm, cultivation, age, age_progress, lifespan,
                  spirit_stones, fortune, stamina, comprehension, insight, breakthrough_ready,
                  rebirth_count, soul_marks, legacy_points, destiny_type, destiny_level, sect_id, primary_method_id,
                  equipped_artifact_id,
                  meditation_started_at, meditation_until, meditation_minutes, meditation_reward,
                  meditation_method_id, meditation_mode, meditation_insight_reward,
                  meditation_breakthrough_reward
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._player_insert_params(player),
                )
                created = cursor.rowcount > 0
                if created:
                    for item_id, quantity in starter_items:
                        await db.execute(
                            """
                            INSERT INTO inventories (user_id, item_id, quantity)
                            VALUES (?, ?, ?)
                            ON CONFLICT(user_id, item_id)
                            DO UPDATE SET quantity = quantity + excluded.quantity
                            """,
                            (player.user_id, item_id, quantity),
                        )
                await db.commit()
                return created
            except Exception:
                await db.rollback()
                raise

    async def update_player_stats(
        self,
        user_id: str,
        *,
        spirit_stones_delta: int = 0,
        cultivation_delta: int = 0,
        fortune_delta: int = 0,
        stamina_delta: int = 0,
        insight_delta: int = 0,
        breakthrough_ready_delta: int = 0,
        legacy_points_delta: int = 0,
        rebirth_count_delta: int = 0,
        soul_marks_delta: int = 0,
        lifespan_delta: int = 0,
        destiny_level_delta: int = 0,
        realm: Realm | None = None,
        root_type: RootType | None = None,
        root_affinity: Affinity | None = None,
        root_purity: int | None = None,
        root_temperament: RootTemperament | None = None,
        root_trait: RootTrait | None = None,
        destiny_type: DestinyType | None | object = None,
        primary_method_id: str | None | object = None,
        equipped_artifact_id: str | None | object = None,
        sect_id: str | None | object = None,
    ) -> None:
        updates: list[str] = []
        params: list[Any] = []

        if spirit_stones_delta:
            updates.append("spirit_stones = MAX(spirit_stones + ?, 0)")
            params.append(spirit_stones_delta)
        if cultivation_delta:
            updates.append("cultivation = MAX(cultivation + ?, 0)")
            params.append(cultivation_delta)
        if fortune_delta:
            updates.append("fortune = MAX(fortune + ?, 0)")
            params.append(fortune_delta)
        if stamina_delta:
            updates.append("stamina = MIN(MAX(stamina + ?, 0), 100)")
            params.append(stamina_delta)
        if insight_delta:
            updates.append("insight = MAX(insight + ?, 0)")
            params.append(insight_delta)
        if breakthrough_ready_delta:
            updates.append("breakthrough_ready = MIN(MAX(breakthrough_ready + ?, 0), 100)")
            params.append(breakthrough_ready_delta)
        if legacy_points_delta:
            updates.append("legacy_points = MAX(legacy_points + ?, 0)")
            params.append(legacy_points_delta)
        if rebirth_count_delta:
            updates.append("rebirth_count = MAX(rebirth_count + ?, 0)")
            params.append(rebirth_count_delta)
        if soul_marks_delta:
            updates.append("soul_marks = MAX(soul_marks + ?, 0)")
            params.append(soul_marks_delta)
        if lifespan_delta:
            updates.append("lifespan = MAX(lifespan + ?, 1)")
            params.append(lifespan_delta)
        if destiny_level_delta:
            updates.append("destiny_level = MAX(destiny_level + ?, 0)")
            params.append(destiny_level_delta)
        if realm is not None:
            updates.append("realm = ?")
            params.append(realm.value)
        if root_type is not None:
            updates.append("root_type = ?")
            params.append(root_type.value)
        if root_affinity is not None:
            updates.append("root_affinity = ?")
            params.append(root_affinity.value)
        if root_purity is not None:
            updates.append("root_purity = ?")
            params.append(root_purity)
        if root_temperament is not None:
            updates.append("root_temperament = ?")
            params.append(root_temperament.value)
        if root_trait is not None:
            updates.append("root_trait = ?")
            params.append(root_trait.value)
        if destiny_type is not None:
            updates.append("destiny_type = ?")
            params.append(destiny_type.value)
        if primary_method_id is not None:
            updates.append("primary_method_id = ?")
            params.append(primary_method_id)
        if equipped_artifact_id is not None:
            updates.append("equipped_artifact_id = ?")
            params.append(equipped_artifact_id)
        if sect_id is not None:
            updates.append("sect_id = ?")
            params.append(sect_id)

        if not updates:
            return

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)

        async with self._connect() as db:
            await db.execute(
                f"UPDATE players SET {', '.join(updates)} WHERE user_id = ?",
                tuple(params),
            )
            await db.commit()

    async def apply_lifespan_progress(
        self,
        user_id: str,
        *,
        progress_delta: int = 0,
        lifespan_delta: int = 0,
    ) -> None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT age, age_progress, lifespan
                FROM players
                WHERE user_id = ?
                """,
                (user_id,),
            )
            if row is None:
                return

            total_progress = int(row["age_progress"]) + progress_delta
            age_delta = max(0, total_progress // 12)
            remaining_progress = max(0, total_progress % 12)
            new_age = int(row["age"]) + age_delta
            new_lifespan = max(1, int(row["lifespan"]) + lifespan_delta)
            if new_lifespan < new_age:
                new_lifespan = new_age

            await db.execute(
                """
                UPDATE players
                SET
                  age = ?,
                  age_progress = ?,
                  lifespan = ?,
                  updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (new_age, remaining_progress, new_lifespan, user_id),
            )
            await db.commit()

    async def reset_player_for_rebirth(self, user_id: str) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE players
                SET
                  age = 16,
                  age_progress = 0,
                  stamina = 100,
                  insight = 0,
                  breakthrough_ready = 0,
                  sect_id = NULL,
                  primary_method_id = NULL,
                  equipped_artifact_id = NULL,
                  meditation_started_at = NULL,
                  meditation_until = NULL,
                  meditation_minutes = 0,
                  meditation_reward = 0,
                  meditation_method_id = NULL,
                  meditation_mode = NULL,
                  meditation_insight_reward = 0,
                  meditation_breakthrough_reward = 0,
                  updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (user_id,),
            )
            await db.execute(
                """
                UPDATE player_methods
                SET equipped = 0
                WHERE user_id = ?
                """,
                (user_id,),
            )
            await db.commit()

    async def set_player_meditation(
        self,
        user_id: str,
        *,
        started_at: str,
        until: str,
        minutes: int,
        reward: int,
        method_id: str | None,
        mode: MeditationMode,
        insight_reward: int,
        breakthrough_reward: int,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE players
                SET
                  meditation_started_at = ?,
                  meditation_until = ?,
                  meditation_minutes = ?,
                  meditation_reward = ?,
                  meditation_method_id = ?,
                  meditation_mode = ?,
                  meditation_insight_reward = ?,
                  meditation_breakthrough_reward = ?,
                  updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (
                    started_at,
                    until,
                    minutes,
                    reward,
                    method_id,
                    mode.value,
                    insight_reward,
                    breakthrough_reward,
                    user_id,
                ),
            )
            await db.commit()

    async def clear_player_meditation(self, user_id: str) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE players
                SET
                  meditation_started_at = NULL,
                  meditation_until = NULL,
                  meditation_minutes = 0,
                  meditation_reward = 0,
                  meditation_method_id = NULL,
                  meditation_mode = NULL,
                  meditation_insight_reward = 0,
                  meditation_breakthrough_reward = 0,
                  updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (user_id,),
            )
            await db.commit()

    async def get_today_signin(self, user_id: str, sign_date: str) -> aiosqlite.Row | None:
        async with self._connect() as db:
            return await self._fetchone(
                db,
                """
                SELECT user_id, sign_date, base_reward, pool_reward, fortune_roll
                FROM daily_signins
                WHERE user_id = ? AND sign_date = ?
                """,
                (user_id, sign_date),
            )

    async def get_fortune_pool_amount(self) -> int:
        async with self._connect() as db:
            row = await self._fetchone(db, "SELECT amount FROM fortune_pool WHERE id = 1")
        return 0 if row is None else int(row["amount"])

    async def adjust_fortune_pool(self, delta: int) -> int:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE fortune_pool
                SET amount = MAX(amount + ?, 0), updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (delta,),
            )
            await db.commit()
            row = await self._fetchone(db, "SELECT amount FROM fortune_pool WHERE id = 1")
        return 0 if row is None else int(row["amount"])

    async def record_signin(
        self,
        user_id: str,
        sign_date: str,
        base_reward: int,
        pool_reward: int,
        fortune_roll: int,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO daily_signins (
                  user_id, sign_date, base_reward, pool_reward, fortune_roll
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, sign_date, base_reward, pool_reward, fortune_roll),
            )
            await db.commit()

    async def claim_signin(
        self,
        user_id: str,
        sign_date: str,
        *,
        base_reward: int,
        cultivation_gain: int,
        fortune_roll: int,
        pool_release_rate: float,
        stamina_delta: int,
    ) -> int | None:
        async with self._connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                existing = await self._fetchone(
                    db,
                    """
                    SELECT 1
                    FROM daily_signins
                    WHERE user_id = ? AND sign_date = ?
                    """,
                    (user_id, sign_date),
                )
                if existing is not None:
                    await db.rollback()
                    return None

                pool_row = await self._fetchone(
                    db,
                    "SELECT amount FROM fortune_pool WHERE id = 1",
                )
                current_pool = 0 if pool_row is None else int(pool_row["amount"])
                releasable = int(current_pool * pool_release_rate)
                pool_reward = 0
                if releasable > 0:
                    if fortune_roll >= 96:
                        pool_reward = max(1, int(releasable * 0.60))
                    elif fortune_roll >= 80:
                        pool_reward = max(1, int(releasable * 0.35))
                    elif fortune_roll >= 50:
                        pool_reward = max(1, int(releasable * 0.20))
                    else:
                        pool_reward = max(1, int(releasable * 0.10))
                    pool_reward = min(pool_reward, current_pool)
                    await db.execute(
                        """
                        UPDATE fortune_pool
                        SET amount = amount - ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = 1
                        """,
                        (pool_reward,),
                    )

                await db.execute(
                    """
                    INSERT INTO daily_signins (
                      user_id, sign_date, base_reward, pool_reward, fortune_roll
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, sign_date, base_reward, pool_reward, fortune_roll),
                )
                await db.execute(
                    """
                    UPDATE players
                    SET
                      spirit_stones = spirit_stones + ?,
                      cultivation = cultivation + ?,
                      stamina = MIN(MAX(stamina + ?, 0), 100),
                      updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                    """,
                    (base_reward + pool_reward, cultivation_gain, stamina_delta, user_id),
                )
                await db.commit()
                return pool_reward
            except Exception:
                await db.rollback()
                raise

    async def list_accessible_sects(self, rebirth_count: int) -> list[dict[str, Any]]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT id, name, theme, description, required_rebirth_count
                FROM sects
                WHERE required_rebirth_count <= ?
                ORDER BY required_rebirth_count, name
                """,
                (rebirth_count,),
            )
        return [dict(row) for row in rows]

    async def get_sect_by_name(self, name: str) -> dict[str, Any] | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT id, name, theme, description, required_rebirth_count
                FROM sects
                WHERE name = ?
                """,
                (name,),
            )
        return None if row is None else dict(row)

    async def get_sect_by_id(self, sect_id: str) -> dict[str, Any] | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT id, name, theme, description, required_rebirth_count
                FROM sects
                WHERE id = ?
                """,
                (sect_id,),
            )
        return None if row is None else dict(row)

    async def set_player_sect(self, user_id: str, sect_id: str | None) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE players
                SET sect_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (sect_id, user_id),
            )
            await db.commit()

    async def get_player_methods(self, user_id: str) -> list[dict[str, Any]]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT
                  cm.id,
                  cm.name,
                  cm.realm_requirement,
                  cm.grade,
                  cm.method_type,
                  cm.affinity,
                  cm.style,
                  cm.practice_bonus,
                  cm.breakthrough_bonus,
                  cm.insight_bonus,
                  pm.mastery,
                  pm.equipped,
                  cm.source_sect_id,
                  cm.required_rebirth_count,
                  cm.description
                FROM cultivation_methods cm
                INNER JOIN player_methods pm ON pm.method_id = cm.id
                WHERE pm.user_id = ?
                ORDER BY pm.equipped DESC, pm.mastery DESC, pm.acquired_at
                """,
                (user_id,),
        )
        return [dict(row) for row in rows]

    async def get_player_method_by_name(
        self,
        user_id: str,
        method_name: str,
    ) -> dict[str, Any] | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT
                  cm.id,
                  cm.name,
                  cm.realm_requirement,
                  cm.grade,
                  cm.method_type,
                  cm.affinity,
                  cm.style,
                  cm.practice_bonus,
                  cm.breakthrough_bonus,
                  cm.insight_bonus,
                  pm.mastery,
                  pm.equipped,
                  cm.source_sect_id,
                  cm.required_rebirth_count,
                  cm.description
                FROM cultivation_methods cm
                INNER JOIN player_methods pm ON pm.method_id = cm.id
                WHERE pm.user_id = ? AND cm.name = ?
                """,
                (user_id, method_name),
            )
        return None if row is None else dict(row)

    async def get_sect_methods(
        self,
        sect_id: str,
        rebirth_count: int,
    ) -> list[dict[str, Any]]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT
                  id, name, realm_requirement, grade, method_type, affinity, style,
                  practice_bonus, breakthrough_bonus, insight_bonus,
                  source_sect_id, required_rebirth_count, description
                FROM cultivation_methods
                WHERE source_sect_id = ? AND required_rebirth_count <= ?
                ORDER BY required_rebirth_count, realm_requirement
                """,
                (sect_id, rebirth_count),
            )
        return [dict(row) for row in rows]

    async def grant_player_method(self, user_id: str, method_id: str) -> bool:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO player_methods (user_id, method_id, mastery, equipped)
                VALUES (?, ?, 0, 0)
                """,
                (user_id, method_id),
            )
            await db.commit()
        return cursor.rowcount > 0

    async def add_method_mastery(self, user_id: str, method_id: str, amount: int) -> None:
        if amount <= 0:
            return
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE player_methods
                SET mastery = mastery + ?
                WHERE user_id = ? AND method_id = ?
                """,
                (amount, user_id, method_id),
            )
            await db.commit()

    async def set_primary_method(self, user_id: str, method_id: str) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE player_methods
                SET equipped = CASE WHEN method_id = ? THEN 1 ELSE 0 END
                WHERE user_id = ?
                """,
                (method_id, user_id),
            )
            await db.execute(
                """
                UPDATE players
                SET primary_method_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (method_id, user_id),
            )
            await db.commit()

    async def get_item_by_name(self, item_name: str) -> dict[str, Any] | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT
                  id, name, item_type, rarity, description,
                  base_price, consumable, tradable
                FROM items
                WHERE name = ?
                """,
                (item_name,),
            )
        return None if row is None else dict(row)

    async def get_item_by_id(self, item_id: str) -> dict[str, Any] | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT
                  id, name, item_type, rarity, description,
                  base_price, consumable, tradable
                FROM items
                WHERE id = ?
                """,
                (item_id,),
            )
        return None if row is None else dict(row)

    async def get_item_by_name_fuzzy(self, item_name: str) -> dict[str, Any] | None:
        return await self.get_item_by_name(item_name)

    async def list_inventory(self, user_id: str) -> list[dict[str, Any]]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT
                  i.item_id,
                  it.name,
                  it.item_type,
                  it.rarity,
                  it.description,
                  i.quantity,
                  it.tradable
                FROM inventories i
                INNER JOIN items it ON it.id = i.item_id
                WHERE i.user_id = ? AND i.quantity > 0
                ORDER BY it.item_type, it.rarity DESC, it.name
                """,
                (user_id,),
            )
        return [dict(row) for row in rows]

    async def add_inventory_item(self, user_id: str, item_id: str, quantity: int) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO inventories (user_id, item_id, quantity)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, item_id)
                DO UPDATE SET quantity = quantity + excluded.quantity
                """,
                (user_id, item_id, quantity),
            )
            item = await self._fetchone(
                db,
                """
                SELECT item_type
                FROM items
                WHERE id = ?
                """,
                (item_id,),
            )
            if item is not None and str(item["item_type"]) == "法宝":
                await db.execute(
                    """
                    INSERT OR IGNORE INTO player_artifacts (user_id, item_id, mastery, equipped)
                    VALUES (?, ?, 0, 0)
                    """,
                    (user_id, item_id),
                )
            await db.commit()

    async def list_player_artifacts(self, user_id: str) -> list[dict[str, Any]]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT
                  pa.item_id,
                  it.name,
                  it.rarity,
                  it.description,
                  pa.mastery,
                  CASE WHEN p.equipped_artifact_id = pa.item_id THEN 1 ELSE pa.equipped END AS equipped
                FROM player_artifacts pa
                INNER JOIN items it ON it.id = pa.item_id
                INNER JOIN players p ON p.user_id = pa.user_id
                WHERE pa.user_id = ?
                ORDER BY equipped DESC, pa.mastery DESC, it.rarity DESC, it.name
                """,
                (user_id,),
            )
        return [dict(row) for row in rows]

    async def get_equipped_artifact(self, user_id: str) -> dict[str, Any] | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT
                  pa.item_id,
                  it.name,
                  it.rarity,
                  it.description,
                  pa.mastery,
                  1 AS equipped
                FROM players p
                INNER JOIN player_artifacts pa
                  ON pa.user_id = p.user_id AND pa.item_id = p.equipped_artifact_id
                INNER JOIN items it ON it.id = pa.item_id
                WHERE p.user_id = ?
                """,
                (user_id,),
            )
        return None if row is None else dict(row)

    async def get_player_artifact_by_name(
        self,
        user_id: str,
        artifact_name: str,
    ) -> dict[str, Any] | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT
                  pa.item_id,
                  it.name,
                  it.rarity,
                  it.description,
                  pa.mastery,
                  CASE WHEN p.equipped_artifact_id = pa.item_id THEN 1 ELSE pa.equipped END AS equipped
                FROM player_artifacts pa
                INNER JOIN items it ON it.id = pa.item_id
                INNER JOIN players p ON p.user_id = pa.user_id
                INNER JOIN inventories inv
                  ON inv.user_id = pa.user_id AND inv.item_id = pa.item_id AND inv.quantity > 0
                WHERE pa.user_id = ? AND it.name = ? AND it.item_type = '法宝'
                """,
                (user_id, artifact_name),
            )
        return None if row is None else dict(row)

    async def set_equipped_artifact(self, user_id: str, item_id: str) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE player_artifacts
                SET equipped = CASE WHEN item_id = ? THEN 1 ELSE 0 END
                WHERE user_id = ?
                """,
                (item_id, user_id),
            )
            await db.execute(
                """
                UPDATE players
                SET equipped_artifact_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (item_id, user_id),
            )
            await db.commit()

    async def add_artifact_mastery(self, user_id: str, item_id: str, amount: int) -> None:
        if amount <= 0:
            return
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE player_artifacts
                SET mastery = mastery + ?
                WHERE user_id = ? AND item_id = ?
                """,
                (amount, user_id, item_id),
            )
            await db.commit()

    async def remove_inventory_item(self, user_id: str, item_id: str, quantity: int) -> bool:
        if quantity <= 0:
            return False
        async with self._connect() as db:
            cursor = await db.execute(
                """
                UPDATE inventories
                SET quantity = quantity - ?
                WHERE user_id = ? AND item_id = ? AND quantity >= ?
                """,
                (quantity, user_id, item_id, quantity),
            )
            if cursor.rowcount <= 0:
                await db.rollback()
                return False
            await db.execute(
                """
                DELETE FROM inventories
                WHERE user_id = ? AND item_id = ? AND quantity <= 0
                """,
                (user_id, item_id),
            )
            await db.commit()
        return True

    async def consume_inventory_items(
        self,
        user_id: str,
        items: list[tuple[str, int]],
    ) -> bool:
        async with self._connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                for item_id, quantity in items:
                    if quantity <= 0:
                        await db.rollback()
                        return False
                    cursor = await db.execute(
                        """
                        UPDATE inventories
                        SET quantity = quantity - ?
                        WHERE user_id = ? AND item_id = ? AND quantity >= ?
                        """,
                        (quantity, user_id, item_id, quantity),
                    )
                    if cursor.rowcount <= 0:
                        await db.rollback()
                        return False
                for item_id, _ in items:
                    await db.execute(
                        """
                        DELETE FROM inventories
                        WHERE user_id = ? AND item_id = ? AND quantity <= 0
                        """,
                        (user_id, item_id),
                    )
                await db.commit()
                return True
            except Exception:
                await db.rollback()
                raise

    async def record_adventure(
        self,
        user_id: str,
        *,
        action_type: str = "adventure",
        roll_value: int,
        outcome: str,
        reward_spirit_stones: int,
        reward_cultivation: int,
        reward_item_id: str | None,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO adventure_logs (
                  user_id, action_type, roll_value, outcome,
                  reward_spirit_stones, reward_cultivation, reward_item_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    action_type,
                    roll_value,
                    outcome,
                    reward_spirit_stones,
                    reward_cultivation,
                    reward_item_id,
                ),
            )
            await db.commit()

    async def list_recent_actions(self, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT
                  action_type,
                  roll_value,
                  outcome,
                  reward_spirit_stones,
                  reward_cultivation,
                  reward_item_id,
                  created_at
                FROM adventure_logs
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
        return [dict(row) for row in rows]

    async def get_action_cooldown(self, user_id: str, action_type: str) -> dict[str, Any] | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT user_id, action_type, available_at, updated_at
                FROM player_action_cooldowns
                WHERE user_id = ? AND action_type = ?
                """,
                (user_id, action_type),
            )
        return None if row is None else dict(row)

    async def set_action_cooldown(self, user_id: str, action_type: str, available_at: str) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO player_action_cooldowns (
                  user_id, action_type, available_at, updated_at
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, action_type)
                DO UPDATE SET
                  available_at = excluded.available_at,
                  updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, action_type, available_at),
            )
            await db.commit()

    async def get_world_state(self, state_date: str) -> dict[str, Any] | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT
                  state_date, title, description, adventure_bonus, meditation_bonus,
                  encounter_bonus, fortune_bonus, lifespan_bonus
                FROM world_states
                WHERE state_date = ?
                """,
                (state_date,),
            )
        return None if row is None else dict(row)

    async def save_world_state(
        self,
        state_date: str,
        title: str,
        description: str,
        adventure_bonus: int,
        meditation_bonus: float,
        encounter_bonus: int,
        fortune_bonus: int,
        lifespan_bonus: int,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO world_states (
                  state_date, title, description, adventure_bonus, meditation_bonus,
                  encounter_bonus, fortune_bonus, lifespan_bonus
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state_date,
                    title,
                    description,
                    adventure_bonus,
                    meditation_bonus,
                    encounter_bonus,
                    fortune_bonus,
                    lifespan_bonus,
                ),
            )
            await db.commit()

    async def get_active_market_listings(self, limit: int = 20) -> list[dict[str, Any]]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT
                  ml.id,
                  ml.seller_user_id,
                  p.nickname AS seller_name,
                  ml.item_id,
                  it.name AS item_name,
                  ml.quantity,
                  ml.unit_price,
                  ml.status,
                  ml.created_at
                FROM market_listings ml
                INNER JOIN players p ON p.user_id = ml.seller_user_id
                INNER JOIN items it ON it.id = ml.item_id
                WHERE ml.status = 'active'
                ORDER BY ml.id ASC
                LIMIT ?
                """,
                (limit,),
            )
        return [dict(row) for row in rows]

    async def create_market_listing(
        self,
        seller_user_id: str,
        item_id: str,
        quantity: int,
        unit_price: int,
    ) -> int:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                INSERT INTO market_listings (
                  seller_user_id, item_id, quantity, unit_price, status
                ) VALUES (?, ?, ?, ?, 'active')
                """,
                (seller_user_id, item_id, quantity, unit_price),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def get_world_event(self, event_date: str) -> dict[str, Any] | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT
                  event_date, event_key, title, description, objective,
                  target_progress, current_progress,
                  reward_spirit_stones, reward_cultivation, reward_insight,
                  reward_item_id, reward_item_quantity,
                  bonus_text, participation_hint, completed_at
                FROM world_events
                WHERE event_date = ?
                """,
                (event_date,),
            )
        return None if row is None else dict(row)

    async def save_world_event(
        self,
        *,
        event_date: str,
        event_key: str,
        title: str,
        description: str,
        objective: str,
        target_progress: int,
        current_progress: int,
        reward_spirit_stones: int,
        reward_cultivation: int,
        reward_insight: int,
        reward_item_id: str | None,
        reward_item_quantity: int,
        bonus_text: str,
        participation_hint: str,
        completed_at: str | None = None,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO world_events (
                  event_date, event_key, title, description, objective,
                  target_progress, current_progress,
                  reward_spirit_stones, reward_cultivation, reward_insight,
                  reward_item_id, reward_item_quantity,
                  bonus_text, participation_hint, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_date,
                    event_key,
                    title,
                    description,
                    objective,
                    target_progress,
                    current_progress,
                    reward_spirit_stones,
                    reward_cultivation,
                    reward_insight,
                    reward_item_id,
                    reward_item_quantity,
                    bonus_text,
                    participation_hint,
                    completed_at,
                ),
            )
            await db.commit()

    async def get_world_event_contribution(self, event_date: str, user_id: str) -> dict[str, Any] | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT event_date, user_id, contribution, claimed, updated_at
                FROM world_event_contributions
                WHERE event_date = ? AND user_id = ?
                """,
                (event_date, user_id),
            )
        return None if row is None else dict(row)

    async def contribute_world_event(
        self,
        *,
        event_date: str,
        user_id: str,
        contribution: int,
    ) -> dict[str, Any] | None:
        if contribution <= 0:
            return None
        async with self._connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                event_row = await self._fetchone(
                    db,
                    """
                    SELECT
                      target_progress, current_progress, completed_at
                    FROM world_events
                    WHERE event_date = ?
                    """,
                    (event_date,),
                )
                if event_row is None:
                    await db.rollback()
                    return None

                current_progress = int(event_row["current_progress"])
                target_progress = int(event_row["target_progress"])
                next_progress = min(target_progress, current_progress + contribution)
                completed_at = event_row["completed_at"]
                if completed_at is None and next_progress >= target_progress:
                    await db.execute(
                        """
                        UPDATE world_events
                        SET current_progress = ?, completed_at = CURRENT_TIMESTAMP
                        WHERE event_date = ?
                        """,
                        (next_progress, event_date),
                    )
                else:
                    await db.execute(
                        """
                        UPDATE world_events
                        SET current_progress = ?
                        WHERE event_date = ?
                        """,
                        (next_progress, event_date),
                    )

                await db.execute(
                    """
                    INSERT INTO world_event_contributions (
                      event_date, user_id, contribution, claimed, updated_at
                    ) VALUES (?, ?, ?, 0, CURRENT_TIMESTAMP)
                    ON CONFLICT(event_date, user_id)
                    DO UPDATE SET
                      contribution = contribution + excluded.contribution,
                      updated_at = CURRENT_TIMESTAMP
                    """,
                    (event_date, user_id, contribution),
                )
                await db.commit()
                return {
                    "event_date": event_date,
                    "user_id": user_id,
                    "contribution": contribution,
                    "current_progress": next_progress,
                    "target_progress": target_progress,
                    "completed": next_progress >= target_progress,
                }
            except Exception:
                await db.rollback()
                raise

    async def claim_world_event_reward(self, *, event_date: str, user_id: str) -> dict[str, Any] | None:
        async with self._connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                event_row = await self._fetchone(
                    db,
                    """
                    SELECT
                      title, completed_at,
                      reward_spirit_stones, reward_cultivation, reward_insight,
                      reward_item_id, reward_item_quantity
                    FROM world_events
                    WHERE event_date = ?
                    """,
                    (event_date,),
                )
                if event_row is None or event_row["completed_at"] is None:
                    await db.rollback()
                    return None

                contribution_row = await self._fetchone(
                    db,
                    """
                    SELECT contribution, claimed
                    FROM world_event_contributions
                    WHERE event_date = ? AND user_id = ?
                    """,
                    (event_date, user_id),
                )
                if contribution_row is None:
                    await db.rollback()
                    return {"reason": "not_participated"}
                if int(contribution_row["claimed"]) == 1:
                    await db.rollback()
                    return {"reason": "already_claimed"}

                reward_spirit_stones = int(event_row["reward_spirit_stones"])
                reward_cultivation = int(event_row["reward_cultivation"])
                reward_insight = int(event_row["reward_insight"])
                reward_item_id = event_row["reward_item_id"]
                reward_item_quantity = int(event_row["reward_item_quantity"])

                await db.execute(
                    """
                    UPDATE players
                    SET
                      spirit_stones = spirit_stones + ?,
                      cultivation = cultivation + ?,
                      insight = insight + ?,
                      updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                    """,
                    (reward_spirit_stones, reward_cultivation, reward_insight, user_id),
                )
                if reward_item_id is not None and reward_item_quantity > 0:
                    await db.execute(
                        """
                        INSERT INTO inventories (user_id, item_id, quantity)
                        VALUES (?, ?, ?)
                        ON CONFLICT(user_id, item_id)
                        DO UPDATE SET quantity = quantity + excluded.quantity
                        """,
                        (user_id, reward_item_id, reward_item_quantity),
                    )

                await db.execute(
                    """
                    UPDATE world_event_contributions
                    SET claimed = 1, updated_at = CURRENT_TIMESTAMP
                    WHERE event_date = ? AND user_id = ?
                    """,
                    (event_date, user_id),
                )
                await db.commit()
                return {
                    "title": str(event_row["title"]),
                    "reward_spirit_stones": reward_spirit_stones,
                    "reward_cultivation": reward_cultivation,
                    "reward_insight": reward_insight,
                    "reward_item_id": reward_item_id,
                    "reward_item_quantity": reward_item_quantity,
                    "contribution": int(contribution_row["contribution"]),
                }
            except Exception:
                await db.rollback()
                raise

    async def create_market_listing_from_inventory(
        self,
        seller_user_id: str,
        item_id: str,
        quantity: int,
        unit_price: int,
    ) -> int | None:
        async with self._connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                remove_cursor = await db.execute(
                    """
                    UPDATE inventories
                    SET quantity = quantity - ?
                    WHERE user_id = ? AND item_id = ? AND quantity >= ?
                    """,
                    (quantity, seller_user_id, item_id, quantity),
                )
                if remove_cursor.rowcount <= 0:
                    await db.rollback()
                    return None
                await db.execute(
                    """
                    DELETE FROM inventories
                    WHERE user_id = ? AND item_id = ? AND quantity <= 0
                    """,
                    (seller_user_id, item_id),
                )
                cursor = await db.execute(
                    """
                    INSERT INTO market_listings (
                      seller_user_id, item_id, quantity, unit_price, status
                    ) VALUES (?, ?, ?, ?, 'active')
                    """,
                    (seller_user_id, item_id, quantity, unit_price),
                )
                await db.commit()
                return int(cursor.lastrowid)
            except Exception:
                await db.rollback()
                raise

    async def get_market_listing(self, listing_id: int) -> dict[str, Any] | None:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT
                  ml.id,
                  ml.seller_user_id,
                  p.nickname AS seller_name,
                  ml.item_id,
                  it.name AS item_name,
                  ml.quantity,
                  ml.unit_price,
                  ml.status,
                  ml.created_at
                FROM market_listings ml
                INNER JOIN players p ON p.user_id = ml.seller_user_id
                INNER JOIN items it ON it.id = ml.item_id
                WHERE ml.id = ?
                """,
                (listing_id,),
            )
        return None if row is None else dict(row)

    async def mark_market_listing_sold(self, listing_id: int, buyer_user_id: str) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE market_listings
                SET status = 'sold', buyer_user_id = ?, sold_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (buyer_user_id, listing_id),
            )
            await db.commit()

    async def purchase_market_listing(
        self,
        buyer_user_id: str,
        listing_id: int,
        fee_rate: float,
    ) -> dict[str, Any] | None:
        async with self._connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                listing = await self._fetchone(
                    db,
                    """
                    SELECT
                      ml.id,
                      ml.seller_user_id,
                      p.nickname AS seller_name,
                      ml.item_id,
                      it.name AS item_name,
                      ml.quantity,
                      ml.unit_price,
                      ml.status
                    FROM market_listings ml
                    INNER JOIN players p ON p.user_id = ml.seller_user_id
                    INNER JOIN items it ON it.id = ml.item_id
                    WHERE ml.id = ?
                    """,
                    (listing_id,),
                )
                if listing is None:
                    await db.rollback()
                    return None
                if str(listing["status"]) != "active":
                    await db.rollback()
                    return {"reason": "listing_unavailable"}
                if str(listing["seller_user_id"]) == buyer_user_id:
                    await db.rollback()
                    return {"reason": "cannot_buy_own_listing"}

                total_price = int(listing["quantity"]) * int(listing["unit_price"])
                fee = max(1, int(total_price * fee_rate))
                seller_income = total_price - fee

                buyer_cursor = await db.execute(
                    """
                    UPDATE players
                    SET spirit_stones = spirit_stones - ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND spirit_stones >= ?
                    """,
                    (total_price, buyer_user_id, total_price),
                )
                if buyer_cursor.rowcount <= 0:
                    await db.rollback()
                    return {"reason": "not_enough_spirit_stones"}

                sold_cursor = await db.execute(
                    """
                    UPDATE market_listings
                    SET status = 'sold', buyer_user_id = ?, sold_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'active'
                    """,
                    (buyer_user_id, listing_id),
                )
                if sold_cursor.rowcount <= 0:
                    await db.rollback()
                    return {"reason": "listing_unavailable"}

                await db.execute(
                    """
                    UPDATE players
                    SET spirit_stones = spirit_stones + ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                    """,
                    (seller_income, str(listing["seller_user_id"])),
                )
                await db.execute(
                    """
                    UPDATE fortune_pool
                    SET amount = amount + ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                    """,
                    (fee,),
                )
                await db.execute(
                    """
                    INSERT INTO inventories (user_id, item_id, quantity)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, item_id)
                    DO UPDATE SET quantity = quantity + excluded.quantity
                    """,
                    (buyer_user_id, str(listing["item_id"]), int(listing["quantity"])),
                )
                await db.commit()
                return {
                    "listing_id": int(listing["id"]),
                    "item_name": str(listing["item_name"]),
                    "quantity": int(listing["quantity"]),
                    "total_price": total_price,
                    "fee": fee,
                    "seller_name": str(listing["seller_name"]),
                }
            except Exception:
                await db.rollback()
                raise

    async def list_top_players(self, limit: int = 10) -> list[dict[str, Any]]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT
                  nickname,
                  realm,
                  cultivation,
                  spirit_stones,
                  rebirth_count
                FROM players
                ORDER BY cultivation DESC, spirit_stones DESC
                LIMIT ?
                """,
                (limit,),
            )
        return [dict(row) for row in rows]

    async def record_rebirth(
        self,
        user_id: str,
        rebirth_count: int,
        previous_realm: Realm,
        legacy_points_gained: int,
        soul_marks_consumed: int,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO rebirth_logs (
                  user_id, rebirth_count, previous_realm,
                  legacy_points_gained, soul_marks_consumed
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    rebirth_count,
                    previous_realm.value,
                    legacy_points_gained,
                    soul_marks_consumed,
                ),
            )
            await db.commit()

    async def save_legacy_unlocks(self, user_id: str, unlock_keys: list[str]) -> None:
        if not unlock_keys:
            return
        async with self._connect() as db:
            await db.executemany(
                """
                INSERT OR IGNORE INTO legacy_unlocks (user_id, unlock_key)
                VALUES (?, ?)
                """,
                [(user_id, unlock_key) for unlock_key in unlock_keys],
            )
            await db.commit()
