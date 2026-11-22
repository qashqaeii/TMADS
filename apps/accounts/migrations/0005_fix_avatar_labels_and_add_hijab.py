from django.db import migrations, models


def remap_avatar_keys(apps, schema_editor):
    CustomerProfile = apps.get_model("accounts", "CustomerProfile")
    CustomerProfile.objects.filter(avatar="female_wine").update(avatar="male_wine")
    CustomerProfile.objects.filter(avatar="female_blue").update(avatar="male_blue")


def unremap_avatar_keys(apps, schema_editor):
    CustomerProfile = apps.get_model("accounts", "CustomerProfile")
    CustomerProfile.objects.filter(avatar="male_wine").update(avatar="female_wine")
    CustomerProfile.objects.filter(avatar="male_blue").update(avatar="female_blue")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_expand_avatar_choices"),
    ]

    operations = [
        migrations.RunPython(remap_avatar_keys, unremap_avatar_keys),
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
                    ("female_red", "زن قرمز"),
                    ("female_hijab", "زن با حجاب"),
                ],
                db_index=True,
                default="male",
                max_length=32,
            ),
        ),
    ]
