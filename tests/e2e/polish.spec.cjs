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

test('public studio compact auth and responsive layouts', async ({page}) => {
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({width, height: 900});
    for (const path of ['/', '/features/', '/accounts/login/', '/accounts/register/']) {
      await assertPage(page, path);
      await expect(page.locator('h1')).toHaveCount(1);
    }
    await expect(page.locator('.studio-auth-header')).toBeVisible();
    await expect(page.locator('#id_username')).toBeVisible();
    await expect(page.locator('#id_password1')).toHaveAttribute('type', 'password');
    await expect(page.locator('.ui-password-toggle')).toHaveCount(2);
    await assertPage(page, '/accounts/login/');
    await expect(page.locator('[data-pp-password-toggle]')).toHaveCount(1);
    await expect(page.locator('.ui-password-toggle')).toHaveCount(0);
    await page.locator('#id_password').fill('local-test-only');
    await page.getByRole('button', {name:'نمایش رمز عبور', exact:true}).click();
    await expect(page.locator('#id_password')).toHaveAttribute('type','text');
    await expect(page.locator('[data-pp-password-toggle]')).toHaveAttribute('aria-pressed','true');
  }
});

test('Orbit landing artwork, CTA and FAQ work across viewports', async ({page}) => {
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({width, height: 900});
    await assertPage(page, '/');
    await expect(page.locator('.orbit-hero h1')).toBeVisible();
    await expect(page.locator('.orbit-actions .btn-primary')).toHaveAttribute('href', /accounts\/register/);
    for (const art of await page.locator('[data-landing-art]').all()) {
      await art.scrollIntoViewIfNeeded();
      await expect.poll(async () => art.evaluate(img => img.complete && img.naturalWidth > 0)).toBe(true);
    }
    await page.locator('#home-faq summary').first().click();
    await expect(page.locator('#home-faq details').first()).toHaveAttribute('open', '');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true);
  }
});


test('Orbit glass surfaces, pointer lighting and motion preferences', async ({page}) => {
  await page.setViewportSize({width: 1440, height: 900});
  await page.emulateMedia({reducedMotion: 'no-preference'});
  await assertPage(page, '/');
  await expect(page.locator('body')).toHaveClass(/orbit-motion-ready/);
  await expect(page.locator('.orbit-hero-art')).toBeVisible();
  const card = page.locator('.orbit-target').first();
  await card.scrollIntoViewIfNeeded();
  await card.hover();
  await expect(card).toHaveClass(/orbit-spot-active/);
  await expect.poll(() => card.evaluate(el => el.style.getPropertyValue('--spot-x'))).not.toBe('');
  const header = page.locator('.ui-public-header');
  await expect(header).toHaveClass(/orbit-nav-scrolled/);
  await expect.poll(() => header.evaluate(el => Number(el.style.getPropertyValue('--orbit-scroll')))).toBeGreaterThan(0);
  await page.emulateMedia({reducedMotion: 'reduce'});
  await expect(card).not.toHaveClass(/orbit-spot-active/);
  await expect.poll(() => header.evaluate(el => el.style.getPropertyValue('--orbit-scroll'))).toBe('');
  await expect(page.locator('.orbit-hero-copy h1')).toBeVisible();
  await page.goto('/features/');
  await expect(page.locator('body')).not.toHaveClass(/orbit-motion-ready/);
});

test('Orbit compact layout at 320px with native FAQ keyboard interaction', async ({page}) => {
  await page.setViewportSize({width: 320, height: 740});
  await page.emulateMedia({reducedMotion: 'reduce'});
  await assertPage(page, '/');
  await expect(page.locator('.orbit-target')).toHaveCount(4);
  for (const art of await page.locator('[data-landing-art]:visible').all()) {
    await art.scrollIntoViewIfNeeded();
    await expect.poll(() => art.evaluate(img => img.complete && img.naturalWidth > 0)).toBe(true);
  }
  const summary = page.locator('#home-faq summary').first();
  await summary.focus();
  await summary.press('Enter');
  await expect(page.locator('#home-faq details').first()).toHaveAttribute('open', '');
  await summary.press('Enter');
  await expect(page.locator('#home-faq details').first()).not.toHaveAttribute('open', '');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true);
});

test.describe('Orbit progressive fallback', () => {
  test.use({javaScriptEnabled: false});
  test('headings, conversion links and FAQ work without scripts', async ({page}) => {
    await page.goto('/');
    await expect(page.locator('.orbit-hero h1')).toBeVisible();
    await expect(page.locator('.orbit-actions .btn-primary')).toHaveAttribute('href', /accounts\/register/);
    await expect(page.locator('.orbit-cta-button')).toBeVisible();
    await page.locator('#home-faq summary').first().click();
    await expect(page.locator('#home-faq details').first()).toHaveAttribute('open', '');
  });
});
