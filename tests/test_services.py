import asyncio

from xianbot.config import get_settings
from xianbot.database import initialize_database
from xianbot.services import (
    adventure,
    create_market_listing,
    create_player_if_missing,
    get_player_status,
    join_sect,
    list_inventory,
    sign_in,
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

        result = await sign_in("10001")
        assert result.base_reward >= 120

        updated = await get_player_status("10001")
        assert updated is not None
        assert updated.spirit_stones >= 420

    asyncio.run(scenario())
    get_settings.cache_clear()


def test_join_sect_and_inventory_and_listing(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "qxian2.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    initialize_database(get_settings().database_url)

    async def scenario() -> None:
        await create_player_if_missing("10002", "tester2")
        result = await join_sect("10002", "青岚宗")
        assert result.sect_name == "青岚宗"

        bag = await list_inventory("10002")
        assert len(bag) >= 1

        await adventure("10002")
        listing = await create_market_listing("10002", "灵草", 20, 1)
        assert listing.listing_id > 0

    asyncio.run(scenario())
    get_settings.cache_clear()
