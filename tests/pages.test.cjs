const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const apiSource = fs.readFileSync(path.join(__dirname, '../Frontend/cic-site/static/js/api.js'), 'utf8');
const pageSource = fs.readFileSync(path.join(__dirname, '../Frontend/cic-site/static/js/pages.js'), 'utf8');

async function load({ status = 200, data, token = 'existing-jwt', page = 'history' }) {
  const calls = [];
  const renders = [];
  const navigations = [];
  const events = [];
  const message = { textContent: 'Loading your CIC page…' };
  const storage = new Map(token ? [['cic.access_token', token]] : []);
  const context = vm.createContext({
    FormData, encodeURIComponent,
    CustomEvent: class { constructor(type) { this.type = type; } },
    sessionStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
    fetch: async (url, options) => {
      calls.push({ url, ...options });
      return { status, ok: status < 400, json: async () => data };
    },
    window: {
      dispatchEvent: event => events.push(event.type),
      location: { replace: url => navigations.push(url) },
    },
    document: {
      body: { dataset: { cicPage: page } },
      getElementById: () => message,
      open: () => renders.push('open'),
      write: html => renders.push(html),
      close: () => renders.push('close'),
    },
  });
  vm.runInContext(apiSource, context);
  await vm.runInContext(pageSource, context);
  return { calls, renders, navigations, events, message, storage };
}

test('the loader uses the unchanged API client and renders only an authorized document', async () => {
  const html = '<!DOCTYPE html><html><body>Authorized history</body></html>';
  const result = await load({ data: { ok: true, html } });
  assert.equal(result.calls[0].url, '/api/pages/history');
  assert.equal(result.calls[0].headers.Authorization, 'Bearer existing-jwt');
  assert.equal(result.calls[0].credentials, 'omit');
  assert.deepEqual(result.renders, ['open', html, 'close']);
  assert.deepEqual(result.navigations, []);
});

test('a missing token cannot render protected content and opens the existing login form', async () => {
  const result = await load({ token: null, status: 401, data: { ok: false, error: 'Unauthorized' } });
  assert.equal(result.calls[0].headers.Authorization, undefined);
  assert.deepEqual(result.renders, []);
  assert.deepEqual(result.navigations, ['/?login=1']);
});

test('an expired token uses the existing API expiry behavior', async () => {
  const result = await load({ status: 401, data: { ok: false, error: 'Invalid or expired token' } });
  assert.equal(result.storage.size, 0);
  assert.deepEqual(result.events, ['cic:session-expired']);
  assert.deepEqual(result.renders, []);
  assert.deepEqual(result.navigations, ['/?login=1']);
});

test('volunteers denied an admin page never receive its rendered markup', async () => {
  const result = await load({ page: 'history-admin', status: 403, data: { ok: false, error: 'Admin access required' } });
  assert.deepEqual(result.renders, []);
  assert.match(result.message.textContent, /do not have access/);
  assert.equal(result.storage.get('cic.access_token'), 'existing-jwt');
});

test('server failures show an error without inventing empty history', async () => {
  const result = await load({ status: 500, data: { ok: false, error: 'Could not load page' } });
  assert.deepEqual(result.renders, []);
  assert.equal(result.message.textContent, 'Could not load page');
});

test('the admin landing response navigates to the completed admin history URL', async () => {
  const result = await load({ page: 'member', data: { ok: true, redirect: '/admin/history' } });
  assert.deepEqual(result.renders, []);
  assert.deepEqual(result.navigations, ['/admin/history']);
});

test('the member page redirect sends an admin to the admin dashboard', async () => {
  const result = await load({ page: 'member', data: { ok: true, redirect: '/admin' } });
  assert.deepEqual(result.renders, []);
  assert.deepEqual(result.navigations, ['/admin']);
});

test('invalid page responses are never rendered or followed as redirects', async () => {
  for (const fields of [{}, { html: [] }, { html: '' }, { redirect: 'https://example.com' }, { redirect: '/member' }]) {
    const result = await load({ data: { ok: true, ...fields } });
    assert.deepEqual(result.renders, []);
    assert.deepEqual(result.navigations, []);
    assert.match(result.message.textContent, /Could not load this page/);
  }
});
