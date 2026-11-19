import uuid
import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("telegram_ads","0001_initial"),("accounts","0001_initial")]
    operations = [
        migrations.CreateModel(name="RelatedAccountRequest", fields=[
            ("id",models.UUIDField(primary_key=True,default=uuid.uuid4,serialize=False,editable=False)),
            ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
            ("updated_at",models.DateTimeField(auto_now=True)),
            ("status",models.CharField(max_length=16,default="pending",choices=[("pending","در انتظار بررسی"),("executing","در حال ایجاد"),("provisioned","ایجاد و تأیید شده"),("rejected","رد شده"),("uncertain","نیازمند تطبیق")])),
            ("title",models.CharField(max_length=128)),
            ("details",models.JSONField(default=dict)),
            ("consent_at",models.DateTimeField()),
            ("main_account_id",models.CharField(max_length=256,blank=True)),
            ("remote_account_id",models.CharField(max_length=256,blank=True)),
            ("note",models.CharField(max_length=500,blank=True)),
            ("customer",models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name="related_account_request",to="accounts.customerprofile")),
        ],options={"ordering":["-created_at"]}),
        migrations.AddConstraint(model_name="relatedaccountrequest",constraint=models.UniqueConstraint(fields=("main_account_id","remote_account_id"),condition=~models.Q(remote_account_id=""),name="unique_related_account_binding")),
    ]
