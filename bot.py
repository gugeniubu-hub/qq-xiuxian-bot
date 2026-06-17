import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

from xianbot.config import get_settings


def main() -> None:
    settings = get_settings()

    nonebot.init()
    driver = nonebot.get_driver()
    driver.register_adapter(OneBotV11Adapter)

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
