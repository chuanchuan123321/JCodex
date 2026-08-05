#!/usr/bin/env node
// Ensure a usable Chromium browser without downloading when the system
// already has Chrome/Chromium installed. Used by `npm run setup`.

const path = require('path');
const { execSync } = require('child_process');

const browserDetect = require(path.join(__dirname, '..', 'lib', 'browser-detect'));

const systemChrome = browserDetect.findSystemChrome();
if (systemChrome) {
  console.log('✅ Found system browser:', systemChrome);
  console.log('No download needed — Playwright will use it automatically.');
  process.exit(0);
}

if (browserDetect.playwrightChromiumInstalled()) {
  console.log('✅ Playwright Chromium is already installed.');
  process.exit(0);
}

console.log('⚠️  No system Chrome/Chromium found.');
console.log('📥 Downloading Playwright Chromium (one-time download)...');
try {
  execSync('npx playwright install chromium', { stdio: 'inherit', cwd: path.join(__dirname, '..') });
  console.log('✅ Chromium installed.');
} catch (error) {
  console.error('❌ Failed to download Chromium:', error.message);
  console.error('Install Google Chrome/Chromium, then re-run: npm run setup');
  process.exit(1);
}
