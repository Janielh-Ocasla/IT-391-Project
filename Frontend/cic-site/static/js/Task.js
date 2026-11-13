/* Task dashboard: loads available tasks + community events and filters on search. */
(function () {
  const api = window.CICApi;
  const statusEl = document.getElementById('task-status');
  const taskList = document.getElementById('task-list');
  const taskEmpty = document.getElementById('task-empty');
  const eventsList = document.getElementById('events-list');
  const eventsEmpty = document.getElementById('events-empty');
  const searchEl = document.getElementById('task-search');
  const canPick = taskList.dataset.canPick === 'true';

  let allTasks = [];

  function esc(value) {
    const entities = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return String(value ?? '').replace(/[&<>"']/g, char => entities[char]);
  }

  function setStatus(message, isError) {
    statusEl.textContent = message || '';
    statusEl.classList.toggle('error', Boolean(isError));
  }

  function taskCard(task) {
    const id = esc(task.id ?? task.task_id ?? '');
    const title = esc(task.title || task.name || 'Untitled task');
    const location = esc(task.location || task.address || 'Location TBD');
    const desc = esc(task.description || task.details || '');
    return `
      <article class="task-card">
        <h3>${title}</h3>
        <p class="task-meta">📍 ${location}</p>
        ${desc ? `<p class="task-desc">${desc}</p>` : ''}
        ${canPick ? `<button class="btn-pick" data-task-id="${id}">Pick up task</button>` : ''}
      </article>`;
  }

  function eventCard(item) {
    const title = esc(item.title || 'Community update');
    const date = esc(item.created_at || item.date || '');
    const body = esc(item.content || item.body || '');
    return `
      <article class="task-card">
        <h3>${title}</h3>
        ${date ? `<p class="task-meta">${date}</p>` : ''}
        ${body ? `<p class="task-desc">${body}</p>` : ''}
      </article>`;
  }

  function renderTasks() {
    const query = (searchEl.value || '').trim().toLowerCase();
    const matches = allTasks.filter(function (t) {
      const hay = `${t.title || t.name || ''} ${t.location || t.address || ''}`.toLowerCase();
      return hay.includes(query);
    });
    taskList.innerHTML = matches.map(taskCard).join('');
    taskEmpty.hidden = matches.length > 0;
  }

  async function pickTask(taskId, button) {
    button.disabled = true;
    const result = await api.request(`/api/tasks/${encodeURIComponent(taskId)}/pick`, { method: 'POST', body: {} });
    if (result.ok) {
      button.textContent = 'Picked ✓';
    } else {
      button.disabled = false;
      setStatus(result.error || 'Could not pick up that task.', true);
    }
  }

  async function load() {
    setStatus('Loading tasks…');

    const tasksRes = await api.request('/api/tasks');
    if (tasksRes.ok && Array.isArray(tasksRes.tasks)) {
      allTasks = tasksRes.tasks;
      renderTasks();
      setStatus('');
    } else if (tasksRes.status === 401) {
      setStatus('Please log in to view available tasks.', true);
    } else {
      setStatus(tasksRes.error || 'Could not load tasks.', true);
    }

    const eventsRes = await api.request('/api/announcements');
    if (eventsRes.ok && Array.isArray(eventsRes.announcements)) {
      eventsList.innerHTML = eventsRes.announcements.map(eventCard).join('');
      eventsEmpty.hidden = eventsRes.announcements.length > 0;
    } else {
      eventsEmpty.hidden = false;
    }
  }

  searchEl.addEventListener('input', renderTasks);
  taskList.addEventListener('click', function (e) {
    const btn = e.target.closest('.btn-pick');
    if (canPick && btn && btn.dataset.taskId) pickTask(btn.dataset.taskId, btn);
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
