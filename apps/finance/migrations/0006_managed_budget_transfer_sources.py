import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0007_telegram_connection_and_account_budget"),
        ("finance", "0005_account_funding_transfer"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accountfundingtransfer",
            name="order",
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="account_funding_transfer", to="finance.advertisingorder",
            ),
        ),
        migrations.AddField(
            model_name="accountfundingtransfer",
            name="operation",
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="account_funding_transfer", to="campaigns.remoteadoperation",
            ),
        ),
        migrations.AddField(
            model_name="accountfundingtransfer",
            name="direction",
            field=models.CharField(max_length=24, default="main_to_related", choices=[
                ("main_to_related", "از حساب مرکزی به حساب مرتبط"),
                ("related_to_main", "از حساب مرتبط به حساب مرکزی"),
            ]),
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
