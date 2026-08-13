// JCodex desktop frontend behavioral smoke test (jsdom, no browser needed).
//
// Loads the real index.html + app.js with a stubbed eel bridge and asserts:
//  1. the app boots without uncaught exceptions and drives the startup eel
//     calls (initialize -> load_settings -> list_*);
//  2. message rendering escapes model/AI content (XSS guard);
//  3. core UI wiring exists (send button + composer listeners).
//
// Run: node tests/frontend/smoke.mjs

import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {JSDOM, VirtualConsole} from 'jsdom';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DESKTOP = path.resolve(__dirname, '../../agent/ui/desktop');
const indexHtml = fs.readFileSync(path.join(DESKTOP, 'index.html'), 'utf8');
const appJs = fs.readFileSync(path.join(DESKTOP, 'app.js'), 'utf8');

let failures = 0;
function check(condition, message) {
    if (condition) {
        console.log(`  ok - ${message}`);
    } else {
        failures += 1;
        console.error(`  FAIL - ${message}`);
    }
}

// ---- virtual console + uncaught capture ----
const runtimeErrors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on('jsdomError', (e) => runtimeErrors.push(`jsdomError: ${e}`));
virtualConsole.on('error', (...args) => runtimeErrors.push(`console.error: ${args.join(' ')}`));

// ---- browser API stubs missing from jsdom ----
function installBrowserStubs(window) {
    window.matchMedia = window.matchMedia || (() => ({
        matches: false,
        media: '',
        onchange: null,
        addListener() {},
        removeListener() {},
        addEventListener() {},
        removeEventListener() {},
        dispatchEvent() { return false; },
    }));
    window.ResizeObserver = window.ResizeObserver || class {
        observe() {}
        unobserve() {}
        disconnect() {}
    };
    if (!window.navigator.clipboard) {
        Object.defineProperty(window.navigator, 'clipboard', {
            value: {writeText: async () => {}, readText: async () => ''},
            configurable: true,
        });
    }
    if (!window.Element.prototype.scrollIntoView) {
        window.Element.prototype.scrollIntoView = () => {};
    }
}

// ---- eel stub: eel.fn(args)() -> Promise ----
const defaultResponses = {
    initialize: () => [true, 'ok'],
    load_settings: () => ({}),
    list_projects: () => ({success: true, projects: []}),
    list_conversations: () => ({success: true, conversations: [], active_id: null}),
    get_split_conversation_state: () => ({success: false}),
    list_workspace_files: () => [],
    list_skills: () => [],
    list_skill_store: () => ({success: true, skills: []}),
    get_token_count: () => ({tokens: 0, compress_at: 256000}),
    get_embedding_status: () => ({provider: 'disabled', available: false}),
    get_execution_status: () => ({running: false, finalized: true}),
    get_preview_sessions: () => ({sessions: []}),
    load_conversation: () => ({success: true, conversation: null}),
    set_active_conversation: () => ({success: true, conversation: null}),
    set_auto_allow_all: () => ({success: true}),
    get_auto_allow_all: () => ({success: true, enabled: false}),
    list_api_configs: () => ({success: true, available: [], configs: {}, active: null}),
    list_scheduled_tasks: () => ({success: true, tasks: []}),
    list_archived_conversations: () => ({success: true, conversations: []}),
    get_recent_tasks: () => [],
};
const calls = [];
const uncaught = [];
const eelStub = {_websocket: null};
for (const [name, responder] of Object.entries(defaultResponses)) {
    eelStub[name] = (...args) => {
        calls.push({name, args});
        return () => Promise.resolve(responder());
    };
}

const dom = new JSDOM(indexHtml, {
    url: 'http://127.0.0.1:8000/',
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    virtualConsole,
    beforeParse(window) {
        installBrowserStubs(window);
        window.eel = eelStub;
        window.addEventListener('error', (e) => uncaught.push(`error: ${e.message}`));
        window.addEventListener('unhandledrejection', (e) => uncaught.push(`rejection: ${String(e.reason)}`));
    },
});
const {window} = dom;

// ---- load the real app scripts as real classic <script> elements ----
// Appending script elements (runScripts: 'dangerously') preserves the shared
// global lexical scope across files, exactly like separate <script> tags in
// index.html — window.eval() would keep top-level let/const private per file.
const scriptSrcs = [...indexHtml.matchAll(/<script src="([^"]+)">/g)]
    .map((m) => m[1])
    .filter((s) => !s.startsWith('/') && !s.startsWith('vendor/'));
if (!scriptSrcs.some((s) => s.split('?')[0] === 'app.js')) {
    throw new Error('app.js not referenced by index.html');
}
const loadedScriptSources = [];
for (const scriptSrc of scriptSrcs) {
    const source = fs.readFileSync(path.join(DESKTOP, scriptSrc.split('?')[0]), 'utf8');
    loadedScriptSources.push(source);
    const scriptEl = window.document.createElement('script');
    scriptEl.textContent = source;
    window.document.body.appendChild(scriptEl);
}
window.document.dispatchEvent(new window.Event('DOMContentLoaded', {bubbles: true}));
await new Promise((resolve) => setTimeout(resolve, 900));

console.log('1) startup');
check(calls.some((c) => c.name === 'initialize'), 'init drives eel.initialize');
check(calls.some((c) => c.name === 'load_settings'), 'init drives eel.load_settings');
check(calls.some((c) => c.name === 'list_conversations'), 'init drives eel.list_conversations');
check(calls.some((c) => c.name === 'list_projects'), 'init drives eel.list_projects');
check(uncaught.length === 0, `no uncaught exceptions (${uncaught.length})`);
if (runtimeErrors.length) console.error('runtimeErrors:', runtimeErrors.slice(0, 8));
check(
    runtimeErrors.filter((r) => !r.includes('Could not parse CSS')).length === 0,
    'no uncaught runtime errors',
);

console.log('2) message rendering + escaping');
window.renderConversationEvents([
    {type: 'user', content: 'hello <world>', attachments: [], message_id: 1},
    {type: 'assistant', content: '<script>alert(1)</script><img src=x onerror=alert(2)>', message_id: 1},
]);
const chatMessages = window.document.getElementById('chatMessages');
const chatText = chatMessages.textContent || '';
check(chatText.includes('hello <world>'), 'user message rendered');
check(!chatMessages.querySelector('script'), 'assistant content has no live <script> element');
check(!chatMessages.querySelector('img[onerror]'), 'assistant content has no onerror attribute');
check(chatText.includes('alert(1)') && chatText.includes('onerror'), 'raw payload text still visible (escaped)');
check(window.escapeHtml('<b>&"') === '&lt;b&gt;&amp;&quot;', 'escapeHtml escapes angle brackets & quotes');

console.log('3) core UI wiring');
check(typeof window.sendMessage === 'function' || typeof window.handleSend === 'function', 'send path function exists');
const input = window.document.getElementById('messageInput');
check(input !== null, 'messageInput exists');
check(typeof window.initializeUI === 'function', 'initializeUI defined');
console.log('4) split modules');
check(typeof window.refreshArchivedConversations === 'function', 'js/data.js loaded (refreshArchivedConversations)');
check(typeof window.refreshPreferences === 'function', 'js/preferences.js loaded (refreshPreferences)');
check(typeof window.refreshKnowledgeBase === 'function', 'js/knowledge.js loaded (refreshKnowledgeBase)');
check(typeof window.refreshWorkspace === 'function', 'js/workspace.js loaded (refreshWorkspace)');
check(typeof window.openSettings === 'function', 'js/settings.js loaded (openSettings)');
check(typeof window.refreshSkills === 'function', 'js/skills.js loaded (refreshSkills)');
check(typeof window.refreshMemory === 'function', 'js/memory.js loaded (refreshMemory)');
check(typeof window.openChangeReview === 'function', 'js/review.js loaded (openChangeReview)');
check(typeof window.openSplitTask === 'function', 'js/split-pane.js loaded (openSplitTask)');
    check(typeof window.setSidebarPanel === 'function', 'js/layout.js loaded (setSidebarPanel)');
    check(typeof window.renderAgentDetail === 'function', 'js/agent-detail.js loaded (renderAgentDetail)');
check(typeof window.showInputDialog === 'function', 'js/dialogs.js loaded (showInputDialog)');
check(typeof window.showQuickCommands === 'function', 'js/quick-commands.js loaded (showQuickCommands)');

console.log('5) static wiring (no inline handlers)');
const modalActive = (id) => window.document.getElementById(id).classList.contains('active');
const click = (id) => window.document.getElementById(id).click();
const tick = () => new Promise((resolve) => setTimeout(resolve, 30));

await tick();
click('settingsBtn');
await tick();
check(modalActive('settingsModal'), 'settingsBtn opens settingsModal (wired in initializeUI)');
click('closeSettingsButton');
check(!modalActive('settingsModal'), 'closeSettingsButton closes settingsModal');
await tick();

click('dataBtn');
await tick();
check(modalActive('dataModal'), 'dataBtn opens dataModal');
click('closeDataButton');
check(!modalActive('dataModal'), 'closeDataButton closes dataModal');
await tick();

click('archiveBtn');
await tick();
check(modalActive('archiveModal'), 'archiveBtn opens archiveModal');
click('archiveCloseButton');
check(!modalActive('archiveModal'), 'archiveCloseButton closes archiveModal');
await tick();

click('scheduledBtn');
await tick();
check(modalActive('scheduledTasksModal'), 'scheduledBtn opens scheduledTasksModal');
click('scheduledTasksCloseButton');
check(!modalActive('scheduledTasksModal'), 'scheduledTasksCloseButton closes scheduledTasksModal');
await tick();

click('skillStoreEntry');
await tick();
check(modalActive('skillStoreModal'), 'skillStoreEntry opens skillStoreModal');
click('closeSkillStoreButton');
check(!modalActive('skillStoreModal'), 'closeSkillStoreButton closes skillStoreModal');
await tick();

const beforeFiles = calls.filter((c) => c.name === 'list_workspace_files').length;
click('workspaceRefreshAll');
await tick();
check(
  calls.filter((c) => c.name === 'list_workspace_files').length > beforeFiles,
  'workspaceRefreshAll drives eel.list_workspace_files',
);
await tick();

console.log('6) no inline event handlers');
const inlineHandlerPattern =
    /\bon(?:click|change|input|keydown|keyup|mouseover|mouseout|focus|blur|submit|load|error)=/g;
const htmlInlineHandlers = indexHtml.match(inlineHandlerPattern) || [];
check(htmlInlineHandlers.length === 0, 'index.html has no inline event handlers');
const jsInlineHandlers = loadedScriptSources.flatMap(
    (source) => source.match(inlineHandlerPattern) || [],
);
check(jsInlineHandlers.length === 0, 'app.js + js/*.js have no inline event handlers');

// ---- cleanup ----
dom.window.close();

if (failures > 0) {
    console.error(`\n${failures} check(s) failed`);
    process.exit(1);
}
console.log('\nfrontend smoke OK');
