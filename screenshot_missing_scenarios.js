/**
 * Capture screenshots for missing scenarios: 13-18, 22-26, 28, 31-33, 35
 * Output: screenshots/scenarios/
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost:3000';
const API_URL  = 'http://localhost:8000';
const OUT_DIR  = path.join(__dirname, 'screenshots', 'scenarios');
fs.mkdirSync(OUT_DIR, { recursive: true });

const MISSING_SCENARIOS = [
  { id: 'scenario-13', name: 'Material Porosity p1 Sample 3'       },
  { id: 'scenario-14', name: 'Machining Lines Tool Marks p1 Sample 9' },
  { id: 'scenario-15', name: 'Coating Stain p4 Sample 4'           },
  { id: 'scenario-16', name: 'Label SN Mismatch p2 Sample 5'       },
  { id: 'scenario-17', name: 'Machining Burr p6 Sample 3'          },
  { id: 'scenario-18', name: 'Paint Peel Off p3 Sample 4'          },
  { id: 'scenario-22', name: 'Machining Burr p1 Sample 6'          },
  { id: 'scenario-23', name: 'Scratch Marks p1 Sample 7'           },
  { id: 'scenario-24', name: 'Machining Burr p1 Sample 8'          },
  { id: 'scenario-25', name: 'Label SN Mismatch p2 Sample 3'       },
  { id: 'scenario-26', name: 'Label SN Mismatch p2 Sample 7'       },
  { id: 'scenario-28', name: 'Dent Impact Damage p3 Sample 3'      },
  { id: 'scenario-31', name: 'Machining Burr p6 Sample 2'          },
  { id: 'scenario-32', name: 'Machining Burr p6 Sample 4'          },
  { id: 'scenario-33', name: 'Coating Stain p4 Sample 2'           },
  { id: 'scenario-35', name: 'Poor Coating Finish p5 Sample 3'     },
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

  for (const s of MISSING_SCENARIOS) {
    console.log(`\n[${s.id}] ${s.name}`);
    const base = `${s.id}-${slug(s.name)}`;

    // Run scenario via API
    const res = await fetch(`${API_URL}/api/v1/demo/scenarios/${s.id}/run`, { method: 'POST' });
    const data = await res.json();
    const iid = data.inspection_id;
    if (!iid) {
      console.log(`  ✗ Failed to get inspection_id: ${JSON.stringify(data)}`);
      continue;
    }
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

    // Reset overlays
    await setOverlay(page, 'XAI Heatmap', false);
    await setOverlay(page, 'Golden Diff', false);
  }

  await browser.close();
  console.log(`\nDone. Screenshots saved to ${OUT_DIR}`);
}

main().catch(e => { console.error(e); process.exit(1); });
