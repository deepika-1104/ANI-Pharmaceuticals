const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1400, height: 900 });
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 15000 });
  await page.screenshot({ path: 'pw_initial.png' });
  console.log('title:', await page.title());
  console.log('url:', page.url());
  const text = await page.textContent('body');
  console.log('body_snippet:', text.slice(0, 400));
  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
