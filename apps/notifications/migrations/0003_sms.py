import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0002_event_idempotency")]
    operations = [
        migrations.CreateModel(name="SmsContact", fields=[
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("phone", models.CharField(max_length=11, unique=True)),
            ("enabled", models.BooleanField(default=True)),
            ("customer", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="sms_contact", to="accounts.customerprofile")),
        ]),
        migrations.CreateModel(name="SmsOutbox", fields=[
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("event_key", models.CharField(max_length=160)),
            ("purpose", models.CharField(max_length=32)),
            ("phone", models.CharField(max_length=11)),
            ("attributes", models.JSONField(default=dict)),
            ("status", models.CharField(choices=[("queued", "در صف"), ("sending", "در حال ارسال"), ("accepted", "پذیرفته‌شده توسط پنل"), ("failed", "ناموفق"), ("unknown", "نتیجه نامشخص"), ("skipped", "ارسال نشد"), ("simulated", "آزمایشی")], db_index=True, default="queued", max_length=16)),
            ("provider_id", models.CharField(blank=True, max_length=128)),
            ("error_code", models.CharField(blank=True, max_length=48)),
            ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sms_messages", to="accounts.customerprofile")),
        ], options={"ordering": ["-created_at"], "constraints": [models.UniqueConstraint(fields=("customer", "event_key"), name="one_sms_per_customer_event")]}),
        migrations.CreateModel(name="SmsOtp", fields=[
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("phone", models.CharField(db_index=True, max_length=11)),
            ("digest", models.CharField(max_length=64)),
            ("expires_at", models.DateTimeField()),
            ("attempts", models.PositiveSmallIntegerField(default=0)),
            ("consumed", models.BooleanField(default=False)),
            ("accepted", models.BooleanField(default=False)),
            ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sms_otps", to="accounts.customerprofile")),
        ]),
        migrations.CreateModel(name="SmsPhoneThrottle", fields=[("phone", models.CharField(max_length=11, primary_key=True, serialize=False))]),
    ]
