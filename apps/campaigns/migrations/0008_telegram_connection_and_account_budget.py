import django.db.models.deletion
from django.db import migrations, models


def backfill_remote_account_ids(apps, schema_editor):
    TelegramAdvertisement = apps.get_model("campaigns", "TelegramAdvertisement")
    for ad in TelegramAdvertisement.objects.exclude(remote_ad_id="").select_related(
        "campaign", "campaign__telegram_connection",
    ).iterator():
        connection = getattr(ad.campaign, "telegram_connection", None)
        if connection and connection.remote_account_id:
            ad.remote_account_id = connection.remote_account_id
            ad.save(update_fields=["remote_account_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0007_alter_campaign_target_type"),
        ("telegram_ads", "0005_telegram_ads_connection"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="telegram_connection",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="campaigns",
                to="telegram_ads.telegramadsconnection",
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
        migrations.AddField(
            model_name="telegramadvertisement",
            name="remote_account_id",
            field=models.CharField(blank=True, db_index=True, max_length=256),
        ),
        migrations.RunPython(backfill_remote_account_ids, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="telegramadvertisement",
            name="unique_remote_ad_id_when_set",
        ),
        migrations.AddConstraint(
            model_name="telegramadvertisement",
            constraint=models.UniqueConstraint(
                condition=models.Q(remote_account_id="") & ~models.Q(remote_ad_id=""),
                fields=("remote_ad_id",),
                name="unique_legacy_remote_ad_id_when_set",
            ),
        ),
        migrations.AddConstraint(
            model_name="telegramadvertisement",
            constraint=models.UniqueConstraint(
                condition=~models.Q(remote_ad_id="") & ~models.Q(remote_account_id=""),
                fields=("remote_account_id", "remote_ad_id"),
                name="unique_remote_ad_per_account",
            ),
        ),
    ]
