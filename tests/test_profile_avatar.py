import pytest
from django.urls import reverse

from apps.accounts.models import CustomerProfile


@pytest.mark.django_db
def test_profile_default_avatar_is_male(client, customer_user):
    profile = customer_user.customer_profile
    assert profile.avatar == CustomerProfile.Avatar.MALE

    client.force_login(customer_user)
    response = client.get(reverse("accounts:profile"))
    assert response.status_code == 200
    html = response.content.decode()
    assert 'id="profile-avatar-dialog"' in html
    assert 'data-avatar-open' in html
    assert "ga-avatar-picker" not in html
    assert "آواتار خودت رو انتخاب کن" in html
    assert 'name="avatar" value="male"' in html
    assert 'name="avatar" value="female"' in html
    assert 'name="avatar" value="male_formal"' in html
    assert 'name="avatar" value="male_wine"' in html
    assert 'name="avatar" value="male_blue"' in html
    assert 'name="avatar" value="male_curly"' in html
    assert 'name="avatar" value="male_locks"' in html
    assert 'name="avatar" value="female_red"' in html
    assert 'name="avatar" value="female_hijab"' in html
    assert 'name="avatar" value="female_gold"' in html
    assert 'name="avatar" value="female_bun"' in html
    assert "زن آبی" not in html
    assert "زن زرشکی" not in html
    assert "زن با حجاب" not in html
    assert "حجاب" not in html
    assert "زن مشکی" in html
    assert 'aria-label="بستن"' in html
    assert "ga-avatar-dialog__close" in html
    assert "avatars/male" in html
    assert "ga-profile-hero" in html
    assert 'value="male" checked' in html or 'value="male" checked=' in html


@pytest.mark.django_db
def test_profile_can_switch_avatar_to_female_via_modal(client, customer_user):
    client.force_login(customer_user)
    response = client.post(
        reverse("accounts:profile"),
        {
            "action": "avatar",
            "avatar": "female_hijab",
        },
    )
    assert response.status_code == 302
    profile = CustomerProfile.objects.get(user=customer_user)
    assert profile.avatar == CustomerProfile.Avatar.FEMALE_HIJAB

    page = client.get(reverse("accounts:profile"))
    html = page.content.decode()
    assert "avatars/female_hijab" in html
    assert 'value="female_hijab" checked' in html or 'value="female_hijab" checked=' in html


@pytest.mark.django_db
def test_profile_info_save_does_not_reset_avatar(client, customer_user):
    profile = customer_user.customer_profile
    profile.avatar = CustomerProfile.Avatar.FEMALE
    profile.save(update_fields=["avatar", "updated_at"])

    client.force_login(customer_user)
    client.post(
        reverse("accounts:profile"),
        {
            "action": "profile",
            "display_name": "سارا",
            "company_name": "تست",
        },
    )
    profile.refresh_from_db()
    assert profile.avatar == CustomerProfile.Avatar.FEMALE
    assert profile.display_name == "سارا"


@pytest.mark.django_db
def test_profile_rejects_unknown_avatar(client, customer_user):
    client.force_login(customer_user)
    client.post(
        reverse("accounts:profile"),
        {
            "action": "avatar",
            "avatar": "alien",
        },
    )
    profile = CustomerProfile.objects.get(user=customer_user)
    assert profile.avatar == CustomerProfile.Avatar.MALE
