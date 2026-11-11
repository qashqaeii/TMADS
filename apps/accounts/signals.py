from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.finance.services import ensure_wallet

from .models import CustomerProfile, User


@receiver(post_save, sender=User)
def create_customer_profile(sender, instance: User, created: bool, **kwargs):
    if not created:
        return
    if instance.role == User.Role.CUSTOMER:
        profile = CustomerProfile.objects.create(user=instance)
        ensure_wallet(profile)


@receiver(post_save, sender=CustomerProfile)
def wallet_on_profile(sender, instance: CustomerProfile, created: bool, **kwargs):
    if created:
        ensure_wallet(instance)
