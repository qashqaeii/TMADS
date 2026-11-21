import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0006_website_photo"),
        ("telegram_ads", "0004_telegram_ads_connection"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="telegram_connection",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="campaigns", to="telegram_ads.telegramadsconnection",
            ),
        ),
        migrations.AddField(
            model_name="campaign",
            name="account_budget_amount",
            field=models.DecimalField(decimal_places=9, default=0, max_digits=24),
        ),
        migrations.AddField(
            model_name="campaign",
            name="account_daily_budget_limit",
            field=models.DecimalField(decimal_places=9, default=0, max_digits=24),
        ),
        migrations.AddField(
            model_name="campaign",
            name="budget_currency",
            field=models.CharField(blank=True, max_length=8),
        ),
    ]
