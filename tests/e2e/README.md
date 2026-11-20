# UI regression browser suite (isolated LOCAL environment only)

Run the Django server against a disposable local database, with fake payments, Telegram writes and paid submissions disabled. Do not run against production or reuse production credentials. Seed a local customer and an editable draft to exercise the authenticated scenarios.

```powershell
cd D:\MYROBOTS\TMADS\tests\e2e
npm install
npx playwright install chromium
$env:TMADS_E2E_URL="http://127.0.0.1:8000"
$env:TMADS_E2E_USERNAME="your-local-test-user"
# Set TMADS_E2E_PASSWORD locally before running; never commit it.
npm test
```

Public pages, password visibility, customer navigation, local amount selection and draft dialog cancellation at 390, 768 and 1440px. No actual financial or Telegram write is performed by these tests. The customer and draft tests explicitly skip when their required fixture is absent. Screenshots and traces are generated on failure. Manual visual review, staff review, all wizard stages, accessibility, populated/empty/error and real sandbox-provider paths remain necessary. Run Django regression tests separately with pytest.

## GramAds workspace reference
The responsive route sweep covers all requested customer and operator sections at 375, 768 and 1440px. Set `TMADS_E2E_OPS_USERNAME` and `TMADS_E2E_OPS_PASSWORD` for a disposable authorized operator. The synthetic confirmation test opens and cancels a local form without submitting any server action. The workspace project is now explicitly included in Playwright. The separate workspace visual workflow runs against an isolated database and captures full-page screenshots for review. Automated geometry checks are not a visual sign-off.

```powershell
npx playwright test --project=workspace
```
