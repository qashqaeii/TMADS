const {test, expect} = require('@playwright/test');
const users = {
  customer: [process.env.TMADS_E2E_USERNAME, process.env.TMADS_E2E_PASSWORD],
  ops: [process.env.TMADS_E2E_OPS_USERNAME, process.env.TMADS_E2E_OPS_PASSWORD],
};
const routes = {
  customer: ['/app/','/campaigns/','/accounts/advertiser-account/','/accounts/advertiser-assets/','/finance/wallet/','/finance/invoices/','/finance/refunds/','/finance/transactions/','/finance/wallet/topup/','/app/ad-policies/','/support/','/support/new/','/accounts/profile/','/accounts/profile/sms/','/app/notifications/'],
  ops: ['/ops/','/ops/campaigns/','/ops/remote-operations/','/ops/related-accounts/','/ops/telegram-account/','/ops/refunds/','/ops/exchange-rates/','/ops/sms/','/ops/api-status/','/ops/release-readiness/','/ops/audit/'],
};
async function login(page, credentials) {
  await page.goto('/accounts/login/');
  await page.locator('#id_username').fill(credentials[0]);
  await page.locator('#id_password').fill(credentials[1]);
  await page.locator('form button[type="submit"]').first().click();
  await expect(page.locator('.ui-shell')).toBeVisible();
}
for (const role of Object.keys(routes)) {
  test(role+' workspace reference — responsive route sweep', async ({page},testInfo) => {
    test.skip(!users[role].every(Boolean),'Requires disposable local '+role+' credentials');
    test.setTimeout(300000);
    await login(page,users[role]);
    await page.emulateMedia({reducedMotion:'reduce'});
    for(const width of [375,768,1440]){
      await page.setViewportSize({width,height:900});
      for(const route of routes[role]){
        const response=await page.goto(route,{waitUntil:'domcontentloaded'});
        expect(response.status(),route).toBe(200);
        expect(new URL(page.url()).pathname,route).toBe(route);
        await expect(page.locator('body')).toHaveClass(/ga-workspace-system/);
        await expect(page.locator('#main-content')).toBeVisible();
        await expect(page.locator('#ui-confirmation')).toHaveCount(1);
        expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),route+' @ '+width).toBe(true);
        const css=await page.locator('body').evaluate(el=>getComputedStyle(el).getPropertyValue('--gw-radius').trim());
        expect(css).toBe('15px');
        if (process.env.TMADS_E2E_CAPTURE === '1') {
          await page.evaluate(()=>document.fonts.ready);
          const file=route.replace(/^\/|\/$/g,'').replaceAll('/','-')||'root';
          await page.screenshot({path:testInfo.outputPath(role+'-'+width+'-'+file+'.png'),fullPage:true,animations:'disabled'});
        }
      }
    }
  });
}
test('shared confirmation closes with Escape and never submits on cancel',async({page})=>{
  test.skip(!users.customer.every(Boolean),'Requires disposable local customer credentials');
  await login(page,users.customer);
  await page.goto('/app/');
  await page.waitForFunction(()=>window.tmadsConfirmReady===true);
  await page.evaluate(()=>{
    const form=document.createElement('form');
    form.dataset.confirmMessage='Local UI test only';
    form.dataset.confirmTitle='تأیید آزمایشی';
    form.id='gw-test-confirm';
    const button=document.createElement('button');
    button.type='submit';
    button.textContent='Local confirmation';
    form.appendChild(button);
    form.addEventListener('submit',e=>e.preventDefault());
    document.getElementById('main-content').prepend(form);
  });
  const trigger=page.locator('#gw-test-confirm button');
  await page.emulateMedia({reducedMotion:'reduce'});
  await trigger.click();
  const dialog=page.locator('#ui-confirmation');
  await expect(dialog).toBeVisible();
  expect(await dialog.evaluate(el=>getComputedStyle(el).animationName)).toBe('none');
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
  await trigger.click();
  await dialog.getByRole('button',{name:'انصراف',exact:true}).click();
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
});
