import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0004_payment_provider_integrity"),
        ("telegram_ads", "0004_telegram_ads_connection"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountFundingTransfer",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(max_length=16, default="executing", choices=[
                    ("executing", "در حال انتقال"), ("completed", "تأییدشده"),
                    ("uncertain", "نیازمند تطبیق"), ("failed", "ناموفق"),
                ])),
                ("amount", models.DecimalField(max_digits=24, decimal_places=9)),
                ("currency", models.CharField(max_length=8)),
                ("idempotency_key", models.CharField(max_length=128, unique=True)),
                ("transaction_id", models.CharField(max_length=256, blank=True)),
                ("response_payload", models.JSONField(default=dict, blank=True)),
                ("error_code", models.CharField(max_length=120, blank=True)),
                ("confirmed_at", models.DateTimeField(null=True, blank=True)),
                ("connection", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="funding_transfers", to="telegram_ads.telegramadsconnection")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="account_funding_transfer", to="finance.advertisingorder")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
