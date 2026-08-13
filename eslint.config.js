// JCodex desktop frontend lint (legacy-friendly).
//
// Legacy files (app.js / styles.css / index.html) are intentionally out of
// scope until they are split. The rule set is enforced on the extracted
// js/*.js modules and any new frontend code.
//
// The extracted modules are classic scripts that share the page's global
// scope: they consume app.js's public helpers (showToast/escapeHtml/...) and
// expose their own entry functions back to app.js/index.html. Those cross-file
// contracts are modelled below as browser globals, so no-unused-vars is
// meaningless here and stays off until the modules own their state.
//
// Instead of hand-maintaining the list of shared bindings, the config derives
// them from app.js + sibling js/ modules at load time: every top-level
// function/let/const/var declared anywhere in the frontend is available to
// every extracted module. This stays correct as more sections are split out.

import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const jsDir = path.join(__dirname, 'agent', 'ui', 'desktop', 'js');

function topLevelBindings(filePath) {
  const source = fs.readFileSync(filePath, 'utf8');
  const bindings = {};
  for (const match of source.matchAll(/^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/gm)) {
    bindings[match[1]] = 'readonly';
  }
  for (const match of source.matchAll(/^(?:let|const|var)\s+([A-Za-z_$][\w$]*)/gm)) {
    bindings[match[1]] = 'readonly';
  }
  return bindings;
}

const sharedGlobals = {
  ...topLevelBindings(path.join(__dirname, 'agent', 'ui', 'desktop', 'app.js')),
};
for (const entry of fs.readdirSync(jsDir)) {
  if (entry.endsWith('.js')) {
    Object.assign(sharedGlobals, topLevelBindings(path.join(jsDir, entry)));
  }
}

const browserGlobals = {
  eel: 'readonly',
  katex: 'readonly',
  document: 'readonly',
  window: 'readonly',
  localStorage: 'readonly',
  sessionStorage: 'readonly',
  console: 'readonly',
  setTimeout: 'readonly',
  setInterval: 'readonly',
  clearTimeout: 'readonly',
  clearInterval: 'readonly',
  requestAnimationFrame: 'readonly',
  cancelAnimationFrame: 'readonly',
  URL: 'readonly',
  URLSearchParams: 'readonly',
  fetch: 'readonly',
  navigator: 'readonly',
  location: 'readonly',
  Blob: 'readonly',
  File: 'readonly',
  FormData: 'readonly',
  Event: 'readonly',
  CustomEvent: 'readonly',
};

export default [
  {
    files: ['agent/ui/desktop/js/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'script',
      globals: {...browserGlobals, ...sharedGlobals},
    },
    rules: {
      'no-undef': 'error',
      'no-unused-vars': 'off', // see header comment (shared global scope)
      'no-constant-condition': 'error',
      'no-dupe-keys': 'error',
      'no-unreachable': 'error',
    },
  },
];
