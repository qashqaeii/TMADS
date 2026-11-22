from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_freeform_username"),
    ]

    operations = [
        migrations.AddField(
            model_name="customerprofile",
            name="avatar",
            field=models.CharField(
                choices=[("male", "مرد"), ("female", "زن")],
                db_index=True,
                default="male",
                max_length=16,
            ),
        ),
    ]
