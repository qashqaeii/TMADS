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

test('Features Orbit hierarchy, image loading and native section navigation', async ({page}) => {
  test.setTimeout(60000);
  for (const width of [320, 768, 1440]) {
    await page.setViewportSize({width,height:900});
    await page.emulateMedia({reducedMotion:'reduce'});
    await assertPage(page,'/features/');
    await expect(page.locator('.fx-core-card')).toHaveCount(6);
    await expect(page.locator('.fx-advanced-card')).toHaveCount(4);
    await expect(page.locator('.fx-guide-card')).toHaveCount(4);
    await expect(page.locator('.fx-actions .btn-primary')).toHaveAttribute('href',/accounts\/register/);
    for (const art of await page.locator('[data-feature-art]:visible').all()) {
      await art.scrollIntoViewIfNeeded();
      await expect.poll(() => art.evaluate(el => el.complete && el.naturalWidth > 0)).toBe(true);
    }
    await page.locator('.fx-section-nav a[href="#features-advanced"]').click();
    await expect(page).toHaveURL(/#features-advanced$/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth+2)).toBe(true);
  }
});

test('Features Orbit motion and reduced motion cleanup', async ({page}) => {
  await page.setViewportSize({width:1440,height:900});
  await page.emulateMedia({reducedMotion:'no-preference'});
  await assertPage(page,'/features/');
  await expect(page.locator('body')).toHaveClass(/fx-motion-ready/);
  const card=page.locator('.fx-core-card').first();
  await card.scrollIntoViewIfNeeded();
  await card.hover();
  await expect(card).toHaveClass(/fx-spot-active/);
  await expect.poll(() => card.evaluate(el=>el.style.getPropertyValue('--fx-x'))).not.toBe('');
  await page.emulateMedia({reducedMotion:'reduce'});
  await expect(card).not.toHaveClass(/fx-spot-active/);
  await expect(page.locator('.fx-hero h1')).toBeVisible();
  await page.goto('/');
  await expect(page.locator('body')).not.toHaveClass(/fx-motion-ready/);
});

test.describe('Features no-script experience',()=>{
  test.use({javaScriptEnabled:false});
  test('copy, section links and CTAs remain available',async ({page})=>{
    await page.goto('/features/');
    await expect(page.locator('.fx-hero h1')).toBeVisible();
    await page.locator('.fx-section-nav a[href="#advertiser-toolkit"]').click();
    await expect(page).toHaveURL(/#advertiser-toolkit$/);
    await expect(page.locator('.fx-cta-button')).toBeVisible();
  });
});


test('Transparent feature artwork has no masks or frames and stays clear of text', async ({page}) => {
  test.setTimeout(60000);
  for (const width of [320, 768, 1440]) {
    await page.setViewportSize({width,height:900});
    await page.emulateMedia({reducedMotion:'reduce'});
    await assertPage(page,'/features/');
    await expect(page.locator('.fx-hero-art')).toHaveAttribute('src', /telegram_glassmorphism_analytics_hero(?:\.optimized)?\.webp/);
    const art=page.locator('.fx-page :is(.fx-hero-art,.fx-card-art,.fx-advanced-art,.fx-guide-art,.fx-cta-illustration)');
    for (const image of await art.all()) {
      await image.scrollIntoViewIfNeeded();
      await expect.poll(() => image.evaluate(el=>el.complete && el.naturalWidth>0)).toBe(true);
      const style=await image.evaluate(el=>({mask:getComputedStyle(el).maskImage,fit:getComputedStyle(el).objectFit}));
      expect(style.mask).toBe('none');
      expect(style.fit).toBe('contain');
    }
    const collisions=await page.locator('.fx-core-card').evaluateAll(cards=>cards.map(card=>{
      const a=card.querySelector('.fx-core-visual').getBoundingClientRect();
      const b=card.querySelector('.fx-card-copy').getBoundingClientRect();
      return Math.max(0,Math.min(a.right,b.right)-Math.max(a.left,b.left))*Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top));
    }));
    expect(collisions.every(area=>area<2)).toBe(true);
    await expect(page.locator('.fx-hero-image')).toHaveCSS('background-color','rgba(0, 0, 0, 0)');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2)).toBe(true);
  }
});


test('Pricing Orbit renders transparent art and calculator at mobile, tablet and desktop widths', async ({page})=>{
  test.setTimeout(60000);
  for(const width of [320,768,1440]){
    await page.setViewportSize({width,height:900});
    await page.emulateMedia({reducedMotion:'reduce'});
    await assertPage(page,'/pricing/');
    await expect(page.locator('.pr-calculator')).toBeVisible();
    await expect(page.locator('#pr-calc-example')).toBeHidden();
    for(const art of await page.locator('[data-pricing-art]').all()){
      await art.scrollIntoViewIfNeeded();
      await expect.poll(()=>art.evaluate(img=>img.complete&&img.naturalWidth>0)).toBe(true);
      const style=await art.evaluate(img=>({mask:getComputedStyle(img).maskImage,fit:getComputedStyle(img).objectFit}));
      expect(style).toEqual({mask:'none',fit:'contain'});
    }
    await page.locator('#pr-budget').fill('۱۲٫۵');
    await page.locator('#pr-cpm').fill('۰٫۵');
    await page.locator('#pr-impressions').fill('۱۰٬۰۰۰');
    await expect(page.locator('#pr-view-result')).toHaveText('۲۵٬۰۰۰');
    await expect(page.locator('#pr-cost-result')).toHaveText('۵');
    await page.locator('#pr-cpm').fill('0');
    await expect(page.locator('#pr-view-result')).toHaveText('—');
    await expect(page.locator('#pr-cost-result')).toHaveText('—');
    await expect(page.locator('#pr-cpm')).toHaveAttribute('aria-invalid','true');
    await page.locator('[data-pr-reset]').click();
    await expect(page.locator('#pr-view-result')).toHaveText('۱۰٬۰۰۰');
    await expect(page.locator('#pr-cost-result')).toHaveText('۲۰');
    await page.locator('.pr-section-nav a[href="#budget-decisions"]').click();
    await expect(page).toHaveURL(/#budget-decisions$/);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2)).toBe(true);
  }
});

test('Pricing Orbit spotlight respects reduced motion',async ({page})=>{
  await page.setViewportSize({width:1440,height:900});
  await page.emulateMedia({reducedMotion:'no-preference'});
  await assertPage(page,'/pricing/');
  await expect(page.locator('body')).toHaveClass(/pr-motion-ready/);
  const card=page.locator('.pr-fee');
  await card.scrollIntoViewIfNeeded();
  await card.hover();
  await expect(card).toHaveClass(/pr-spot-active/);
  await page.emulateMedia({reducedMotion:'reduce'});
  await expect(card).not.toHaveClass(/pr-spot-active/);
});

test.describe('Pricing no-script experience',()=>{
  test.use({javaScriptEnabled:false});
  test('educational example and CTAs remain available',async({page})=>{
    await page.goto('/pricing/');
    await expect(page.locator('#pr-calc-example')).toBeVisible();
    await expect(page.locator('[data-pr-calculator]')).toBeHidden();
    await expect(page.locator('.pr-actions .btn-primary')).toHaveAttribute('href',/accounts\/register/);
    await page.locator('.pr-detail summary').first().click();
    await expect(page.locator('.pr-detail').first()).toHaveAttribute('open','');
  });
});


test('Workflow journey and educational checklist at three viewport sizes',async({page})=>{
  test.setTimeout(60000);
  for(const width of [320,768,1440]){
    await page.setViewportSize({width,height:900});
    await page.emulateMedia({reducedMotion:'reduce'});
    await assertPage(page,'/how-it-works/');
    await expect(page.locator('.wf-step')).toHaveCount(6);
    await expect(page.locator('[data-wf-check]')).toHaveCount(5);
    for(const art of await page.locator('[data-workflow-art]').all()){
      await art.scrollIntoViewIfNeeded();
      await expect.poll(()=>art.evaluate(img=>img.complete&&img.naturalWidth>0)).toBe(true);
      expect(await art.evaluate(img=>getComputedStyle(img).objectFit)).toBe('contain');
    }
    await page.locator('.wf-section-nav a[href="#campaign-playbook"]').click();
    await expect(page).toHaveURL(/#campaign-playbook$/);
    await page.locator('[data-wf-check]').nth(0).check();
    await page.locator('[data-wf-check]').nth(1).check();
    await expect(page.locator('[data-wf-count]')).toHaveText('۲ از ۵');
    await expect(page.locator('progress')).toHaveAttribute('value','2');
    await page.locator('[data-wf-reset]').click();
    await expect(page.locator('[data-wf-count]')).toHaveText('۰ از ۵');
    await expect(page.locator('[data-wf-check]:checked')).toHaveCount(0);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2)).toBe(true);
  }
});

test('Workflow motion is disabled by reduced motion',async({page})=>{
  await page.setViewportSize({width:1440,height:900});
  await page.emulateMedia({reducedMotion:'no-preference'});
  await assertPage(page,'/how-it-works/');
  const card=page.locator('.wf-step').first();
  await card.scrollIntoViewIfNeeded();
  await card.hover();
  await expect(card).toHaveClass(/wf-spot-active/);
  await page.emulateMedia({reducedMotion:'reduce'});
  await expect(card).not.toHaveClass(/wf-spot-active/);
});

test.describe('Workflow no-script experience',()=>{
  test.use({javaScriptEnabled:false});
  test('all steps and guidance remain readable',async({page})=>{
    await page.goto('/how-it-works/');
    await expect(page.locator('.wf-step')).toHaveCount(6);
    await expect(page.locator('.wf-check-item')).toHaveCount(5);
    await expect(page.locator('[data-wf-progress]')).toBeHidden();
    await expect(page.locator('.wf-actions .btn-primary')).toHaveAttribute('href',/accounts\/register/);
    await page.locator('.wf-section-nav a[href="#guide-preparation"]').click();
    await expect(page).toHaveURL(/#guide-preparation$/);
  });
});


test('FAQ Orbit category, Persian search and keyboard accordion at three widths',async({page})=>{
  test.setTimeout(60000);
  for(const width of [320,768,1440]){
    await page.setViewportSize({width,height:900});
    await page.emulateMedia({reducedMotion:'reduce'});
    await assertPage(page,'/faq/');
    const questions=page.locator('[data-fq-question]');
    await expect(questions).toHaveCount(16);
    const query=page.locator('#pp-faq-query');
    const category=page.locator('[data-fq-category="finance"]');
    await category.click();
    await expect(category).toHaveAttribute('aria-pressed','true');
    await expect(page.locator('[data-fq-question]:visible')).toHaveCount(4);
    await query.fill('cpm');
    await expect(page.locator('[data-fq-question]:visible')).toHaveCount(1);
    const result=page.locator('[data-fq-question]:visible').first();
    await result.locator('summary').focus();
    await page.keyboard.press('Enter');
    await expect(result).toHaveAttribute('open','');
    await query.fill('zzzznotfound');
    await expect(page.locator('[data-fq-empty]')).toBeVisible();
    await page.locator('[data-fq-reset]').click();
    await expect(query).toHaveValue('');
    await expect(page.locator('[data-fq-question]:visible')).toHaveCount(16);
    await query.fill('كيف پول');
    await expect.poll(()=>page.locator('[data-fq-question]:visible').count()).toBeGreaterThan(0);
    await page.locator('[data-fq-clear]').click();
    await expect(page.locator('[data-fq-question]:visible')).toHaveCount(16);
    for(const image of await page.locator('[data-faq-art]:visible').all()){
      await image.scrollIntoViewIfNeeded();
      await expect.poll(()=>image.evaluate(el=>el.complete&&el.naturalWidth>0)).toBe(true);
      expect(await image.evaluate(el=>getComputedStyle(el).objectFit)).toBe('contain');
    }
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2)).toBe(true);
  }
});
test('FAQ Orbit motion honors reduced motion',async({page})=>{
  await page.setViewportSize({width:1440,height:900});
  await page.emulateMedia({reducedMotion:'no-preference'});
  await assertPage(page,'/faq/');
  await expect(page.locator('body')).toHaveClass(/fq-motion-ready/);
  const card=page.locator('.fq-guide-card').first();
  await card.scrollIntoViewIfNeeded();
  await card.hover();
  await expect(card).toHaveClass(/fq-spot-active/);
  await page.emulateMedia({reducedMotion:'reduce'});
  await expect(card).not.toHaveClass(/fq-spot-active/);
});
test.describe('FAQ without JavaScript',()=>{
  test.use({javaScriptEnabled:false});
  test('answers and support remain accessible',async({page})=>{
    await page.goto('/faq/');
    await expect(page.locator('[data-fq-question]:visible')).toHaveCount(16);
    await expect(page.locator('[data-pp-faq-search]')).toBeHidden();
    const first=page.locator('[data-fq-question]').first();
    await first.locator('summary').click();
    await expect(first).toHaveAttribute('open','');
    await expect(page.locator('.fq-support a')).toHaveAttribute('href',/contact/);
  });
});


test('Orbit legal documents retain semantic sections and responsive navigation', async ({page})=>{
  test.setTimeout(60000);
  for(const width of [320,768,1440]){
    await page.setViewportSize({width,height:900});
    await page.emulateMedia({reducedMotion:'reduce'});
    for(const path of ['/legal/terms/','/legal/privacy/','/legal/refund/','/legal/content-policy/']){
      await assertPage(page,path);
      await expect(page.locator('.lg-tabs a[aria-current="page"]')).toHaveCount(1);
      await expect(page.locator('#legal-document')).toBeVisible();
      await expect(page.locator('[data-legal-print]')).toBeVisible();
      const art=page.locator('.lg-hero-scene img');
      await expect.poll(()=>art.evaluate(img=>img.complete&&img.naturalWidth>0)).toBe(true);
      const toc=page.locator('[data-legal-section-link]').last();
      const hash=await toc.getAttribute('href');
      await toc.click();
      expect(new URL(page.url()).hash).toBe(hash);
      await expect(page.locator(hash)).toBeVisible();
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2)).toBe(true);
    }
  }
});

test('Legal print is invoked without requesting a server action', async ({page})=>{
  await page.addInitScript(()=>{window.print=()=>{window.__legalPrintCalled=true;};});
  await page.goto('/legal/terms/');
  await page.locator('[data-legal-print]').click();
  expect(await page.evaluate(()=>window.__legalPrintCalled)).toBe(true);
});

test.describe('Legal content without JavaScript',()=>{
  test.use({javaScriptEnabled:false});
  test('native contents links and visible clauses',async({page})=>{
    await page.goto('/legal/terms/');
    await expect(page.locator('.lg-clause')).toHaveCount(4);
    await expect(page.locator('[data-legal-print]')).toBeHidden();
    await page.locator('a[href="#legal-clause-4"]').click();
    await expect(page).toHaveURL(/#legal-clause-4$/);
    await expect(page.locator('#legal-clause-4')).toBeVisible();
  });
});
