import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0008_telegram_connection_and_account_budget"),
        ("finance", "0005_gramratemarkuprule"),
        ("telegram_ads", "0005_telegram_ads_connection"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountFundingTransfer",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("direction", models.CharField(
                    max_length=24,
                    default="main_to_related",
                    choices=[
                        ("main_to_related", "از حساب مرکزی به حساب مرتبط"),
                        ("related_to_main", "از حساب مرتبط به حساب مرکزی"),
                    ],
                )),
                ("status", models.CharField(
                    max_length=16,
                    default="executing",
                    choices=[
                        ("executing", "در حال انتقال"),
                        ("completed", "تأییدشده"),
                        ("uncertain", "نیازمند تطبیق"),
                        ("failed", "ناموفق"),
                    ],
                )),
                ("amount", models.DecimalField(max_digits=24, decimal_places=9)),
                ("currency", models.CharField(max_length=8)),
                ("idempotency_key", models.CharField(max_length=128, unique=True)),
                ("transaction_id", models.CharField(max_length=256, blank=True)),
                ("response_payload", models.JSONField(default=dict, blank=True)),
                ("error_code", models.CharField(max_length=120, blank=True)),
                ("confirmed_at", models.DateTimeField(null=True, blank=True)),
                (
                    "connection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="funding_transfers",
                        to="telegram_ads.telegramadsconnection",
                    ),
                ),
                (
                    "order",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="account_funding_transfer",
                        to="finance.advertisingorder",
                    ),
                ),
                (
                    "operation",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="account_funding_transfer",
                        to="campaigns.remoteadoperation",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="accountfundingtransfer",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(order__isnull=False, operation__isnull=True)
                    | models.Q(order__isnull=True, operation__isnull=False)
                ),
                name="account_funding_transfer_has_one_source",
            ),
        ),
    ]
