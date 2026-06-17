from __future__ import annotations

from typing import Any

import aiosqlite

from xianbot.database import resolve_sqlite_path
from xianbot.domain import Player, Realm, RootType


class GameRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.db_path = resolve_sqlite_path(database_url)

    async def _connect(self) -> aiosqlite.Connection:
        connection = await aiosqlite.connect(self.db_path)
        connection.row_factory = aiosqlite.Row
        return connection

    async def _fetchone(
        self,
        db: aiosqlite.Connection,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> aiosqlite.Row | None:
        cursor = await db.execute(query, params)
        return await cursor.fetchone()

    async def get_player(self, user_id: str) -> Player | None:
        async with await self._connect() as db:
            row = await self._fetchone(
                db,
                """
                SELECT
                  user_id, nickname, root_type, realm, cultivation, age, lifespan,
                  spirit_stones, fortune, stamina, comprehension, rebirth_count,
                  soul_marks, legacy_points, sect_id
                FROM players
                WHERE user_id = ?
                """,
                (user_id,),
            )
        if row is None:
            return None
        return Player(
            user_id=row["user_id"],
            nickname=row["nickname"],
            root_type=RootType(row["root_type"]),
            realm=Realm(row["realm"]),
            cultivation=row["cultivation"],
            age=row["age"],
            lifespan=row["lifespan"],
            spirit_stones=row["spirit_stones"],
            fortune=row["fortune"],
            stamina=row["stamina"],
            comprehension=row["comprehension"],
            rebirth_count=row["rebirth_count"],
            soul_marks=row["soul_marks"],
            legacy_points=row["legacy_points"],
            sect_id=row["sect_id"],
        )

    async def create_player(self, player: Player) -> Player:
        async with await self._connect() as db:
            await db.execute(
                """
                INSERT INTO players (
                  user_id, nickname, root_type, realm, cultivation, age, lifespan,
                  spirit_stones, fortune, stamina, comprehension, rebirth_count,
                  soul_marks, legacy_points, sect_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    player.user_id,
                    player.nickname,
                    player.root_type.value,
                    player.realm.value,
                    player.cultivation,
                    player.age,
                    player.lifespan,
                    player.spirit_stones,
                    player.fortune,
                    player.stamina,
                    player.comprehension,
                    player.rebirth_count,
                    player.soul_marks,
                    player.legacy_points,
                    player.sect_id,
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
        legacy_points_delta: int = 0,
        rebirth_count_delta: int = 0,
        soul_marks_delta: int = 0,
        realm: Realm | None = None,
        root_type: RootType | None = None,
    ) -> None:
        updates: list[str] = []
        params: list[Any] = []

        if spirit_stones_delta:
            updates.append("spirit_stones = spirit_stones + ?")
            params.append(spirit_stones_delta)
        if cultivation_delta:
            updates.append("cultivation = cultivation + ?")
            params.append(cultivation_delta)
        if fortune_delta:
            updates.append("fortune = fortune + ?")
            params.append(fortune_delta)
        if stamina_delta:
            updates.append("stamina = stamina + ?")
            params.append(stamina_delta)
        if legacy_points_delta:
            updates.append("legacy_points = legacy_points + ?")
            params.append(legacy_points_delta)
        if rebirth_count_delta:
            updates.append("rebirth_count = rebirth_count + ?")
            params.append(rebirth_count_delta)
        if soul_marks_delta:
            updates.append("soul_marks = soul_marks + ?")
            params.append(soul_marks_delta)
        if realm is not None:
            updates.append("realm = ?")
            params.append(realm.value)
        if root_type is not None:
            updates.append("root_type = ?")
            params.append(root_type.value)

        if not updates:
            return

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)

        async with await self._connect() as db:
            await db.execute(
                f"UPDATE players SET {', '.join(updates)} WHERE user_id = ?",
                tuple(params),
            )
            await db.commit()

    async def get_today_signin(self, user_id: str, sign_date: str) -> aiosqlite.Row | None:
        async with await self._connect() as db:
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
        async with await self._connect() as db:
            row = await self._fetchone(db, "SELECT amount FROM fortune_pool WHERE id = 1")
        return 0 if row is None else int(row["amount"])

    async def adjust_fortune_pool(self, delta: int) -> int:
        async with await self._connect() as db:
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
        async with await self._connect() as db:
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
        async with await self._connect() as db:
            cursor = await db.execute(
                """
                SELECT id, name, theme, description, required_rebirth_count
                FROM sects
                WHERE required_rebirth_count <= ?
                ORDER BY required_rebirth_count, name
                """,
                (rebirth_count,),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def record_rebirth(
        self,
        user_id: str,
        rebirth_count: int,
        previous_realm: Realm,
        legacy_points_gained: int,
        soul_marks_consumed: int,
    ) -> None:
        async with await self._connect() as db:
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
        async with await self._connect() as db:
            await db.executemany(
                """
                INSERT OR IGNORE INTO legacy_unlocks (user_id, unlock_key)
                VALUES (?, ?)
                """,
                [(user_id, unlock_key) for unlock_key in unlock_keys],
            )
            await db.commit()
