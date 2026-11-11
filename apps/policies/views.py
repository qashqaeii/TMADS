from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.permissions import customer_required
from apps.policies.content_center import POLICY_CATEGORIES, POLICY_FAQ, POLICY_INTRO


@login_required
@customer_required
def ad_policies(request):
    return render(
        request,
        "policies/ad_policies.html",
        {
            "intro": POLICY_INTRO,
            "categories": POLICY_CATEGORIES,
            "faq": POLICY_FAQ,
        },
    )
