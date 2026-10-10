/* The browser code runner: HTML, CSS and JavaScript run in the learner's own
 * browser, inside a sandboxed frame (allow-scripts only, so the code has no
 * access to this page, its cookies or the learner's account).
 *
 *   WebRunner.run({files, tests, api})       -> Promise<{logs, error, tests}>
 *       Runs once in a hidden frame and, when `tests` is given, runs them.
 *   WebRunner.preview(frame, {files, api}, onLog)
 *       Shows the page in a visible frame and streams its console to onLog.
 *   WebRunner.runJs(code)                    -> Promise<{output, error}>
 *       Plain JavaScript, console.log collected (flashcards).
 *
 * `files` maps 'index.html', 'style.css' and 'script.js' to their text.
 * `tests` is JavaScript calling test('id', async () => { ... }) with expect(),
 * waitFor(), $ and $$ (see HARNESS). `api` is a fake API for fetch():
 * {'/api/users': {status: 200, body: [...]}}. Nothing reaches the network.
 */
window.WebRunner = (() => {
  const TIMEOUT_MS = 5000;
  const TEST_TIMEOUT_MS = 2000;

  // Runs first inside the frame: console capture, error capture, fake fetch and the test helpers.
  const HARNESS = String.raw`
(() => {
  const token = __TOKEN__;
  const send = (type, data) => parent.postMessage(Object.assign({ token, type }, data), '*');
  const show = (v) => {
    if (typeof v === 'string') return v;
    if (v instanceof Error) return v.name + ': ' + v.message;
    try { return JSON.stringify(v); } catch (e) { return String(v); }
  };
  const logs = [];
  ['log', 'info', 'warn', 'error'].forEach((level) => {
    console[level] = (...args) => { const line = args.map(show).join(' '); logs.push(line); send('log', { level, line }); };
  });
  let loadError = null;
  window.addEventListener('error', (e) => {
    const line = e.error ? e.error.name + ': ' + e.error.message : String(e.message);
    loadError = loadError || line;
    send('log', { level: 'error', line });
  });
  window.addEventListener('unhandledrejection', (e) => send('log', { level: 'error', line: 'Uncaught (in promise) ' + show(e.reason) }));

  // fetch() answers from the exercise's fake API after a short delay, like a real server.
  const api = __API__;
  const calls = [];
  const respond = (status, body) => ({
    ok: status >= 200 && status < 300, status,
    json: async () => JSON.parse(JSON.stringify(body)),
    text: async () => typeof body === 'string' ? body : JSON.stringify(body),
  });
  window.fetch = (url, options = {}) => new Promise((resolve) => {
    const path = new URL(String(url), 'https://api.example.com').pathname;
    calls.push({ url: String(url), path, method: (options.method || 'GET').toUpperCase() });
    setTimeout(() => {
      const route = api[path];
      resolve(route ? respond(route.status || 200, route.body) : respond(404, { error: 'Not found' }));
    }, 120);
  });

  class Failure extends Error {}
  const name = (v) => show(v);
  const expect = (actual) => {
    const check = (ok, message) => { if (!ok) throw new Failure(message); };
    return {
      toBe: (want) => check(Object.is(actual, want), 'Expected ' + name(want) + ' but got ' + name(actual)),
      toEqual: (want) => check(JSON.stringify(actual) === JSON.stringify(want), 'Expected ' + name(want) + ' but got ' + name(actual)),
      toContain: (part) => check(actual != null && actual.includes(part), 'Expected ' + name(actual) + ' to contain ' + name(part)),
      toBeTruthy: () => check(Boolean(actual), 'Expected a value but got ' + name(actual)),
      toBeAtLeast: (n) => check(actual >= n, 'Expected at least ' + n + ' but got ' + name(actual)),
    };
  };
  const waitFor = async (fn, ms = 1500) => {
    const end = Date.now() + ms;
    for (;;) {
      try { const v = await fn(); if (v) return v; } catch (e) { if (Date.now() > end) throw e; }
      if (Date.now() > end) return null;
      await new Promise((r) => setTimeout(r, 30));
    }
  };
  const tests = [];
  Object.assign(window, {
    test: (id, fn) => tests.push({ id, fn }),
    expect, waitFor,
    $: (sel) => document.querySelector(sel),
    $$: (sel) => Array.from(document.querySelectorAll(sel)),
    css: (el, prop) => el ? getComputedStyle(el).getPropertyValue(prop).trim() : '',
    __learn: {
      api, calls,
      async start() {
        if (document.readyState !== 'complete') await new Promise((r) => window.addEventListener('load', r));
        await new Promise((r) => setTimeout(r, 0));
        const results = [];
        for (const t of tests) {
          try {
            await Promise.race([t.fn(), new Promise((_, no) => setTimeout(() => no(new Failure('This test took longer than __TEST_MS__ ms.')), __TEST_MS__))]);
            results.push({ id: t.id, outcome: 'passed' });
          } catch (e) {
            results.push(e instanceof Failure ? { id: t.id, outcome: 'failed', message: e.message } : { id: t.id, outcome: 'error', message: show(e) });
          }
          send('progress', {});
        }
        send('done', { logs, error: loadError, tests: results });
      },
    },
  });
})();
`;

  // Learner text can't close our <script> tags early.
  const safe = (code) => String(code || '').replace(/<\/(script)/gi, '<\\/$1');

  function build({ files = {}, tests = '', api = {}, token }) {
    let html = files['index.html'];
    if (html == null || !html.trim()) html = '<!doctype html><html><head></head><body></body></html>';
    // The page links style.css and script.js; they are put inline instead.
    html = html.replace(/<link\b[^>]*href=["']?\.?\/?style\.css["']?[^>]*>/gi, '')
      .replace(/<script\b[^>]*src=["']?\.?\/?script\.js["']?[^>]*>\s*<\/script>/gi, '');
    // Function replacements, so a "$" in the inserted text is never read as a pattern.
    const harness = HARNESS.replace('__TOKEN__', () => JSON.stringify(token))
      .replace('__API__', () => JSON.stringify(api || {}))
      .replace(/__TEST_MS__/g, () => String(TEST_TIMEOUT_MS));
    const head = `<script>${safe(harness)}<\/script>` + (files['style.css'] ? `<style>${files['style.css'].replace(/<\/(style)/gi, '<\\/$1')}</style>` : '');
    const tail = (files['script.js'] ? `<script>${safe(files['script.js'])}\n<\/script>` : '')
      + (tests ? `<script>${safe(tests)}\n<\/script>` : '') + '<script>__learn.start();<\/script>';
    const headTag = html.match(/<head\b[^>]*>/i);
    html = headTag ? html.replace(headTag[0], () => headTag[0] + head) : head + html;
    const bodyEnd = html.toLowerCase().lastIndexOf('</body>');
    return bodyEnd === -1 ? html + tail : html.slice(0, bodyEnd) + tail + html.slice(bodyEnd);
  }

  // One listener for every frame; each run or preview registers its token.
  const handlers = new Map();
  window.addEventListener('message', (event) => {
    const handler = event.data && handlers.get(event.data.token);
    if (handler && event.source === handler.frame.contentWindow) handler.fn(event.data);
  });
  const newToken = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

  function run({ files, tests = '', api = {} }) {
    return new Promise((resolve) => {
      const frame = document.createElement('iframe');
      frame.setAttribute('sandbox', 'allow-scripts');
      frame.setAttribute('aria-hidden', 'true');
      frame.tabIndex = -1;
      // Off screen but laid out at a laptop width, so CSS tests see real sizes.
      frame.style.cssText = 'position:fixed;left:-10000px;top:0;width:1024px;height:768px;border:0;visibility:hidden';
      const token = newToken();
      const logs = [];
      const finish = (data) => {
        clearTimeout(timer);
        handlers.delete(token);
        frame.remove();
        resolve({ logs: data.logs || logs, error: data.error || null, tests: data.tests || [], timedOut: Boolean(data.timedOut) });
      };
      // The clock restarts whenever the frame reports, so only a frame that stops answering
      // (an infinite loop) runs out of time, however many tests there are.
      let timer = null;
      const wait = () => { clearTimeout(timer); timer = setTimeout(() => finish({ timedOut: true, error: `Your code took longer than ${TIMEOUT_MS / 1000} seconds. Is there an infinite loop?` }), TIMEOUT_MS); };
      wait();
      handlers.set(token, { frame, fn: (data) => {
        if (data.type === 'done') return finish(data);
        wait();
        if (data.type === 'log') logs.push(data.line);
      } });
      frame.srcdoc = build({ files, tests, api, token });
      document.body.appendChild(frame);
    });
  }

  function preview(frame, { files, api = {} }, onLog) {
    for (const [token, handler] of handlers) if (handler.frame === frame) handlers.delete(token);
    const token = newToken();
    handlers.set(token, { frame, fn: (data) => { if (data.type === 'log' && onLog) onLog(data); } });
    frame.setAttribute('sandbox', 'allow-scripts allow-modals');
    frame.srcdoc = build({ files, api, token });
  }

  async function runJs(code) {
    const result = await run({ files: { 'script.js': code } });
    return { output: result.logs.length ? result.logs.join('\n') + '\n' : '', error: result.error };
  }

  return { run, preview, runJs, build };
})();
