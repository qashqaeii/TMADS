from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0002_ad_creation_studio"),
    ]

    operations = [
        migrations.AlterField(
            model_name="campaign",
            name="placement",
            field=models.CharField(
                blank=True,
                choices=[
                    ("search_result", "نتایج جستجو"),
                    ("bot_banner", "بنر ربات"),
                    ("channel_post", "پست کانال"),
                    ("video_banner", "بنر ویدیو"),
                    ("channels", "کانال‌ها (قدیمی)"),
                    ("video", "ویدیو (قدیمی)"),
                ],
                max_length=32,
            ),
        ),
    ]
