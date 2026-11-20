from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

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
    username = forms.CharField(label="نام کاربری یا ایمیل")
