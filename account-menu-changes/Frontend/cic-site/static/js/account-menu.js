/* =====================================================
   Account menu: one dropdown that replaces the separate
   "Account Settings" / "Sign Out" buttons and the
   "Login / Sign Up" button across the member pages.

   Behavior:
   - Signed in  -> show the account menu, hide any #login-button.
   - Signed out -> hide the account menu, leave #login-button
                   for site.js to show "Login / Sign Up".

   Reuses api.js (window.CICApi) and site.js (which already
   wires [data-signout] to log out). Load this AFTER site.js.
   ===================================================== */
(function () {
  const menu = document.querySelector('[data-account-menu]');
  if (!menu) return;

  const api = window.CICApi;
  const toggle = menu.querySelector('.account-trigger');
  const roleEl = menu.querySelector('[data-account-role]');
  // The login button that site.js manages (only on some pages).
  const loginBtn = document.getElementById('login-button') || document.getElementById('openLogin');

  function openMenu() {
    menu.classList.add('open');
    toggle.setAttribute('aria-expanded', 'true');
  }
  function closeMenu() {
    menu.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
  }

  toggle.addEventListener('click', function (e) {
    e.stopPropagation();
    menu.classList.contains('open') ? closeMenu() : openMenu();
  });
  document.addEventListener('click', function (e) {
    if (!menu.contains(e.target)) closeMenu();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeMenu();
  });

  // ----- Reset password: inline form that calls /api/reset-password -----
  const resetBtn = menu.querySelector('[data-account-reset]');
  const resetPanel = menu.querySelector('.account-reset');
  const resetForm = menu.querySelector('#account-reset-form');
  const resetMsg = menu.querySelector('#account-reset-msg');

  if (resetBtn && resetPanel) {
    resetBtn.addEventListener('click', function () {
      resetPanel.hidden = !resetPanel.hidden;
      if (!resetPanel.hidden) resetPanel.querySelector('input').focus();
    });
  }

  if (resetForm) {
    resetForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      const email = (resetForm.querySelector('input').value || '').trim();
      if (!/^\S+@\S+\.\S+$/.test(email)) {
        resetMsg.textContent = 'Please enter a valid email address.';
        resetMsg.className = 'account-msg error';
        return;
      }
      const submit = resetForm.querySelector('button');
      submit.disabled = true;
      resetMsg.textContent = 'Sending…';
      resetMsg.className = 'account-msg';

      const res = await api.request('/api/reset-password', { method: 'POST', body: { email: email } });
      submit.disabled = false;

      if (res.ok) {
        resetMsg.textContent = 'If an account exists for that email, a reset link is on its way.';
        resetMsg.className = 'account-msg ok';
        resetForm.reset();
      } else {
        resetMsg.textContent = res.error || 'Could not send the reset link. Please try again.';
        resetMsg.className = 'account-msg error';
      }
    });
  }

  // Note: Sign out ([data-signout]) is already handled by site.js.

  // ----- Show the menu (and hide the login button) only when signed in -----
  async function refresh() {
    if (!api) return;
    const res = await api.request('/api/me');
    const signedIn = res.ok && res.logged_in;
    menu.hidden = !signedIn;
    if (loginBtn) loginBtn.hidden = signedIn;
    if (signedIn && roleEl) {
      roleEl.textContent = res.role ? ('Signed in · ' + res.role) : 'Signed in';
    }
  }

  refresh();
  window.addEventListener('cic:session-expired', refresh);
})();
