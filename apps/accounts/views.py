from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, PasswordChangeFormFa, RegisterForm
from .models import CustomerProfile
from .permissions import customer_required


def _account_landing(user):
    """Operators do not require customer profiles; redirect to their workspace."""
    return "operations:overview" if user.is_platform_manager else "dashboard:home"


def register_view(request):
    if request.user.is_authenticated:
        return redirect(_account_landing(request.user))
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "خوش آمدید! حساب شما ایجاد شد.")
        return redirect(_account_landing(request.user))
    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_account_landing(request.user))
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        messages.success(request, "ورود موفق.")
        next_url = request.GET.get("next", "")
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ) and next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
        return redirect(_account_landing(request.user))
    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.info(request, "از حساب خارج شدید.")
    return redirect("public:home")


@login_required
@customer_required
def profile_view(request):
    profile = request.user.customer_profile
    password_form = PasswordChangeFormFa(request.user)
    if request.method == "POST":
        action = request.POST.get("action", "profile")
        if action == "password":
            password_form = PasswordChangeFormFa(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "رمز عبور تغییر کرد.")
                return redirect("accounts:profile")
        elif action == "avatar":
            avatar = request.POST.get("avatar", CustomerProfile.Avatar.MALE)
            if avatar not in CustomerProfile.Avatar.values:
                avatar = CustomerProfile.Avatar.MALE
            profile.avatar = avatar
            profile.save(update_fields=["avatar", "updated_at"])
            messages.success(request, "آواتار ذخیره شد.")
            return redirect("accounts:profile")
        else:
            display_name = request.POST.get("display_name", "").strip()
            company_name = request.POST.get("company_name", "").strip()
            display_limit = profile._meta.get_field("display_name").max_length
            company_limit = profile._meta.get_field("company_name").max_length
            if len(display_name) > display_limit or len(company_name) > company_limit:
                messages.error(
                    request,
                    f"نام نمایشی حداکثر {display_limit} و نام کسب‌وکار حداکثر {company_limit} کاراکتر است.",
                )
                return redirect("accounts:profile")
            profile.display_name = display_name
            profile.company_name = company_name
            profile.save(update_fields=["display_name", "company_name", "updated_at"])
            messages.success(request, "پروفایل به‌روزرسانی شد.")
            return redirect("accounts:profile")
    return render(
        request,
        "accounts/profile.html",
        {
            "profile": profile,
            "password_form": password_form,
            "avatar_choices": CustomerProfile.Avatar.choices,
        },
    )
