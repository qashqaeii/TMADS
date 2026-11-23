from django.core.management.base import BaseCommand

from apps.finance.funding_reconciliation import reconcile_uncertain_funding_transfer
from apps.finance.models import AccountFundingTransfer


class Command(BaseCommand):
    help = "Reconcile an uncertain AccountFundingTransfer using read-only Telegram transaction status."

    def add_arguments(self, parser):
        parser.add_argument("transfer_id", help="AccountFundingTransfer UUID")
        parser.add_argument(
            "--username",
            required=True,
            help="Platform manager username to record as reconciliation actor",
        )

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.get(username=options["username"])
        if not user.is_platform_manager:
            self.stderr.write(self.style.ERROR("User must be a platform manager."))
            return
        try:
            transfer = reconcile_uncertain_funding_transfer(options["transfer_id"], actor=user)
        except (AccountFundingTransfer.DoesNotExist, ValueError) as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return
        self.stdout.write(self.style.SUCCESS(f"Transfer {transfer.pk} reconciled as {transfer.status}"))