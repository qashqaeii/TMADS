from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.finance.exceptions import NobitexAPIError, PricingError
from apps.finance.services.campaign_pricing import build_campaign_quote
from apps.finance.services.money import irr_to_toman_int
from apps.finance.services.ton_exchange_rate import fetch_live_snapshot, get_cached_snapshot


class Command(BaseCommand):
    help = "Fetch live Gram(TON)/IRR from Nobitex (read-only) and print pricing diagnostics."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sample-ton",
            type=str,
            default="1.5",
            help="Hypothetical TON budget for sample quote math (not persisted)",
        )

    def handle(self, *args, **options):
        self.stdout.write(f"API base: {settings.NOBITEX_API_BASE_URL}")
        self.stdout.write(f"Stats pair: {settings.NOBITEX_STATS_PAIR}")
        self.stdout.write(f"Orderbook: {settings.NOBITEX_ORDERBOOK_SYMBOL}")
        try:
            snap = fetch_live_snapshot(persist=True)
            status = "ok"
        except NobitexAPIError as exc:
            self.stderr.write(self.style.ERROR(f"API status: failed ({exc})"))
            cached = get_cached_snapshot(allow_stale_display=True)
            if not cached:
                return
            snap = cached
            status = "cached_stale"
        self.stdout.write(self.style.SUCCESS(f"API status: {status}"))
        self.stdout.write(f"Market symbol: {snap.market_symbol}")
        self.stdout.write(f"Best bid IRR: {snap.best_bid_irr}")
        self.stdout.write(f"Best ask IRR: {snap.best_ask_irr}")
        self.stdout.write(f"Last trade IRR: {snap.last_trade_irr}")
        self.stdout.write(f"Rate IRR/TON: {snap.irr_per_ton}")
        self.stdout.write(f"Rate Toman/TON: {irr_to_toman_int(snap.irr_per_ton):,}")
        self.stdout.write(f"Data timestamp: {snap.fetched_at.isoformat()}")
        self.stdout.write(f"Fresh: {snap.is_fresh}")
        self.stdout.write(f"Source: {snap.source}")

        sample_ton = Decimal(str(options["sample_ton"]))
        sample_irr = int((sample_ton * snap.best_ask_irr).to_integral_value(rounding="ROUND_CEILING"))
        self.stdout.write("")
        self.stdout.write(f"Sample hypothetical: {sample_ton} TON ≈ {irr_to_toman_int(sample_irr):,} toman (ask)")
        try:
            q = build_campaign_quote(sample_irr)
            self.stdout.write(
                f"Quote sample: total {irr_to_toman_int(q['total_irr']):,} toman "
                f"(fee {q['fee_percent']}%, buffer {q['risk_buffer_percent']}%)"
            )
        except PricingError as exc:
            self.stdout.write(self.style.WARNING(f"Sample quote skipped: {exc}"))
