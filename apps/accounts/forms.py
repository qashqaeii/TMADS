from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
    UsernameField,
)
from django.core.validators import MaxLengthValidator, MinLengthValidator
from django.db.models import Q

from apps.notifications.faraz import normalize_mobile

from .models import User


class PasswordChangeFormFa(PasswordChangeForm):
    """Persian labels and compact help text for the profile security panel."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "old_password": "رمز عبور فعلی",
            "new_password1": "رمز عبور جدید",
            "new_password2": "تکرار رمز عبور جدید",
        }
        for name, label in labels.items():
            field = self.fields[name]
            field.label = label
            field.error_messages["required"] = "تکمیل این فیلد الزامی است."
            field.widget.attrs.update({"dir": "ltr"})
        self.fields["old_password"].widget.attrs["autocomplete"] = "current-password"
        self.fields["new_password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["new_password2"].widget.attrs["autocomplete"] = "new-password"
        self.fields["new_password1"].help_text = "حداقل ۸ نویسه؛ از اطلاعات شخصی خیلی شبیه استفاده نکنید."
        self.fields["new_password2"].help_text = ""


class RegisterForm(UserCreationForm):
    mobile = forms.CharField(
        label="شماره تماس",
        max_length=20,
        error_messages={"required": "تکمیل این فیلد الزامی است."},
    )

    class Meta:
        model = User
        fields = ("username", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={"autocomplete": "username"}),
        }

    field_order = ("username", "mobile", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "username": "نام کاربری",
            "mobile": "شماره تماس",
            "password1": "رمز عبور",
            "password2": "تکرار رمز عبور",
        }
        for name, label in labels.items():
            field = self.fields[name]
            field.label = label
            field.error_messages["required"] = "تکمیل این فیلد الزامی است."
            field.widget.attrs.update({"dir": "ltr"})
        username = self.fields["username"]
        username.widget.attrs.update({"dir": "auto", "placeholder": "نام کاربری دلخواه", "minlength": "6"})
        # Allow any characters; only enforce length (more than 5 → min 6).
        username.validators = [
            MinLengthValidator(6, message="نام کاربری باید بیشتر از ۵ نویسه باشد."),
            MaxLengthValidator(150, message="نام کاربری حداکثر ۱۵۰ نویسه است."),
        ]
        username.help_text = "حداقل ۶ نویسه"
        self.fields["mobile"].widget.attrs.update(
            {
                "autocomplete": "tel",
                "inputmode": "tel",
                "placeholder": "09123456789",
            }
        )
        self.fields["mobile"].help_text = "مثال: ۰۹۱۲۳۴۵۶۷۸۹"
        self.fields["password1"].help_text = "حداقل ۸ نویسه"
        self.fields["password2"].help_text = ""

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if len(username) < 6:
            raise forms.ValidationError("نام کاربری باید بیشتر از ۵ نویسه باشد.")
        if len(username) > 150:
            raise forms.ValidationError("نام کاربری حداکثر ۱۵۰ نویسه است.")
        return username

    def clean_mobile(self):
        mobile = normalize_mobile(self.cleaned_data.get("mobile"))
        if not mobile:
            raise forms.ValidationError("شماره موبایل معتبر وارد کنید (مثال: ۰۹۱۲۳۴۵۶۷۸۹).")
        if User.objects.filter(mobile=mobile).exists():
            raise forms.ValidationError("این شماره تماس قبلاً ثبت شده است.")
        return mobile

    def save(self, commit=True):
        user = super().save(commit=False)
        user.mobile = self.cleaned_data["mobile"]
        user.email = ""
        user.role = User.Role.CUSTOMER
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """Accept a unique saved mobile alias, without replacing Django password auth."""

    username = UsernameField(
        label="نام کاربری یا شماره موبایل",
        max_length=150,
        error_messages={"required": "نام کاربری یا شماره موبایل را وارد کنید."},
    )
    password = forms.CharField(
        label="رمز عبور",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        error_messages={"required": "رمز عبور را وارد کنید."},
    )
    error_messages = {
        "invalid_login": "نام کاربری یا شماره موبایل یا رمز عبور اشتباه است.",
        "inactive": "نام کاربری یا شماره موبایل یا رمز عبور اشتباه است.",
    }

    def clean(self):
        identifier = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if not identifier or not password:
            return super().clean()

        mobile = normalize_mobile(identifier)
        # Preserve exact usernames, including existing numeric usernames.
        if not mobile or User.objects.filter(username=identifier).exists():
            return super().clean()

        # SMS enrollment stores canonical 09...; also handle common legacy
        # formats (including Persian/Arabic digits) on admin-managed accounts.
        local = (mobile, "+98" + mobile[1:], "0098" + mobile[1:], "98" + mobile[1:])
        aliases = {identifier, *local}
        for digits in ("۰۱۲۳۴۵۶۷۸۹", "٠١٢٣٤٥٦٧٨٩"):
            aliases.update(value.translate(str.maketrans("0123456789", digits)) for value in local)
        candidates = list(
            User.objects.filter(Q(mobile__in=aliases) | Q(username=mobile))
            .values_list("username", flat=True)[:2]
        )
        if len(candidates) > 1:
            # Ambiguous aliases must never choose an arbitrary account.
            # Match the password-hashing work of an unknown account.
            User().set_password(password)
            raise self.get_invalid_login_error()
        if candidates:
            self.cleaned_data["username"] = candidates[0]
            try:
                return super().clean()
            finally:
                self.cleaned_data["username"] = identifier
        return super().clean()
