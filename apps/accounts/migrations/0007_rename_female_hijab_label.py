from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_add_more_avatars"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customerprofile",
            name="avatar",
            field=models.CharField(
                choices=[
                    ("male", "مرد"),
                    ("female", "زن"),
                    ("male_formal", "مرد رسمی"),
                    ("male_wine", "مرد زرشکی"),
                    ("male_blue", "مرد آبی"),
                    ("male_curly", "مرد موفر"),
                    ("male_locks", "مرد با موهای فر"),
                    ("female_red", "زن قرمز"),
                    ("female_hijab", "زن مشکی"),
                    ("female_gold", "زن طلایی"),
                    ("female_bun", "زن با شینیون"),
                ],
                db_index=True,
                default="male",
                max_length=32,
            ),
        ),
    ]
