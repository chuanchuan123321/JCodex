// Fingerprint cache-busting params (?v=) in agent/ui/desktop/index.html.
//
// Every local asset (styles.css, app.js, js/*.js) gets a content-derived
// SHA-256 prefix, so browsers reload exactly the files that changed and keep
// the rest cached. Run after editing frontend files before packaging:
//
//   npm run version:frontend          # rewrite ?v= in place
//   npm run version:frontend:check    # fail if any ?v= is stale (CI)
//
// Third-party / eel assets (vendor/*, /eel.js) are intentionally left alone.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DESKTOP = path.resolve(__dirname, '..', 'agent', 'ui', 'desktop');
const INDEX_HTML = path.join(DESKTOP, 'index.html');
const checkOnly = process.argv.includes('--check');

const indexHtml = fs.readFileSync(INDEX_HTML, 'utf8');
const entries = [];
for (const match of indexHtml.matchAll(/(href|src)="([^"]+)\?v=([^"]+)"/g)) {
    const [, attr, assetPath, oldVersion] = match;
    if (assetPath.startsWith('vendor/') || assetPath.startsWith('/')) continue;
    const filePath = path.join(DESKTOP, assetPath);
    if (!fs.existsSync(filePath)) {
        console.error(`fingerprint: missing asset referenced by index.html: ${assetPath}`);
        process.exit(1);
    }
    const hash = crypto
        .createHash('sha256')
        .update(fs.readFileSync(filePath))
        .digest('hex')
        .slice(0, 10);
    entries.push({attr, assetPath, oldVersion, hash, changed: hash !== oldVersion});
}

const stale = entries.filter((entry) => entry.changed);
if (checkOnly) {
    if (stale.length) {
        for (const entry of stale) {
            console.error(
                `fingerprint: stale cache version for ${entry.assetPath} ` +
                    `(${entry.oldVersion} -> ${entry.hash})`,
            );
        }
        console.error('Run `npm run version:frontend` to refresh index.html.');
        process.exit(1);
    }
    console.log(`fingerprint: ${entries.length} asset(s) up to date`);
    process.exit(0);
}

let updated = indexHtml;
for (const entry of stale) {
    const before = `${entry.attr}="${entry.assetPath}?v=${entry.oldVersion}"`;
    const after = `${entry.attr}="${entry.assetPath}?v=${entry.hash}"`;
    updated = updated.replace(before, after);
}
fs.writeFileSync(INDEX_HTML, updated);
if (stale.length) {
    for (const entry of stale) {
        console.log(`fingerprint: ${entry.assetPath} ${entry.oldVersion} -> ${entry.hash}`);
    }
} else {
    console.log('fingerprint: no changes');
}
