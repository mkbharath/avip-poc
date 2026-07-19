const { chromium } = require('playwright');
const path = require('path');
const API_URL = 'http://localhost:8001';
const BASE_URL = 'http://localhost:3000';
const extraDir = path.join('screenshots', 'dashboards');

(async () => {
  await fetch(API_URL + '/api/v1/demo/reset', { method: 'POST' });
  console.log('Demo reset done');

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });

  // OCR Label Selection state
  console.log('OCR Label Selection...');
  await page.goto(BASE_URL + '/kiosk', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  await page.locator('button:has-text("OCR Capture")').first().click().catch(() => {});
  await page.waitForTimeout(2500);
  await page.screenshot({ path: extraDir + '/13-ocr-label-selection.png' });
  console.log('  ✓ 13-ocr-label-selection.png');

  // Select first valid label (not damaged/unknown)
  const labelBtns = page.locator('.grid-cols-5 button');
  const labelCount = await labelBtns.count();
  console.log(`  Found ${labelCount} label buttons`);

  if (labelCount > 0) {
    await labelBtns.first().click();
    await page.waitForTimeout(1200);
    await page.screenshot({ path: extraDir + '/14-ocr-label-selected.png' });
    console.log('  ✓ 14-ocr-label-selected.png');

    // Click Capture & Extract
    await page.locator('button:has-text("Capture & Extract")').click().catch(() => {});
    await page.waitForTimeout(5000);
    await page.screenshot({ path: extraDir + '/15-ocr-result.png' });
    console.log('  ✓ 15-ocr-result.png');
  }

  await browser.close();
  console.log('Done!');
})().catch(err => { console.error(err); process.exit(1); });
