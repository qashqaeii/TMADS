from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="event_key",
            field=models.CharField(blank=True, default="", db_index=True, max_length=160),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                fields=["customer", "event_key"],
                condition=~models.Q(event_key=""),
                name="one_notification_per_customer_event",
            ),
        ),
    ]
