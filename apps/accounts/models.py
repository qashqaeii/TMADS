from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel, UUIDModel


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "مشتری"
        SUPPORT = "support", "پشتیبانی"
        FINANCE = "finance", "مالی"
        CAMPAIGN_MANAGER = "campaign_manager", "مدیر کمپین"
        ADMIN = "admin", "مدیر"
        SUPERADMIN = "superadmin", "مدیر ارشد"

    # Free-form username: any characters, just more than 5 (min length 6).
    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        help_text=_("Required. 150 characters or fewer."),
        validators=[MinLengthValidator(6)],
        error_messages={
            "unique": _("A user with that username already exists."),
        },
    )
    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.CUSTOMER,
        db_index=True,
    )
    mobile = models.CharField(max_length=20, blank=True)
    email_verified = models.BooleanField(default=False)

    @property
    def is_staff_ops(self) -> bool:
        return self.role in {
            self.Role.SUPPORT,
            self.Role.FINANCE,
            self.Role.CAMPAIGN_MANAGER,
            self.Role.ADMIN,
            self.Role.SUPERADMIN,
        } or self.is_superuser

    @property
    def is_platform_manager(self) -> bool:
        """دسترسی پنل عملیات / منوی مدیریت (سوپریوزر یا نقش مدیر)."""
        if self.is_superuser:
            return True
        return self.role in {self.Role.ADMIN, self.Role.SUPERADMIN}


class CustomerProfile(UUIDModel, TimeStampedModel):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    display_name = models.CharField(max_length=120, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    is_suspended = models.BooleanField(default=False)
    internal_notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.display_name or self.user.get_full_name() or self.user.username
