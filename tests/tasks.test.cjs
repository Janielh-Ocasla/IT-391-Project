const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../Frontend/cic-site/static/js/Task.js'), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));

async function openTasks(canPick) {
  const calls = [];
  const elements = Object.fromEntries(
    ['task-status', 'task-list', 'task-empty', 'events-list', 'events-empty', 'task-search']
      .map(id => [id, {
        dataset: {}, classList: { toggle() {} },
        addEventListener(name, handler) { this[name] = handler; },
      }]),
  );
  elements['task-list'].dataset.canPick = String(canPick);
  vm.runInNewContext(source, {
    document: { readyState: 'complete', getElementById: id => elements[id] },
    window: { CICApi: { async request(url, options) {
      calls.push({ url, method: options?.method ?? 'GET' });
      if (url === '/api/tasks') return {
        ok: true, tasks: [{ id: 'delivery-1', title: '<img src=x onerror=alert(1)>', location: 'Pantry' }],
      };
      if (url === '/api/announcements') return { ok: true, announcements: [{ title: 'Food drive' }] };
      return { ok: true };
    } } },
  });
  await settle();
  return { calls, taskList: elements['task-list'], events: elements['events-list'] };
}

test('the task page loads its lists and lets a volunteer pick a task', async () => {
  const { calls, taskList, events } = await openTasks(true);
  assert.deepEqual(calls, [{ url: '/api/tasks', method: 'GET' }, { url: '/api/announcements', method: 'GET' }]);
  assert.match(taskList.innerHTML, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(taskList.innerHTML, /<img /);
  assert.match(taskList.innerHTML, /Pick up task/);
  assert.match(events.innerHTML, /Food drive/);
  const button = { dataset: { taskId: 'delivery-1' } };
  taskList.click({ target: { closest: () => button } });
  await settle();
  assert.deepEqual(calls.at(-1), { url: '/api/tasks/delivery-1/pick', method: 'POST' });
  assert.equal(button.disabled, true);
});

test('the admin task list is viewable without volunteer pickup controls', async () => {
  const { calls, taskList } = await openTasks(false);
  assert.match(taskList.innerHTML, /Pantry/);
  assert.doesNotMatch(taskList.innerHTML, /Pick up task/);
  taskList.click({ target: { closest: () => ({ dataset: { taskId: 'delivery-1' } }) } });
  assert.ok(calls.every(call => call.method === 'GET'));
});
