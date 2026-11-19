from django.db import migrations, models


def check_reference_duplicates(apps, schema_editor):
    Payment = apps.get_model("finance", "Payment")
    from django.db.models import Count
    duplicates = Payment.objects.exclude(provider_reference="").values(
        "gateway", "provider_reference").annotate(n=Count("id")).filter(n__gt=1)
    if duplicates.exists():
        raise RuntimeError("Duplicate payment provider references require manual financial reconciliation before migration.")


class Migration(migrations.Migration):
    dependencies = [("finance", "0003_credit_allocation")]
    operations = [
        migrations.RunPython(check_reference_duplicates, migrations.RunPython.noop),
        migrations.AddField(model_name="payment", name="provider_amount_irr",
                           field=models.BigIntegerField(blank=True, null=True)),
        migrations.AddConstraint(model_name="payment", constraint=models.UniqueConstraint(
            fields=["gateway", "provider_reference"], condition=~models.Q(provider_reference=""),
            name="unique_payment_gateway_reference")),
    ]
