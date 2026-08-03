/**
 * Capture screenshots for the 7 newly added scenarios.
 * Output: screenshots/scenarios/
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost:3000';
const API_URL  = 'http://localhost:8000';
const OUT_DIR  = path.join(__dirname, 'screenshots', 'scenarios');
fs.mkdirSync(OUT_DIR, { recursive: true });

const NEW_SCENARIOS = [
  { id: 'scenario-19', name: 'Material Porosity p1 Sample 2'  },
  { id: 'scenario-20', name: 'Dent Impact Damage p1 Sample 4' },
  { id: 'scenario-21', name: 'Tool Marks p1 Sample 5'         },
  { id: 'scenario-27', name: 'Scratch Marks p3 Sample 2'      },
  { id: 'scenario-29', name: 'Coating Stain p4 Sample 5'      },
  { id: 'scenario-30', name: 'Color Variation p5 Sample 2'    },
  { id: 'scenario-34', name: 'Coating Stain p4 Sample 3'      },
];

function slug(n) { return n.toLowerCase().replace(/[^a-z0-9]+/g, '-'); }

async function setOverlay(page, btn, on) {
  const el = page.locator(`button:has-text("${btn}")`);
  const cls = await el.getAttribute('class').catch(() => '');
  const active = cls.includes('bg-lam') || cls.includes('bg-primary') || cls.includes('default');
  if (active !== on) { await el.click().catch(() => {}); await page.waitForTimeout(400); }
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  // Login as operator
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' }).catch(() => {});
  await page.locator('text=Operator').first().click().catch(() => {});
  await page.waitForTimeout(1000);

  for (const s of NEW_SCENARIOS) {
    console.log(`\n[${s.id}] ${s.name}`);
    const base = `${s.id}-${slug(s.name)}`;

    // Run scenario via API
    const res = await fetch(`${API_URL}/api/v1/demo/scenarios/${s.id}/run`, { method: 'POST' });
    const data = await res.json();
    const iid = data.inspection_id;
    console.log(`  inspection: ${iid}`);

    await page.goto(`${BASE_URL}/review/${iid}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2500);

    // 1. Bounding Box only
    await setOverlay(page, 'XAI Heatmap', false);
    await setOverlay(page, 'Golden Diff', false);
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(OUT_DIR, `${base}-bbox.png`) });
    console.log(`  ✓ bbox`);

    // 2. Heatmap only
    await setOverlay(page, 'XAI Heatmap', true);
    await setOverlay(page, 'Golden Diff', false);
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(OUT_DIR, `${base}-heatmap.png`) });
    console.log(`  ✓ heatmap`);

    // 3. Golden Diff only
    await setOverlay(page, 'XAI Heatmap', false);
    await setOverlay(page, 'Golden Diff', true);
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(OUT_DIR, `${base}-golden.png`) });
    console.log(`  ✓ golden diff`);

    // Reset
    await setOverlay(page, 'XAI Heatmap', false);
    await setOverlay(page, 'Golden Diff', false);
  }

  await browser.close();
  console.log(`\nDone. Screenshots saved to ${OUT_DIR}`);
}

main().catch(e => { console.error(e); process.exit(1); });
