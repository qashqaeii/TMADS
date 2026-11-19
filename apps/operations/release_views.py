from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.accounts.permissions import staff_ops_required
from apps.operations.release_checks import readiness_summary


@login_required
@staff_ops_required
@require_GET
def release_readiness(request):
    result = readiness_summary()
    response = render(request, "operations/release_readiness.html", result)
    response["Cache-Control"] = "private, no-store"
    return response
