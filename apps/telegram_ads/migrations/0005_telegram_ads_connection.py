import django.db.models.deletion
from django.db import migrations, models


def create_existing_managed_connections(apps, schema_editor):
    RelatedAccountRequest = apps.get_model("telegram_ads", "RelatedAccountRequest")
    TelegramAdsConnection = apps.get_model("telegram_ads", "TelegramAdsConnection")
    for row in RelatedAccountRequest.objects.filter(status="provisioned").exclude(remote_account_id="").iterator():
        has_default = TelegramAdsConnection.objects.filter(customer_id=row.customer_id, is_default=True).exists()
        TelegramAdsConnection.objects.get_or_create(
            customer_id=row.customer_id,
            connection_type="platform_managed",
            defaults={
                "status": "connected",
                "remote_account_id": row.remote_account_id,
                "account_title": row.title,
                "currency": "",
                "remaining_budget": 0,
                "encrypted_access_token": "",
                "token_fingerprint": "",
                "related_account_id": row.pk,
                "is_default": not has_default,
                "capabilities": {"account.read": "needs_refresh", "ads.create": "unverified"},
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("telegram_ads", "0004_targetbotcatalogentry"),
    ]

    operations = [
        migrations.CreateModel(
            name="TelegramAdsConnection",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=__import__("uuid").uuid4, serialize=False, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("connection_type", models.CharField(max_length=24, choices=[("customer_owned", "حساب اختصاصی مشتری"), ("platform_managed", "حساب مدیریت‌شده پلتفرم")])),
                ("status", models.CharField(max_length=16, default="connected", choices=[("connected", "متصل"), ("error", "نیازمند بررسی"), ("disconnected", "قطع‌شده")])),
                ("remote_account_id", models.CharField(max_length=256)),
                ("account_title", models.CharField(max_length=200, blank=True)),
                ("currency", models.CharField(max_length=8, blank=True)),
                ("remaining_budget", models.DecimalField(max_digits=24, decimal_places=9, default=0)),
                ("encrypted_access_token", models.TextField(blank=True)),
                ("token_fingerprint", models.CharField(max_length=64, blank=True)),
                ("is_default", models.BooleanField(default=False, db_index=True)),
                ("capabilities", models.JSONField(default=dict, blank=True)),
                ("last_checked_at", models.DateTimeField(null=True, blank=True)),
                ("last_error", models.CharField(max_length=500, blank=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="telegram_ads_connections", to="accounts.customerprofile")),
                ("related_account", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="telegram_connection", to="telegram_ads.relatedaccountrequest")),
            ],
            options={"ordering": ["-is_default", "-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="telegramadsconnection",
            constraint=models.UniqueConstraint(fields=("customer", "connection_type"), name="unique_customer_telegram_connection_type"),
        ),
        migrations.AddConstraint(
            model_name="telegramadsconnection",
            constraint=models.UniqueConstraint(condition=~models.Q(remote_account_id=""), fields=("remote_account_id",), name="unique_telegram_remote_account_binding"),
        ),
        migrations.AddConstraint(
            model_name="telegramadsconnection",
            constraint=models.UniqueConstraint(condition=~models.Q(token_fingerprint=""), fields=("token_fingerprint",), name="unique_telegram_token_fingerprint"),
        ),
        migrations.AddConstraint(
            model_name="telegramadsconnection",
            constraint=models.UniqueConstraint(condition=models.Q(is_default=True), fields=("customer",), name="unique_default_telegram_connection_per_customer"),
        ),
        migrations.AddConstraint(
            model_name="telegramadsconnection",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(connection_type="customer_owned", encrypted_access_token__gt="", token_fingerprint__gt="", related_account__isnull=True)
                    | models.Q(connection_type="platform_managed", encrypted_access_token="", token_fingerprint="", related_account__isnull=False)
                    | models.Q(connection_type="customer_owned", status="disconnected", encrypted_access_token="", token_fingerprint="", related_account__isnull=True)
                ),
                name="telegram_connection_credentials_match_type",
            ),
        ),
        migrations.RunPython(create_existing_managed_connections, migrations.RunPython.noop),
    ]
