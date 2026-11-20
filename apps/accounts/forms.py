from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UsernameField
from django.db.models import Q

from apps.notifications.faraz import normalize_mobile

from .models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label="ایمیل")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={"autocomplete": "username"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "username": "نام کاربری",
            "email": "ایمیل",
            "password1": "رمز عبور",
            "password2": "تکرار رمز عبور",
        }
        for name, label in labels.items():
            field = self.fields[name]
            field.label = label
            field.error_messages["required"] = "تکمیل این فیلد الزامی است."
            field.widget.attrs.update({"dir": "ltr"})
        self.fields["username"].widget.attrs.update({"dir": "auto", "placeholder": "نام کاربری دلخواه"})
        self.fields["email"].widget.attrs.update({"autocomplete": "email", "placeholder": "name@example.com"})
        self.fields["username"].help_text = "حداکثر ۱۵۰ نویسه؛ حروف، اعداد و نشانه‌های مجاز."
        self.fields["password1"].help_text = "حداقل ۸ نویسه؛ غیرعددیِ صرف، غیررایج و متفاوت از اطلاعات شخصی."
        self.fields["password2"].help_text = ""
        self.fields["email"].error_messages["invalid"] = "نشانی ایمیل معتبر وارد کنید."

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
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
