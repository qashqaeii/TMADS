import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("telegram_ads", "0005_telegram_ads_connection")]

    operations = [
        migrations.CreateModel(
            name="TelegramAdsPlatformCredential",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("slot", models.CharField(max_length=16, unique=True, default="primary", editable=False)),
                ("encrypted_access_token", models.TextField(blank=True)),
                ("token_fingerprint", models.CharField(max_length=64, blank=True)),
                ("remote_account_id", models.CharField(max_length=256, blank=True)),
                ("account_title", models.CharField(max_length=200, blank=True)),
                ("currency", models.CharField(max_length=8, blank=True)),
                ("remaining_budget", models.DecimalField(max_digits=24, decimal_places=9, default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("last_checked_at", models.DateTimeField(null=True, blank=True)),
            ],
        ),
    ]
