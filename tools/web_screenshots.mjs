// Screenshots of the browser version for the README: docs/images/browser.png (a laptop
// window) and docs/images/browser-phone.png. Same setup as web_smoke.mjs:
//
//   python3 tools/build_web.py && (python3 -m http.server 8123 -d dist/web &)
//   CHROME=/path/to/chromium node tools/web_screenshots.mjs [http://localhost:8123/] [more query]
//
// A second argument is added to the address as a query string, for example
// `pyodide=http://localhost:8124/` to load Pyodide from another server. Each shot runs the
// default program at Instant speed in a fresh browser profile, in light mode; the laptop
// one also points at the canvas, so the turtle coordinates show.
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const address = new URL(process.argv[2] || 'http://localhost:8123/');
for (const [key, value] of new URLSearchParams(process.argv[3] || '')) address.searchParams.set(key, value);
const images = fileURLToPath(new URL('../docs/images/', import.meta.url));

const browser = await chromium.launch({
  executablePath: process.env.CHROME,
  args: ['--no-sandbox', '--disable-gpu'],
});

async function capture(name, viewport, point) {
  const context = await browser.newContext({ viewport, colorScheme: 'light' });
  const page = await context.newPage();
  await page.goto(address.href);
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      await page.waitForFunction(() => document.getElementById('status').textContent.startsWith('Ready'), null, { timeout: 120000 });
      break;
    } catch (error) { // the first visit reloads once so the service worker can take over
      if (!/destroyed|navigat|closed/i.test(String(error))) throw error;
      await page.waitForLoadState();
    }
  }
  await page.selectOption('#speed', '0');
  await page.click('#run');
  await page.waitForFunction(() => !document.getElementById('run').disabled);
  if (point) {
    const box = await page.locator('#stage').boundingBox();
    await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.46);
  }
  await page.waitForTimeout(600);
  await page.screenshot({ path: images + name });
  console.log(`wrote docs/images/${name}`);
  await context.close();
}

await capture('browser.png', { width: 1280, height: 800 }, true);
await capture('browser-phone.png', { width: 390, height: 844 }, false);
await browser.close();
