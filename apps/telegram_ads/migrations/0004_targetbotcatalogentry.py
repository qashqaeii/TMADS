import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("telegram_ads", "0003_account_asset_operation"),
    ]

    operations = [
        migrations.CreateModel(
            name="TargetBotCatalogEntry",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("username", models.CharField(db_index=True, max_length=64, unique=True)),
                ("title", models.CharField(blank=True, max_length=200)),
                ("photo_url", models.URLField(blank=True, max_length=500)),
                ("category", models.CharField(blank=True, db_index=True, max_length=64)),
                ("language_codes", models.JSONField(blank=True, default=list)),
                ("topic_ids", models.JSONField(blank=True, default=list)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("related_usernames", models.JSONField(blank=True, default=list)),
                ("monthly_users", models.PositiveIntegerField(blank=True, null=True)),
                ("priority", models.IntegerField(default=0)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "verbose_name": "Target bot catalog entry",
                "verbose_name_plural": "Target bot catalog entries",
                "ordering": ["-priority", "username"],
            },
        ),
    ]
