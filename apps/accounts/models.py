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
    class Avatar(models.TextChoices):
        MALE = "male", "مرد"
        FEMALE = "female", "زن"
        MALE_FORMAL = "male_formal", "مرد رسمی"
        MALE_WINE = "male_wine", "مرد زرشکی"
        MALE_BLUE = "male_blue", "مرد آبی"
        MALE_CURLY = "male_curly", "مرد موفر"
        MALE_LOCKS = "male_locks", "مرد با موهای فر"
        FEMALE_RED = "female_red", "زن قرمز"
        FEMALE_HIJAB = "female_hijab", "زن مشکی"
        FEMALE_GOLD = "female_gold", "زن طلایی"
        FEMALE_BUN = "female_bun", "زن با شینیون"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    display_name = models.CharField(max_length=120, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    avatar = models.CharField(
        max_length=32,
        choices=Avatar.choices,
        default=Avatar.MALE,
        db_index=True,
    )
    is_suspended = models.BooleanField(default=False)
    internal_notes = models.TextField(blank=True)

    @property
    def avatar_static_path(self) -> str:
        key = self.avatar if self.avatar in self.Avatar.values else self.Avatar.MALE
        return f"img/avatars/{key}.svg"

    def __str__(self) -> str:
        return self.display_name or self.user.get_full_name() or self.user.username
