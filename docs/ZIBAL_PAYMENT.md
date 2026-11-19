# Zibal payment setup and recovery

The gateway adapter follows the existing Divarfiling Zibal integration and uses integer IRR. Customer input is Toman (x10). No merchant secret is committed. Set these on the deployment environment only:

```dotenv
PAYMENT_GATEWAY=zibal
PAYMENT_FAKE_ENABLED=false
ZIBAL_MERCHANT_ID=<merchant-from-zibal-panel>
PUBLIC_SITE_URL=https://your-registered-domain.example
```

The literal test merchant `zibal` is blocked in production. Keep the existing local fake configuration for automated tests. Register the actual domain and any required outbound server IP in Zibal's panel. The customer must follow the same-origin handoff link to the HTTPS Zibal gateway; no card data is collected here.

Callback: `/finance/wallet/topup/<payment-uuid>/zibal/return/` (see URLConf for mount). It checks the stored track ID and accepts a result only after the server verifies exact IRR and a bank reference. Amount mismatch and unknown responses remain pending. Duplicate callbacks cannot credit twice. The receipt is private; the callback can recover after session loss.

## Recovery
Customers can recheck a pending payment from Wallet > Recent bank payments. Operators can inspect a payment without a network call:

```bash
python manage.py reconcile_zibal --payment-id <uuid>
```

Use `--apply` only after confirming the attempt; it verifies the existing track, never creates another charge. Verified transactions must not be manually edited. For unknown/failed attempts investigate with the provider before requesting another payment. If a verification or invoice operation fails, the wallet update is rolled back.

## Release acceptance (not performed by mocked CI)
- Obtain current API contract from Zibal panel, confirm 201/inquiry settlement fields and status semantics against live documentation.
- Test success, cancellation, return after logout, provider timeout/recovery, actual bank reference and balance/invoice reconciliation with authorized low-value transactions.
- Verify responsive pages and referrer behavior on the deployed domain.
- Reconcile provider dashboard and wallet ledger; monitor pending payments.
