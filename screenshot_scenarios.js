/**
 * AVIP POC — Full Screenshot Automation
 * 
 * Captures:
 *  - Each scenario: 4 shots (bbox, heatmap, golden diff, all three combined)
 *  - Dashboard screens: Inspections, Defects, Suppliers, AI Performance, Review Queue
 * 
 * Usage: node screenshot_scenarios.js
 * Output: screenshots/
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost:3000';
const API_URL  = 'http://localhost:8000';
const OUTPUT_DIR = path.join(__dirname, 'screenshots');

const SCENARIOS = [
  { id: 'scenario-01', name: 'Clean Machined Plate',           decision: 'PASS' },
  { id: 'scenario-02', name: 'Scratched Plate',                decision: 'FAIL' },
  { id: 'scenario-03', name: 'Dented Housing',                 decision: 'FAIL' },
  { id: 'scenario-04', name: 'Missing Screw',                  decision: 'FAIL' },
  { id: 'scenario-05', name: 'Surface Contamination',          decision: 'FAIL' },
  { id: 'scenario-06', name: 'Unknown Anomaly',                decision: 'REVIEW' },
  { id: 'scenario-07', name: 'Golden Deviation',               decision: 'REVIEW' },
  { id: 'scenario-08', name: 'Multi-Defect PCB',               decision: 'FAIL' },
  { id: 'scenario-09', name: 'Low-Confidence Edge Case',       decision: 'REVIEW' },
  { id: 'scenario-10', name: 'Override Scenario',              decision: 'FAIL' },
  { id: 'scenario-11', name: 'Solder Bridge RF Board',         decision: 'FAIL' },
  { id: 'scenario-12', name: 'Cold Solder Joint Power Board',  decision: 'FAIL' },
  { id: 'scenario-19', name: 'Material Porosity p1 Sample 2',       decision: 'FAIL' },
  { id: 'scenario-20', name: 'Dent Impact Damage p1 Sample 4',      decision: 'FAIL' },
  { id: 'scenario-21', name: 'Tool Marks p1 Sample 5',              decision: 'FAIL' },
  { id: 'scenario-27', name: 'Scratch Marks p3 Sample 2',           decision: 'FAIL' },
  { id: 'scenario-29', name: 'Coating Stain p4 Sample 5',           decision: 'FAIL' },
  { id: 'scenario-30', name: 'Color Variation p5 Sample 2',         decision: 'FAIL' },
  { id: 'scenario-34', name: 'Coating Stain p4 Sample 3',           decision: 'FAIL' },
];

const DASHBOARDS = [
  { name: '00-login',           url: '/login',                 label: 'Login Screen' },
  { name: '01-station-kiosk',   url: '/kiosk',                 label: 'Station Kiosk (Scan)' },
  { name: '02-review-queue',    url: '/review',                label: 'Review Queue' },
  { name: '03-inspections',     url: '/dashboard/inspection',  label: 'Inspections Dashboard' },
  { name: '04-defects',         url: '/dashboard/defects',     label: 'Defect Analytics' },
  { name: '05-suppliers',       url: '/dashboard/suppliers',   label: 'Supplier Quality' },
  { name: '06-ai-performance',  url: '/dashboard/ai',          label: 'AI Performance' },
  { name: '07-demo-panel',      url: '/demo',                  label: 'Demo Panel' },
];

function slug(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

async function save(page, filepath) {
  await page.screenshot({ path: filepath, fullPage: false });
  console.log(`  ✓ ${path.basename(filepath)}`);
}

async function setOverlays(page, { bbox, heatmap, golden }) {
  const bboxBtn    = page.locator('button:has-text("Bounding Boxes")');
  const heatmapBtn = page.locator('button:has-text("XAI Heatmap")');
  const goldenBtn  = page.locator('button:has-text("Golden Diff")');

  // Helper: get current active state from button class
  const isActive = async (btn) => {
    const cls = await btn.getAttribute('class').catch(() => '');
    return cls.includes('bg-lam-navy') || cls.includes('bg-primary') || cls.includes('default');
  };

  // Bounding Boxes — default ON, so toggle if needed
  const bboxActive = await isActive(bboxBtn).catch(() => true);
  if (bbox !== undefined && bboxActive !== bbox) {
    await bboxBtn.click().catch(() => {});
    await page.waitForTimeout(300);
  }

  // Heatmap
  const heatmapActive = await isActive(heatmapBtn).catch(() => false);
  if (heatmap !== undefined && heatmapActive !== heatmap) {
    await heatmapBtn.click().catch(() => {});
    await page.waitForTimeout(400);
  }

  // Golden Diff
  const goldenActive = await isActive(goldenBtn).catch(() => false);
  if (golden !== undefined && goldenActive !== golden) {
    await goldenBtn.click().catch(() => {});
    await page.waitForTimeout(400);
  }

  await page.waitForTimeout(600); // let overlays render
}

async function resetOverlays(page) {
  // Turn off heatmap and golden, ensure bbox is on
  const heatmapBtn = page.locator('button:has-text("XAI Heatmap")');
  const goldenBtn  = page.locator('button:has-text("Golden Diff")');
  await heatmapBtn.click().catch(() => {});
  await page.waitForTimeout(200);
  await goldenBtn.click().catch(() => {});
  await page.waitForTimeout(200);
}

async function screenshotScenario(page, scenario, inspectionId, outDir) {
  const base = `${scenario.id}-${slug(scenario.name)}`;

  if (scenario.decision === 'PASS') {
    // PASS — show result screen with camera images
    await page.goto(`${BASE_URL}/kiosk/result/${inspectionId}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await save(page, path.join(outDir, `${base}.png`));
    return;
  }

  await page.goto(`${BASE_URL}/review/${inspectionId}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  // 1. Bounding Boxes only (default state)
  await setOverlays(page, { heatmap: false, golden: false });
  await save(page, path.join(outDir, `${base}-bbox.png`));

  // 2. XAI Heatmap only
  await setOverlays(page, { heatmap: true, golden: false });
  await save(page, path.join(outDir, `${base}-heatmap.png`));

  // 3. Golden Diff only
  await setOverlays(page, { heatmap: false, golden: true });
  await save(page, path.join(outDir, `${base}-golden.png`));

  // 4. All three combined
  await setOverlays(page, { heatmap: true, golden: true });
  await save(page, path.join(outDir, `${base}-all-overlays.png`));

  // Reset for next scenario
  await resetOverlays(page);
}

async function screenshotDashboards(page, outDir) {
  console.log('\n--- Dashboards ---');
  const dashDir = path.join(outDir, 'dashboards');
  fs.mkdirSync(dashDir, { recursive: true });

  for (const dash of DASHBOARDS) {
    console.log(`\n${dash.label}`);
    await page.goto(`${BASE_URL}${dash.url}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(3500); // let charts fully render
    await save(page, path.join(dashDir, `${dash.name}.png`));
  }
}

async function main() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  const scenariosDir  = path.join(OUTPUT_DIR, 'scenarios');
  fs.mkdirSync(scenariosDir, { recursive: true });

  console.log('AVIP Screenshot Automation');
  console.log('='.repeat(40));
  console.log(`Output: ${OUTPUT_DIR}\n`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Login
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' }).catch(() => {});
  await page.locator('button:has-text("Operator"), text=Operator').first().click().catch(() => {});
  await page.waitForTimeout(1000);

  // Reset demo
  console.log('Resetting demo data...');
  await fetch(`${API_URL}/api/v1/demo/reset`, { method: 'POST' });
  console.log('Done.\n');

  // ── Scenarios ──
  console.log('--- Scenarios ---');
  for (const scenario of SCENARIOS) {
    console.log(`\n[${scenario.id}] ${scenario.name} (${scenario.decision})`);

    // Run scenario via API
    const res = await fetch(`${API_URL}/api/v1/demo/scenarios/${scenario.id}/run`, { method: 'POST' });
    const data = await res.json();
    const inspectionId = data.inspection_id;
    console.log(`  Inspection: ${inspectionId}`);

    await screenshotScenario(page, scenario, inspectionId, scenariosDir);
    await page.waitForTimeout(300);
  }

  // ── Dashboards + static screens ──
  await screenshotDashboards(page, OUTPUT_DIR);

  // ── Capture screen — navigate to an existing inspection's capture ──
  console.log('\n--- Extra Screens ---');
  const extraDir = path.join(OUTPUT_DIR, 'dashboards');

  // Capture screen: run a fresh scenario-01 and catch mid-capture
  console.log('\nCapture Screen (mid-inspection)');
  const scanRes = await fetch(`${API_URL}/api/v1/demo/scenarios/scenario-01/run`, { method: 'POST' });
  const scanData = await scanRes.json();
  await page.goto(`${BASE_URL}/kiosk/capture/${scanData.inspection_id}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await save(page, path.join(extraDir, '08-capture-screen.png'));

  // PASS result screen
  console.log('\nPASS Result Screen');
  await page.goto(`${BASE_URL}/kiosk/result/${scanData.inspection_id}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await save(page, path.join(extraDir, '09-result-pass.png'));

  // FAIL result screen — run scenario-02
  console.log('\nFAIL Result Screen');
  const failRes = await fetch(`${API_URL}/api/v1/demo/scenarios/scenario-02/run`, { method: 'POST' });
  const failData = await failRes.json();
  await page.goto(`${BASE_URL}/kiosk/result/${failData.inspection_id}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await save(page, path.join(extraDir, '10-result-fail.png'));

  // REVIEW result screen — run scenario-06
  console.log('\nREVIEW Result Screen');
  const revRes = await fetch(`${API_URL}/api/v1/demo/scenarios/scenario-06/run`, { method: 'POST' });
  const revData = await revRes.json();
  await page.goto(`${BASE_URL}/kiosk/result/${revData.inspection_id}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await save(page, path.join(extraDir, '11-result-review.png'));

  // OCR Modal — label selection state
  console.log('\nOCR Label Capture (selection)');
  await page.goto(`${BASE_URL}/kiosk`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  await page.locator('button:has-text("OCR Capture")').click().catch(() => {});
  await page.waitForTimeout(1500);
  await save(page, path.join(extraDir, '13-ocr-label-selection.png'));

  // OCR Modal — after selecting a label (click first label)
  console.log('\nOCR Label Capture (label selected)');
  await page.locator('.grid button').first().click().catch(() => {});
  await page.waitForTimeout(800);
  await save(page, path.join(extraDir, '14-ocr-label-selected.png'));

  // OCR Modal — capture and extract result
  console.log('\nOCR Label Capture (result)');
  await page.locator('button:has-text("Capture & Extract")').click().catch(() => {});
  await page.waitForTimeout(3000); // scanning animation + result
  await save(page, path.join(extraDir, '15-ocr-result.png'));
  await page.goto(`${BASE_URL}/review/${failData.inspection_id}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);
  // Enable all overlays for richest view
  await page.locator('button:has-text("XAI Heatmap")').click().catch(() => {});
  await page.waitForTimeout(500);
  await page.locator('button:has-text("Golden Diff")').click().catch(() => {});
  await page.waitForTimeout(800);
  await save(page, path.join(extraDir, '12-review-workbench.png'));

  await browser.close();

  // Summary
  const allFiles = [];
  const walk = (dir) => {
    fs.readdirSync(dir).forEach(f => {
      const full = path.join(dir, f);
      if (fs.statSync(full).isDirectory()) walk(full);
      else if (f.endsWith('.png')) allFiles.push(full.replace(OUTPUT_DIR + '/', ''));
    });
  };
  walk(OUTPUT_DIR);

  console.log('\n' + '='.repeat(40));
  console.log(`\n✓ ${allFiles.length} screenshots saved to ${OUTPUT_DIR}\n`);
  allFiles.forEach(f => console.log(`  ${f}`));
}

main().catch(err => { console.error(err); process.exit(1); });
