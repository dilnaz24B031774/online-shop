/**
 * Saves all product photos inside the app, so the shop works without internet.
 *   1) start the backend (python3 manage.py runserver)
 *   2) npm run download-images
 * Photos go to public/products/, the list to public/products/manifest.json.
 */
import { mkdir, writeFile } from 'node:fs/promises';
import { extname } from 'node:path';

const API = process.env.API_URL || 'http://127.0.0.1:8000/api';
const OUT = new URL('../public/products/', import.meta.url);

const products = await (await fetch(`${API}/products/`)).json();
await mkdir(OUT, { recursive: true });

const manifest = {};
let ok = 0, failed = 0;
for (const p of products) {
  if (!p.image_url) continue;
  try {
    const res = await fetch(p.image_url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const ext = extname(new URL(p.image_url).pathname) || '.jpg';
    const file = `${p.sku}${ext}`;
    await writeFile(new URL(file, OUT), Buffer.from(await res.arrayBuffer()));
    manifest[p.sku] = file;
    ok++;
    process.stdout.write('.');
  } catch (e) {
    failed++;
    console.log(`\n${p.sku}: ${e.message}`);
  }
}
await writeFile(new URL('manifest.json', OUT), JSON.stringify(manifest, null, 2));
console.log(`\nSaved ${ok} photos${failed ? `, ${failed} failed` : ''}. Restart "npm start" if it is running.`);
