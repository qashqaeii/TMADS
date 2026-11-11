from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="target_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("search", "جستجو"),
                    ("bots", "ربات‌ها"),
                    ("users", "کاربران"),
                    ("channels", "کانال‌ها"),
                ],
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="campaign",
            name="wizard_version",
            field=models.PositiveSmallIntegerField(default=2),
        ),
        migrations.AddField(
            model_name="campaign",
            name="ad_settings",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="campaign",
            name="draft_revision",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="campaign",
            name="draft_saved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
