from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm
from .permissions import customer_required


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "خوش آمدید! حساب شما ایجاد شد.")
        return redirect("dashboard:home")
    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        messages.success(request, "ورود موفق.")
        next_url = request.GET.get("next") or "dashboard:home"
        return redirect(next_url)
    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.info(request, "از حساب خارج شدید.")
    return redirect("public:home")


@login_required
@customer_required
def profile_view(request):
    profile = request.user.customer_profile
    password_form = PasswordChangeForm(request.user)
    if request.method == "POST":
        action = request.POST.get("action", "profile")
        if action == "password":
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "رمز عبور تغییر کرد.")
                return redirect("accounts:profile")
        else:
            profile.display_name = request.POST.get("display_name", "").strip()
            profile.company_name = request.POST.get("company_name", "").strip()
            profile.save(update_fields=["display_name", "company_name", "updated_at"])
            messages.success(request, "پروفایل به‌روزرسانی شد.")
            return redirect("accounts:profile")
    return render(
        request,
        "accounts/profile.html",
        {"profile": profile, "password_form": password_form},
    )
