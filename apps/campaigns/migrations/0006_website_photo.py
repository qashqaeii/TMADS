from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("campaigns", "0005_budget_management_requests")]

    operations = [
        migrations.AddField(
            model_name="adcreative",
            name="website_photo",
            field=models.FileField(blank=True, upload_to="website_photos/"),
        ),
    ]
