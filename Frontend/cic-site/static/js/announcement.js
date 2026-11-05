/* =====================================================
   Announcement page: loads announcements from the backend.
   Admins can also post, edit and delete
   ===================================================== */
(function () {
  // Small helper for calling the backend: it adds the login token (same key as api.js)
  // and returns {ok, status, data} or {ok: false, error}.
  const api = {
    async request(path, { method = 'GET', body } = {}) {
      const headers = { Accept: 'application/json' };
      const token = sessionStorage.getItem('cic.access_token');
      if (token) headers.Authorization = 'Bearer ' + token;
      if (body !== undefined) headers['Content-Type'] = 'application/json';

      try {
        const response = await fetch(path, {
          method,
          headers,
          body: body !== undefined ? JSON.stringify(body) : undefined,
        });
        const data = await response.json().catch(() => null);
        if (response.status === 401) {
          window.dispatchEvent(new Event('cic:session-expired'));
        }
        if (!response.ok) {
          return { ok: false, status: response.status, error: (data && data.error) || 'Request failed.' };
        }
        return { ok: true, status: response.status, data };
      } catch (err) {
        return { ok: false, status: 0, error: 'Could not reach the server.' };
      }
    },
  };

  // The role ("admin" or "volunteer") comes from GET /api/me.
  let currentRole = null;
  const isAdmin = () => currentRole === 'admin';

  async function loadRole() {
    currentRole = null;
    if (!sessionStorage.getItem('cic.access_token')) return;
    const res = await api.request('/api/me');
    if (res.ok && res.data && res.data.logged_in) currentRole = res.data.role;
  }

  const byId = (id) => document.getElementById(id);
  const el = {
    status: byId('ann-status'),
    form: byId('ann-form'),
    formTitle: byId('ann-form-title'),
    title: byId('ann-title'),
    content: byId('ann-content'),
    formMsg: byId('ann-form-msg'),
    submit: byId('ann-submit'),
    cancel: byId('ann-cancel'),
    featured: byId('ann-featured'),
    featuredCard: byId('ann-featured-card'),
    older: byId('ann-older'),
    list: byId('ann-list'),
    search: byId('ann-search'),
    empty: byId('ann-empty'),
    more: byId('ann-more'),
  };

  const PAGE_SIZE = 5;   // earlier announcements shown at a time
  const NEW_DAYS = 7;    // announcements newer than this get a "New" badge
  let visibleCount = PAGE_SIZE;
  let query = '';

  let items = [];        // announcements currently on the page, newest first
  let editingId = null;  // announcement_id being edited, or null when posting a new one

  /* ---------- Helpers ---------- */
  function setMsg(node, text, type) {
    node.textContent = text || '';
    node.className = 'ann-status' + (type ? ' ' + type : '');
  }

  function formatDate(iso) {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
  }

  function makeButton(label, className, action, id) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'btn btn-small ' + className;
    b.textContent = label;
    b.dataset.action = action;
    b.dataset.id = id;
    return b;
  }

  /* ---------- Rendering ---------- */
  // textContent shows announcement text as plain text, not HTML.
  function buildCard(a, featured) {
    const card = document.createElement('article');
    card.className = 'ann-card' + (featured ? ' featured' : '');
    const top = document.createElement('div');
    top.className = 'ann-top';

    const isRecent = Date.now() - new Date(a.created_at).getTime() < NEW_DAYS * 24 * 60 * 60 * 1000;
    const tagText = featured ? 'Latest' : (isRecent ? 'New' : '');
    if (tagText) {
      const tag = document.createElement('span');
      tag.className = 'ann-pill';
      tag.textContent = tagText;
      top.appendChild(tag);
    }

    const date = document.createElement('span');
    date.className = 'ann-date';
    let dateText = 'Posted ' + formatDate(a.created_at);
    const edited = new Date(a.updated_at) - new Date(a.created_at) > 60 * 1000;
    if (edited) dateText += ' \u00b7 Edited ' + formatDate(a.updated_at);
    date.textContent = dateText;
    top.appendChild(date);
    card.appendChild(top);

    const heading = document.createElement('h2');
    heading.textContent = a.title;
    card.appendChild(heading);

    const body = document.createElement('p');
    body.className = 'ann-body';
    body.textContent = a.content;
    card.appendChild(body);

    if (isAdmin()) {
      const actions = document.createElement('div');
      actions.className = 'ann-actions';
      actions.appendChild(makeButton('Edit', 'btn-secondary', 'edit', a.announcement_id));
      actions.appendChild(makeButton('Delete', 'btn-danger', 'delete', a.announcement_id));
      card.appendChild(actions);
    }
    return card;
  }

  function renderOlder() {
    const matches = items.slice(1).filter((a) =>
      !query || (a.title + ' ' + a.content).toLowerCase().includes(query));

    el.list.replaceChildren();
    matches.slice(0, visibleCount).forEach((a) => el.list.appendChild(buildCard(a, false)));
    el.more.hidden = matches.length <= visibleCount;
    el.empty.hidden = matches.length > 0;
  }

  function render(list) {
    items = list;
    el.featuredCard.replaceChildren();

    el.featured.hidden = list.length === 0;
    el.older.hidden = list.length < 2;
    if (list.length === 0) return;

    el.featuredCard.appendChild(buildCard(list[0], true));
    renderOlder();
  }

  el.search.addEventListener('input', () => {
    query = el.search.value.trim().toLowerCase();
    visibleCount = PAGE_SIZE;
    renderOlder();
  });

  el.more.addEventListener('click', () => {
    visibleCount += PAGE_SIZE;
    renderOlder();
  });

  function refreshAdminUI() {
    el.form.hidden = !isAdmin();
  }

  /* ---------- Loading ---------- */
  async function load() {
    setMsg(el.status, 'Loading announcements...');
    const res = await api.request('/api/announcements');

    if (!res.ok) {
      render([]);
      if (res.status === 401) {
        setMsg(el.status, 'Please log in to see announcements.', 'error');
      } else {
        setMsg(el.status, res.error || 'Could not load announcements.', 'error');
      }
      return false;
    }

    // The backend answers { announcements: [...], ok: true }
    const list = res.data && Array.isArray(res.data.announcements) ? res.data.announcements : [];
    render(list);
    setMsg(el.status, list.length ? '' : 'No announcements yet.');
    return true;
  }

  /* ---------- Admin form: post or edit ---------- */
  function resetForm() {
    editingId = null;
    el.form.reset();
    el.formTitle.textContent = 'Post an announcement';
    el.submit.textContent = 'Post announcement';
    el.cancel.hidden = true;
    setMsg(el.formMsg, '');
  }

  function startEdit(item) {
    editingId = item.announcement_id;
    el.title.value = item.title;
    el.content.value = item.content;
    el.formTitle.textContent = 'Edit announcement';
    el.submit.textContent = 'Save changes';
    el.cancel.hidden = false;
    setMsg(el.formMsg, '');
    el.form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    el.title.focus();
  }

  el.cancel.addEventListener('click', resetForm);

  el.form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const title = el.title.value.trim();
    const content = el.content.value.trim();
    if (!title || !content) {
      return setMsg(el.formMsg, 'Please enter a title and a message.', 'error');
    }

    const wasEdit = editingId !== null;
    el.submit.disabled = true;
    setMsg(el.formMsg, wasEdit ? 'Saving...' : 'Posting...');

    const res = wasEdit
      ? await api.request('/api/announcements/' + encodeURIComponent(editingId), {
          method: 'PUT',
          body: { title, content },
        })
      : await api.request('/api/announcements', {
          method: 'POST',
          body: { title, content },
        });

    el.submit.disabled = false;
    if (!res.ok) {
      return setMsg(el.formMsg, res.error || 'Something went wrong. Please try again.', 'error');
    }

    resetForm();
    setMsg(el.formMsg, wasEdit ? 'Announcement updated.' : 'Announcement posted.', 'ok');
    await load();
  });

  /* ---------- Edit / delete buttons on the cards ---------- */
  async function remove(item, button) {
    if (!window.confirm('Delete "' + item.title + '"? This cannot be undone.')) return;

    button.disabled = true;
    const res = await api.request('/api/announcements/' + encodeURIComponent(item.announcement_id), {
      method: 'DELETE',
    });

    if (!res.ok) {
      button.disabled = false;
      return setMsg(el.status, res.error || 'Could not delete the announcement.', 'error');
    }

    if (editingId === item.announcement_id) resetForm();
    await load();
    setMsg(el.status, 'Announcement deleted.', 'ok');
  }

  document.addEventListener('click', (e) => {
    const button = e.target.closest('[data-action]');
    if (!button) return;
    const item = items.find((a) => a.announcement_id === button.dataset.id);
    if (!item) return;

    if (button.dataset.action === 'edit') startEdit(item);
    if (button.dataset.action === 'delete') remove(item, button);
  });

  /* ---------- Session ended (the request helper above sends this on a 401) ---------- */
  window.addEventListener('cic:session-expired', () => {
    currentRole = null;
    goHome();
  });

  /* ---------- Members-only: no login means back to the home page ---------- */
  const HOME_URL = '/';   // the home page has the login popup
  const hasToken = () => !!sessionStorage.getItem('cic.access_token');
  const goHome = () => window.location.replace(HOME_URL);

  // After "Log out" is clicked, go to the home page once the login is cleared.
  const authButton = document.getElementById('login-button');
  if (authButton) {
    authButton.addEventListener('click', () => {
      let tries = 0;
      const timer = setInterval(() => {
        if (!hasToken()) { clearInterval(timer); goHome(); }
        else if (++tries > 25) clearInterval(timer);   // give up after ~5 seconds
      }, 200);
    });
  }

  /* ---------- Start ---------- */
  (async function init() {
    if (!hasToken()) return goHome();
    await loadRole();      
    refreshAdminUI();
    await load();          
  })();
})();