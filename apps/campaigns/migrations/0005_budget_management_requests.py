from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("campaigns", "0004_remote_ad_operation")]
    operations = [
        migrations.AlterField(model_name="remoteadoperation", name="action",
            field=models.CharField(max_length=24, choices=[
                ("pause","توقف تبلیغ"),("resume","ادامه تبلیغ"),("review","ارسال مجدد برای بررسی"),
                ("edit_cpm","تغییر CPM"),("edit_daily_limit","تغییر سقف روزانه"),("edit_title","تغییر عنوان داخلی"),
                ("increase_budget","افزایش اعتبار تبلیغ"),("decrease_budget","کاهش اعتبار تبلیغ"),
            ])),
    ]
