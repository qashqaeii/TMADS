import uuid
import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("telegram_ads","0002_related_account_request")]
    operations = [
        migrations.CreateModel(name="AccountAssetOperation", fields=[
            ("id",models.UUIDField(primary_key=True,default=uuid.uuid4,serialize=False,editable=False)),
            ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
            ("updated_at",models.DateTimeField(auto_now=True)),
            ("action",models.CharField(max_length=16)),
            ("state",models.CharField(max_length=16,default="executing")),
            ("remote_id",models.CharField(max_length=256,blank=True)),
            ("account",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="asset_operations",to="telegram_ads.relatedaccountrequest")),
        ],options={"ordering":["-created_at"]}),
        migrations.AddConstraint(model_name="accountassetoperation",constraint=models.UniqueConstraint(fields=("account",),condition=models.Q(state__in=["executing","uncertain"]),name="one_unresolved_asset_operation")),
    ]
