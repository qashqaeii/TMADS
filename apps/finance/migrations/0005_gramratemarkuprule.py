import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0004_payment_provider_integrity"),
    ]

    operations = [
        migrations.CreateModel(
            name="GramRateMarkupRule",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "percent",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="Percent added on top of Nobitex ask for customer pricing (0–100).",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="gramratemarkuprule",
            constraint=models.CheckConstraint(
                condition=models.Q(percent__gte=0) & models.Q(percent__lte=100),
                name="gram_rate_markup_percent_range",
            ),
        ),
    ]
