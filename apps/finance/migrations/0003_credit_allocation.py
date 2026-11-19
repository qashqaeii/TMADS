from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0002_exchangerate_details_invoice_refundrequest")]

    operations = [
        migrations.AlterField(
            model_name="walletledgerentry",
            name="entry_type",
            field=models.CharField(max_length=32, choices=[
                ("deposit", "واریز"), ("reservation", "رزرو"),
                ("reservation_release", "آزادسازی رزرو"),
                ("credit_allocation", "تخصیص اعتبار تبلیغاتی"),
                ("spend", "هزینه تبلیغ"), ("service_fee", "کارمزد سرویس"),
                ("refund", "بازپرداخت"), ("adjustment", "تعدیل دستی"),
            ]),
        ),
    ]
