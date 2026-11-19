import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("accounts", "0001_initial")]
    operations = [
        migrations.CreateModel(name="AiDay", fields=[
            ("day", models.DateField(primary_key=True, serialize=False)),
        ]),
        migrations.CreateModel(name="AiRun", fields=[
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("day", models.DateField(db_index=True)), ("feature", models.CharField(max_length=32)),
            ("fingerprint", models.CharField(max_length=64)), ("state", models.CharField(default="pending", max_length=16)),
            ("result", models.JSONField(default=dict)), ("input_tokens", models.PositiveIntegerField(blank=True, null=True)),
            ("output_tokens", models.PositiveIntegerField(blank=True, null=True)), ("error", models.CharField(blank=True, max_length=32)),
            ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ai_runs", to="accounts.customerprofile")),
        ], options={"indexes": [models.Index(fields=["customer", "day", "feature", "fingerprint"], name="ai_run_lookup_idx")]}),
    ]
