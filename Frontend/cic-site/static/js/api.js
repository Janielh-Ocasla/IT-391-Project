/* One same-origin client for authentication, tasks, announcements and uploads. */
(function () {
  const TOKEN_KEY = 'cic.access_token';

  async function request(path, { method = 'GET', body } = {}) {
    if (!path.startsWith('/api/')) {
      throw new Error('CIC API requests must use a same-origin /api/ path.');
    }

    const token = sessionStorage.getItem(TOKEN_KEY);
    const headers = { Accept: 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;

    const options = { method, headers, credentials: 'omit' };
    if (body instanceof FormData) {
      options.body = body; // The browser supplies the multipart boundary.
    } else if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(path, options);
      const data = await response.json().catch(() => null);
      if (response.status === 401 && token === sessionStorage.getItem(TOKEN_KEY)) {
        sessionStorage.removeItem(TOKEN_KEY);
        window.dispatchEvent(new CustomEvent('cic:session-expired'));
      }
      if (!data || Array.isArray(data) || typeof data !== 'object') {
        return { ok: false, status: response.status, error: 'Unexpected server response.' };
      }
      return { ...data, ok: response.ok && data.ok === true, status: response.status };
    } catch (error) {
      return { ok: false, status: 0, error: 'Could not reach the server. Please try again.' };
    }
  }

  async function login(credentials) {
    const result = await request('/api/login', { method: 'POST', body: credentials });
    if (result.ok) {
      if (typeof result.access_token !== 'string' || !result.access_token) {
        return { ok: false, status: result.status, error: 'Login did not return an access token.' };
      }
      sessionStorage.setItem(TOKEN_KEY, result.access_token);
    }
    return result;
  }

  async function logout() {
    try {
      return await request('/api/logout', { method: 'POST', body: {} });
    } finally {
      sessionStorage.removeItem(TOKEN_KEY);
    }
  }

  window.CICApi = { request, login, logout };
})();
