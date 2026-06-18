import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter
from nonebot.adapters.qq import Adapter as QQAdapter

from xianbot.config import get_settings


def _register_health_routes() -> None:
    driver = nonebot.get_driver()
    app = getattr(driver, "server_app", None)
    if app is None:
        return

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "name": "qxianbot",
            "status": "ok",
            "health": "/health",
            "qq_webhook": "/qq/webhook",
        }

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "qxianbot"}


def main() -> None:
    settings = get_settings()

    nonebot.init()
    driver = nonebot.get_driver()
    driver.register_adapter(OneBotV11Adapter)
    driver.register_adapter(QQAdapter)
    _register_health_routes()

    nonebot.load_plugin("plugins.qxian")
    nonebot.logger.info(
        "qxianbot starting with database={} market_fee={} daily_pool_release={}",
        settings.database_url,
        settings.market_fee_rate,
        settings.daily_pool_release_rate,
    )
    nonebot.run()


if __name__ == "__main__":
    main()
