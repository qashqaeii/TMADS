import django.db.models.deletion
from django.db import migrations, models


def bind_existing_asset_operations(apps, schema_editor):
    AccountAssetOperation = apps.get_model("telegram_ads", "AccountAssetOperation")
    TelegramAdsConnection = apps.get_model("telegram_ads", "TelegramAdsConnection")
    for operation in AccountAssetOperation.objects.all().iterator():
        connection = TelegramAdsConnection.objects.filter(
            related_account_id=operation.account_id,
        ).first()
        if connection is None:
            raise RuntimeError(
                "Cannot migrate Telegram asset operation without a verified account connection."
            )
        operation.connection_id = connection.pk
        operation.save(update_fields=["connection"])


class Migration(migrations.Migration):
    dependencies = [("telegram_ads", "0004_telegram_ads_connection")]

    operations = [
        migrations.AddField(
            model_name="accountassetoperation",
            name="connection",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="asset_operations",
                to="telegram_ads.telegramadsconnection",
            ),
        ),
        migrations.RunPython(bind_existing_asset_operations, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="accountassetoperation",
            name="one_unresolved_asset_operation",
        ),
        migrations.AlterField(
            model_name="accountassetoperation",
            name="connection",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="asset_operations",
                to="telegram_ads.telegramadsconnection",
            ),
        ),
        migrations.RemoveField(
            model_name="accountassetoperation",
            name="account",
        ),
        migrations.AddConstraint(
            model_name="accountassetoperation",
            constraint=models.UniqueConstraint(
                fields=("connection",),
                condition=models.Q(state__in=["executing", "uncertain"]),
                name="one_unresolved_asset_operation",
            ),
        ),
    ]
