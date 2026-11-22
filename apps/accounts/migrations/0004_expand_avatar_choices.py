from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_customerprofile_avatar"),
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
                    ("female_wine", "زن زرشکی"),
                    ("female_blue", "زن آبی"),
                    ("female_red", "زن قرمز"),
                ],
                db_index=True,
                default="male",
                max_length=32,
            ),
        ),
    ]
