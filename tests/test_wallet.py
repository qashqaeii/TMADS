import pytest

from apps.finance.services import credit_wallet_deposit, ensure_wallet, reserve_for_order
from uuid import uuid4


@pytest.mark.django_db
def test_wallet_idempotent_deposit(customer_profile):
    wallet = ensure_wallet(customer_profile)
    credit_wallet_deposit(wallet, 100_000, "idem-1")
    credit_wallet_deposit(wallet, 100_000, "idem-1")
    wallet.refresh_from_db()
    assert wallet.available_irr == 100_000


@pytest.mark.django_db
def test_reserve_prevents_double_spend(customer_profile):
    wallet = ensure_wallet(customer_profile)
    credit_wallet_deposit(wallet, 50_000, "idem-2")
    order_id = uuid4()
    reserve_for_order(wallet, 30_000, order_id, "res-1")
    with pytest.raises(ValueError):
        reserve_for_order(wallet, 30_000, order_id, "res-2")
