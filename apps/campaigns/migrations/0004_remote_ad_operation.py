import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("campaigns", "0003_alter_campaign_placement")]
    operations = [
        migrations.CreateModel(
            name="RemoteAdOperation",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("action", models.CharField(max_length=24, choices=[("pause","توقف تبلیغ"),("resume","ادامه تبلیغ"),("review","ارسال مجدد برای بررسی"),("edit_cpm","تغییر CPM"),("edit_daily_limit","تغییر سقف روزانه"),("edit_title","تغییر عنوان داخلی")])),
                ("status", models.CharField(max_length=16, default="pending", choices=[("pending","در انتظار اپراتور"),("executing","در حال اجرا"),("completed","انجام‌شده"),("rejected","رد شده"),("uncertain","نیازمند تطبیق")])),
                ("request_payload", models.JSONField(default=dict)),
                ("result_payload", models.JSONField(default=dict)),
                ("note", models.CharField(max_length=500, blank=True)),
                ("advertisement", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="operations", to="campaigns.telegramadvertisement")),
            ],
            options={"ordering":["-created_at"]},
        ),
        migrations.AddConstraint(model_name="remoteadoperation", constraint=models.UniqueConstraint(fields=("advertisement",), condition=models.Q(status__in=["pending","executing","uncertain"]), name="unique_open_remote_ad_operation")),
    ]
