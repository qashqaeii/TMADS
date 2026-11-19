"""Explicit operator recovery for redirected payments; dry run by default."""
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from apps.finance.models import Payment
from apps.finance.zibal_views import verify_zibal


class Command(BaseCommand):
    help = "List or reconcile pending Zibal top-ups (without creating a new charge)."

    def add_arguments(self, parser):
        parser.add_argument("--payment-id", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            payment = Payment.objects.get(pk=options["payment_id"], gateway="zibal", order__isnull=True)
        except (Payment.DoesNotExist, ValueError, ValidationError):
            raise CommandError("Unknown Zibal top-up.")
        self.stdout.write(f"{payment.pk}: {payment.status}")
        if not options["apply"]:
            self.stdout.write("Dry run; no gateway request made.")
            return
        if payment.status != Payment.Status.REDIRECTED or not payment.provider_reference:
            self.stdout.write("No verification needed or no track ID.")
            return
        verify_zibal(payment.pk, expected_track=payment.provider_reference)
        payment.refresh_from_db()
        self.stdout.write(f"Final local status: {payment.status}")
