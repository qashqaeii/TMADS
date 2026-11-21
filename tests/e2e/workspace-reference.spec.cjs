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
        if (role === 'ops') {
          await expect(page.locator('.sidebar-admin-group')).toHaveAttribute('open', '');
          await expect(page.locator('.ga-ops-premium')).toBeVisible();
          if (route === '/ops/') {
            const cards = page.locator('.ga-ops-center-metrics .kpi-exec');
            await expect(cards).toHaveCount(4);
            for (const card of await cards.all()) {
              const geometry = await card.evaluate(el => {
                const rect = node => {
                  const r = node.getBoundingClientRect();
                  return {left:r.left,right:r.right,top:r.top,bottom:r.bottom};
                };
                const intersects = (a,b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
                const cardRect = rect(el), labelRect = rect(el.querySelector('.kpi-exec__label'));
                const valueRect = rect(el.querySelector('.kpi-exec__value'));
                const iconRect = rect(el.querySelector('.kpi-exec__icon'));
                return {labelValue:intersects(labelRect,valueRect),iconValue:intersects(iconRect,valueRect),
                  contained:valueRect.left>=cardRect.left-1 && valueRect.right<=cardRect.right+1};
              });
              expect(geometry.labelValue).toBe(false);
              expect(geometry.iconValue).toBe(false);
              expect(geometry.contained).toBe(true);
            }
          }
          if (route === '/ops/campaigns/' || route === '/ops/refunds/') {
            const actions = page.locator('.ops-filter-actions');
            await expect(actions).toBeVisible();
            expect(await actions.evaluate(el => el.parentElement.classList.contains('filter-exec__grid'))).toBe(true);
          }
          if (route === '/ops/remote-operations/' || route === '/ops/related-accounts/') {
            await expect(page.locator('.ops-queue-empty')).toBeVisible();
            await expect(page.locator('.ops-pager')).toHaveCount(0);
            const emptyHeight = (await page.locator('.ops-queue-empty').boundingBox()).height;
            expect(emptyHeight).toBeLessThan(190);
            if (route === '/ops/remote-operations/') {
              const filterHeight = (await page.locator('.ops-remote-filter').boundingBox()).height;
              expect(filterHeight).toBeLessThan(width < 800 ? 180 : 125);
            }
          }
          if (route === '/ops/api-status/' && !(await page.locator('.ops-api-account').count())) {
            const layout = await page.locator('.ops-api-layout').boundingBox();
            const capabilities = await page.locator('.ops-api-capabilities').boundingBox();
            expect(capabilities.width).toBeGreaterThan(layout.width * .95);
          }
          if (route === '/ops/exchange-rates/') {
            const columns = await page.locator('.ops-rate-metrics').evaluate(el => getComputedStyle(el).gridTemplateColumns.trim().split(' ').length);
            expect(columns).toBe(width <= 560 ? 1 : width <= 800 ? 2 : 3);
            const metrics = page.locator('.ops-rate-metrics .kpi-exec');
            await expect(metrics).toHaveCount(5);
            for (const card of await metrics.all()) {
              const geometry = await card.evaluate(el => {
                const a=el.querySelector('.kpi-exec__label').getBoundingClientRect();
                const value=el.querySelector('.kpi-exec__value');
                const b=value.getBoundingClientRect();
                const body=el.querySelector('.kpi-exec__body');
                return {overlap:a.left<b.right && a.right>b.left && a.top<b.bottom && a.bottom>b.top,
                  valueInside:b.left>=el.getBoundingClientRect().left-1 && b.right<=el.getBoundingClientRect().right+1,
                  bodyRatio:body.getBoundingClientRect().width/el.getBoundingClientRect().width,
                  valueOverflow:value.scrollWidth>value.clientWidth+1};
              });
              expect(geometry.overlap).toBe(false);
              expect(geometry.valueInside).toBe(true);
              expect(geometry.bodyRatio).toBeGreaterThan(.55);
              expect(geometry.valueOverflow).toBe(false);
            }
          }
          if (route === '/ops/api-status/') {
            const status = page.locator('.ops-api-capabilities .ops-api-table .status').first();
            await expect(status).toBeVisible();
            expect(await status.evaluate(el => getComputedStyle(el).whiteSpace)).toBe('nowrap');
          }
          if (route === '/ops/sms/') {
            await expect(page.locator('.ops-sms-metrics .sms-kpi')).toHaveCount(4);
            await expect(page.locator('.sms-kpi__icon')).toHaveCount(4);
          }
        }
        await expect(page.locator('#main-content')).toBeVisible();
        const titleRow = page.locator('.ga-ops-premium .dash-header__title-row').first();
        const subtitle = page.locator('.ga-ops-premium .dash-header .page-sub').first();
        const titleCount = await titleRow.count();
        const subtitleCount = await subtitle.count();
        if (titleCount && subtitleCount) {
          const titleBox = await titleRow.boundingBox();
          const subtitleBox = await subtitle.boundingBox();
          expect(subtitleBox.y).toBeGreaterThanOrEqual(titleBox.y + titleBox.height - 1);
        }
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

test('operator Telegram account facts wrap long values without overlap', async ({page}, testInfo) => {
  test.skip(!users.ops.every(Boolean), 'Requires disposable local operator credentials');
  await login(page, users.ops);
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({width, height:900});
    await page.goto('/ops/api-status/', {waitUntil:'domcontentloaded'});
    await expect(page.locator('.ops-api-layout')).toBeVisible();
    await page.locator('.ops-api-layout').evaluate(root => {
      const panel=document.createElement('section');
      panel.className='ga-panel ops-api-account';
      const body=document.createElement('div');
      body.className='ga-panel-body ga-api-facts ops-api-facts';
      const facts=[
        ['عنوان','GramAds Central Account'],
        ['ارز','TON'],
        ['مصرف کل','0.125000 TON'],
        ['باقی‌مانده','0.00000012 TON'],
        ['بودجه تبلیغات','123456789.123456 TON'],
        ['شناسه حساب','bj4KvgRwQRW28yLry1O2MrBSH2BBvETPnewLPT8s'],
      ];
      for(const [label,value] of facts){
        const line=document.createElement('div');line.className='finance-line';
        const key=document.createElement('span');key.textContent=label;
        const val=label==='شناسه حساب'?document.createElement('code'):document.createElement('strong');
        if(label==='شناسه حساب')val.dir='ltr';
        val.textContent=value;line.append(key,val);body.append(line);
      }
      panel.append(body);root.prepend(panel);
    });
    const facts=await page.locator('.ops-api-facts .finance-line').evaluateAll(cards=>cards.map(card=>{
      const label=card.querySelector('span').getBoundingClientRect();
      const value=card.querySelector('strong,code').getBoundingClientRect();
      const box=card.getBoundingClientRect();
      return {stacked:label.bottom<=value.top+2,inside:value.left>=box.left-1&&value.right<=box.right+1,
        noOverflow:card.scrollWidth<=card.clientWidth+1};
    }));
    expect(facts).toHaveLength(6);
    for(const fact of facts){expect(fact.stacked).toBe(true);expect(fact.inside).toBe(true);expect(fact.noOverflow).toBe(true);}
    const chip=page.locator('.ops-api-capabilities .ops-api-table .status').first();
    await expect(chip).toBeVisible();
    expect(await chip.evaluate(el=>getComputedStyle(el).whiteSpace)).toBe('nowrap');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
    if(process.env.TMADS_E2E_CAPTURE==='1'){
      await page.evaluate(()=>document.fonts.ready);
      await page.screenshot({path:testInfo.outputPath('ops-api-facts-'+width+'.png'),fullPage:true,animations:'disabled'});
    }
  }
});
