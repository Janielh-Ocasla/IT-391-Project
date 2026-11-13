const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../Frontend/cic-site/static/js/site.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));

function browser({ role = 'volunteer', loginOk = true, loggedIn = false, search = '', logoutOk = true } = {}) {
  function element() {
    const classes = new Set();
    return {
      listeners: {}, style: {}, value: '', textContent: '',
      classList: { add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c) },
      addEventListener(type, listener) { this.listeners[type] = listener; },
      setAttribute() {}, focus() {}, reset() {},
      querySelector() { return { disabled: false }; },
    };
  }
  const ids = new Map([
    'loginOverlay', 'openLogin', 'closeLogin', 'loginForm', 'signupForm', 'forgotForm',
    'loginEmail', 'loginPassword', 'loginMsg', 'signupMsg', 'forgotMsg',
  ].map(id => [id, element()]));
  ids.get('loginEmail').value = 'volunteer@example.com';
  ids.get('loginPassword').value = 'password';
  const signout = element();
  const navigations = [];
  let logouts = 0;
  const window = {
    location: { search, assign: url => navigations.push(url), replace: url => navigations.push(url) },
    addEventListener() {},
    CICApi: {
      request: async () => ({ ok: true, logged_in: loggedIn, role }),
      login: async () => ({ ok: loginOk, role, error: loginOk ? undefined : 'Login failed' }),
      logout: async () => { logouts += 1; return { ok: logoutOk }; },
    },
  };
  vm.runInNewContext(source, {
    window, URLSearchParams,
    document: {
      body: { style: {}, insertAdjacentHTML() {} },
      getElementById: id => ids.get(id) || null,
      querySelector: () => null,
      querySelectorAll: selector => selector === '[data-signout]' ? [signout] : [],
      addEventListener() {},
    },
  });
  return {
    ids, signout, navigations, logouts: () => logouts,
    submit: () => ids.get('loginForm').listeners.submit({ preventDefault() {}, currentTarget: ids.get('loginForm') }),
  };
}

test('volunteer login navigates to the member URL', async () => {
  const page = browser();
  await tick();
  await page.submit();
  assert.deepEqual(page.navigations, ['/member']);
});

test('admin login navigates to the admin dashboard URL', async () => {
  const page = browser({ role: 'admin' });
  await tick();
  await page.submit();
  assert.deepEqual(page.navigations, ['/admin']);
});

test('failed login stays on the page and displays the existing API error', async () => {
  const page = browser({ loginOk: false });
  await tick();
  await page.submit();
  assert.deepEqual(page.navigations, []);
  assert.equal(page.ids.get('loginMsg').textContent, 'Login failed');
});

test('unsupported roles do not select a dashboard or change session handling', async () => {
  const page = browser({ role: 'constructor' });
  await tick();
  await page.submit();
  assert.deepEqual(page.navigations, []);
  assert.equal(page.logouts(), 0);
  assert.match(page.ids.get('loginMsg').textContent, /does not have access/);
});

test('template signout links call the existing logout client before going home', async () => {
  for (const logoutOk of [true, false]) {
    const page = browser({ loggedIn: true, logoutOk });
    await tick();
    await page.signout.listeners.click({ preventDefault() {} });
    assert.equal(page.logouts(), 1);
    assert.deepEqual(page.navigations, ['/']);
  }
});

test('the original header logout behavior remains unchanged', async () => {
  const page = browser({ loggedIn: true });
  await tick();
  await page.ids.get('openLogin').listeners.click();
  assert.equal(page.logouts(), 1);
  assert.deepEqual(page.navigations, []);
  assert.equal(page.ids.get('openLogin').textContent, 'Login/Signup');
});

test('an unauthorized page redirect opens the home login form', async () => {
  const page = browser({ search: '?login=1' });
  await tick();
  assert.equal(page.ids.get('loginOverlay').classList.contains('open'), true);
});
