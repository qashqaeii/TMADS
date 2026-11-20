const { defineConfig } = require('@playwright/test');
const baseURL = process.env.TMADS_E2E_URL || 'http://127.0.0.1:8000';
const target = new URL(baseURL);
if (!['127.0.0.1', 'localhost', '[::1]'].includes(target.hostname)) {
  throw new Error('UI smoke suite is restricted to an isolated local test server.');
}
module.exports = defineConfig({
  testDir: '.',
  timeout: 30000,
  use: { baseURL, browserName: 'chromium', screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  projects: [
    { name: 'mobile', testMatch: 'polish.spec.cjs', use: { viewport: { width: 390, height: 844 } } },
    { name: 'tablet', testMatch: 'polish.spec.cjs', use: { viewport: { width: 768, height: 1024 } } },
    { name: 'desktop', testMatch: 'polish.spec.cjs', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'workspace', testMatch: 'workspace-reference.spec.cjs', use: { viewport: { width: 1440, height: 900 } } },
  ],
});
