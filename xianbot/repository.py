from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
from typing import Any

import aiosqlite

from xianbot.database import resolve_sqlite_path
from xianbot.domain import Affinity, MeditationMode, Player, Realm, RootTemperament, RootTrait, RootType


class GameRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.db_path = resolve_sqlite_path(database_url)

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        connection = await aiosqlite.connect(self.db_path)
        connection.row_factory = aiosqlite.Row
        try:
            yield connection
        finally:
            await connection.close()

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
                  rebirth_count, soul_marks, legacy_points, sect_id, primary_method_id,
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
            sect_id=row["sect_id"],
            primary_method_id=row["primary_method_id"],
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

    async def create_player(self, player: Player) -> Player:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO players (
                  user_id, nickname, root_type, root_affinity, root_purity, root_temperament,
                  root_trait, realm, cultivation, age, age_progress, lifespan,
                  spirit_stones, fortune, stamina, comprehension, insight, breakthrough_ready,
                  rebirth_count, soul_marks, legacy_points, sect_id, primary_method_id,
                  meditation_started_at, meditation_until, meditation_minutes, meditation_reward,
                  meditation_method_id, meditation_mode, meditation_insight_reward,
                  meditation_breakthrough_reward
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
                    player.sect_id,
                    player.primary_method_id,
                    player.meditation_started_at,
                    player.meditation_until,
                    player.meditation_minutes,
                    player.meditation_reward,
                    player.meditation_method_id,
                    None if player.meditation_mode is None else player.meditation_mode.value,
                    player.meditation_insight_reward,
                    player.meditation_breakthrough_reward,
                ),
            )
            await db.commit()
        return player

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
        realm: Realm | None = None,
        root_type: RootType | None = None,
        root_affinity: Affinity | None = None,
        root_purity: int | None = None,
        root_temperament: RootTemperament | None = None,
        root_trait: RootTrait | None = None,
        primary_method_id: str | None | object = None,
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
        if primary_method_id is not None:
            updates.append("primary_method_id = ?")
            params.append(primary_method_id)
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
            await db.commit()

    async def remove_inventory_item(self, user_id: str, item_id: str, quantity: int) -> bool:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT quantity
                FROM inventories
                WHERE user_id = ? AND item_id = ?
                """,
                (user_id, item_id),
            )
            if row is None or int(row["quantity"]) < quantity:
                return False
            await db.execute(
                """
                UPDATE inventories
                SET quantity = quantity - ?
                WHERE user_id = ? AND item_id = ?
                """,
                (quantity, user_id, item_id),
            )
            await db.execute(
                """
                DELETE FROM inventories
                WHERE user_id = ? AND item_id = ? AND quantity <= 0
                """,
                (user_id, item_id),
            )
            await db.commit()
        return True

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
