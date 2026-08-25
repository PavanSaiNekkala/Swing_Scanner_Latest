from loguru import logger

from app.models.dividend import Dividend

from app.database.tables import DividendTable

from app.providers.yahoo.dividend_provider import (
    DividendProvider as YahooDividendProvider,
)

from app.providers.nse.dividend_provider import (
    DividendProvider as NSEDividendProvider,
)

from app.mergers.dividend_merger import DividendMerger

from app.services.base_service import BaseService


class DividendService(BaseService):

    def __init__(

        self,

    ) -> None:

        super().__init__()

        self.yahoo = YahooDividendProvider()

        self.nse = NSEDividendProvider()

    def get(

        self,

        symbol: str,

    ) -> list[Dividend]:

        # ----------------------------
        # Cache
        # ----------------------------

        cached = self.cache.get(

            "dividend",

            symbol,

        )

        if cached:

            logger.info(

                "Dividend cache hit : {}",

                symbol,

            )

            return cached

        # ----------------------------
        # Database
        # ----------------------------

        stored = self.repo.dividend.get(

            symbol,

        )

        if stored:

            logger.info(

                "Dividend database hit : {} ({} records)",

                symbol,

                len(

                    stored,

                ),

            )

            self.cache.set(

                "dividend",

                symbol,

                stored,

            )

            return stored

        # ----------------------------
        # Providers
        # ----------------------------

        yahoo = self.yahoo.get_dividends(

            symbol,

        )

        nse = self.nse.get_dividends(

            symbol,

        )

        dividends = DividendMerger.merge(

            yahoo,

            nse,

        )


        if not dividends:

            return []

        # ----------------------------
        # Database
        # ----------------------------

        tables = [

            DividendTable(

                symbol=d.symbol,

                ex_date=d.ex_date,

                record_date=d.record_date,

                payment_date=d.payment_date,

                amount=d.amount,

                dividend_type=d.dividend_type,

                currency=d.currency,

            )

            for d in dividends

        ]

        self.repo.dividend.save_many(

            tables,

        )

        # ----------------------------
        # Cache
        # ----------------------------

        self.cache.set(

            "dividend",

            symbol,

            dividends,

        )

        return dividends