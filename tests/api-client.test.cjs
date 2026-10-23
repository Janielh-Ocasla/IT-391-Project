const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../Frontend/cic-site/static/js/api.js'), 'utf8');

function browser(replies, storage = new Map()) {
  const calls = [];
  const events = [];
  const window = { dispatchEvent: event => events.push(event.type) };
  vm.runInNewContext(source, {
    window, FormData,
    CustomEvent: class { constructor(type) { this.type = type; } },
    sessionStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
    fetch: async (url, options) => {
      calls.push({ url, ...options });
      const reply = replies.shift();
      if (reply instanceof Error) throw reply;
      return { status: reply.status, ok: reply.status < 400, json: async () => reply.data };
    },
  });
  return { api: window.CICApi, calls, events, storage };
}

test('login token survives navigation and is sent on later API calls', async () => {
  const first = browser([{ status: 200, data: { ok: true, role: 'volunteer', access_token: 'jwt' } }]);
  assert.equal((await first.api.login({ email: 'v@example.com', password: 'password' })).ok, true);
  const next = browser([{ status: 200, data: { ok: true, logged_in: true } }], first.storage);
  assert.equal((await next.api.request('/api/me')).logged_in, true);
  assert.equal(next.calls[0].headers.Authorization, 'Bearer jwt');
  assert.equal(next.calls[0].credentials, 'omit');
});

test('login without a token and failed HTTP responses cannot report success', async () => {
  const { api, storage } = browser([
    { status: 200, data: { ok: true } },
    { status: 500, data: { ok: true, error: 'Server failed', status: 200 } },
    { status: 503, data: { ok: false, error: 'Registration paused' } },
  ]);
  assert.equal((await api.login({})).ok, false);
  assert.equal(storage.size, 0);
  const failed = await api.request('/api/tasks');
  assert.equal(failed.ok, false);
  assert.equal(failed.status, 500);
  assert.equal((await api.request('/api/register', { method: 'POST', body: {} })).error, 'Registration paused');
});

test('expired token is cleared and the page is notified', async () => {
  const storage = new Map([['cic.access_token', 'expired']]);
  const { api, events } = browser([{ status: 401, data: { ok: false, error: 'Expired' } }], storage);
  assert.equal((await api.request('/api/tasks')).ok, false);
  assert.equal(storage.size, 0);
  assert.deepEqual(events, ['cic:session-expired']);
});

test('logout clears local token even when the server is unreachable', async () => {
  const storage = new Map([['cic.access_token', 'jwt']]);
  const { api, calls } = browser([new Error('offline')], storage);
  assert.equal((await api.logout()).ok, false);
  assert.equal(storage.size, 0);
  assert.equal(calls[0].url, '/api/logout');
  assert.equal(calls[0].method, 'POST');
});

test('uploads preserve FormData so the browser can set the multipart boundary', async () => {
  const { api, calls } = browser([{ status: 200, data: { ok: true, photo_path: 'photo.png' } }]);
  const body = new FormData();
  body.append('photo', new Blob(['image']), 'photo.png');
  await api.request('/api/tasks/id/photo', { method: 'POST', body });
  assert.equal(calls[0].body, body);
  assert.equal(calls[0].headers['Content-Type'], undefined);
});

test('network failures and invalid response bodies produce actionable errors', async () => {
  const { api } = browser([
    new Error('offline'), { status: 200, data: null }, { status: 200, data: [] },
  ]);
  const offline = await api.request('/api/me');
  assert.equal(offline.ok, false);
  assert.equal(offline.status, 0);
  assert.equal((await api.request('/api/me')).ok, false);
  assert.equal((await api.request('/api/tasks')).ok, false);
});

test('tokens cannot be sent to external URLs', async () => {
  const { api, calls } = browser([]);
  await assert.rejects(api.request('https://example.com/api/tasks'));
  assert.equal(calls.length, 0);
});
