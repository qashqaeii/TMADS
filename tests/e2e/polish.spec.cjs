const { test, expect } = require('@playwright/test');
const username = process.env.TMADS_E2E_USERNAME;
const password = process.env.TMADS_E2E_PASSWORD;

async function assertPage(page, path) {
  const response = await page.goto(path);
  expect(response.status()).toBe(200);
  await expect(page.locator('body')).toHaveClass(/ui-final/);
  await expect(page.locator('#main-content')).toBeVisible();
  await expect(page.locator('#ui-confirmation')).toHaveCount(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true);
}

test('public pages and password visibility', async ({page}) => {
  for (const path of ['/', '/features/', '/how-it-works/', '/pricing/', '/faq/', '/contact/', '/about/', '/legal/terms/', '/legal/privacy/', '/legal/refund/', '/legal/content-policy/', '/accounts/register/', '/accounts/password-reset/']) {
    await assertPage(page, path);
  }
  await assertPage(page, '/accounts/login/');
  const input = page.locator('#id_password');
  await input.fill('local-test-only');
  await page.getByRole('button', {name:'نمایش رمز عبور', exact:true}).click();
  await expect(input).toHaveAttribute('type','text');
  await page.getByRole('button', {name:'پنهان کردن رمز عبور', exact:true}).click();
  await expect(input).toHaveAttribute('type','password');
});

test('customer workspace and local-only amount selector', async ({page}) => {
  test.skip(!username || !password, 'Set credentials for an isolated local customer.');
  await page.goto('/accounts/login/');
  await page.locator('#id_username').fill(username);
  await page.locator('#id_password').fill(password);
  await page.locator('form button[type="submit"]').click();
  await expect(page.locator('.ui-shell')).toBeVisible();
  for (const path of ['/app/', '/app/notifications/', '/campaigns/', '/finance/wallet/', '/finance/transactions/', '/finance/invoices/', '/finance/refunds/', '/support/', '/support/new/', '/accounts/profile/', '/accounts/advertiser-account/', '/accounts/advertiser-account/ads/', '/accounts/advertiser-assets/', '/app/ad-policies/']) {
    await assertPage(page, path);
    await expect(page.locator('.ui-shell')).toBeVisible();
  }
  await assertPage(page, '/finance/wallet/topup/');
  await page.locator('[data-amount="100000"]').click();
  await expect(page.locator('#topup-amount')).toHaveValue('100000');
  await expect(page.locator('[data-amount="100000"]')).toHaveAttribute('aria-pressed','true');
  await expect(page.locator('[data-topup-value]')).toBeVisible();
  // Deliberately do not submit payment, deletion, or Telegram actions.
});

test('draft confirmation cancellation', async ({page}) => {
  test.skip(!username || !password, 'Set local customer credentials.');
  await page.goto('/accounts/login/');
  await page.locator('#id_username').fill(username);
  await page.locator('#id_password').fill(password);
  await page.locator('form button[type="submit"]').click();
  await expect(page.locator('.ui-shell')).toBeVisible();
  await assertPage(page, '/campaigns/');
  const menu=page.locator('details').filter({has:page.locator('form[data-confirm-message]')}).first();
  if (await menu.count()) await menu.locator('summary').click();
  const action=page.locator('form[data-confirm-message] button[type="submit"]:visible').first();
  test.skip(!(await action.count()),'Seed a local draft to exercise cancellation.');
  await action.click();
  const dialog=page.locator('#ui-confirmation');
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button',{name:'انصراف',exact:true}).click();
  await expect(dialog).not.toBeVisible();
  await expect(page).toHaveURL(/\/campaigns\//);
});
