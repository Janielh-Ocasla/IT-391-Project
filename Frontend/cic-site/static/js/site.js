/* =====================================================
   Shared script: builds the login popup and wires it up.
   Any page with a button id="openLogin" gets the popup.
   ===================================================== */
(function () {
  const LOGO = 'https://static.wixstatic.com/media/c5f985_712eb51acfae41ef9dacca664413c454~mv2.png/v1/fill/w_980,h_509,al_c,q_90/transparent%20logo_edited.png';

  const MODAL_HTML = `
  <div class="overlay" id="loginOverlay" aria-hidden="true">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="loginTitle">
      <button class="close" id="closeLogin" aria-label="Close">&times;</button>

      <div class="modal-main">
        <img class="modal-logo" alt="Community Innovation Center" src="${LOGO}" />

        <!-- ===== LOG IN ===== -->
        <section class="view active" data-view="login">
          <h2 id="loginTitle">Welcome to CIC</h2>
          <p class="sub">Log in to access the Message Board, File Share, and the Volunteer Hub</p>

          <form id="loginForm" novalidate>
            <div class="field">
              <input type="email" id="loginEmail" placeholder="Email" autocomplete="email" required />
            </div>
            <div class="field">
              <input type="password" id="loginPassword" placeholder="Password" autocomplete="current-password" required />
              <button type="button" class="toggle-pw" data-toggle="loginPassword" aria-label="Show password">&#128065;</button>
            </div>
            <div class="msg" id="loginMsg" role="alert"></div>
            <button type="button" class="link forgot" data-goto="forgot">Forgot your password?</button>
            <button type="submit" class="btn btn-primary full">Log in</button>
          </form>

          <div class="divider">OR</div>

          <button class="social" data-provider="Google"><span class="ico g">G</span> Continue with Google</button>
          <button class="social" data-provider="Facebook"><span class="ico f">f</span> Continue with Facebook</button>

          <p class="switch-line">New to CIC? <button type="button" class="link bold" data-goto="signup">Create account</button></p>
        </section>

        <!-- ===== CREATE ACCOUNT ===== -->
        <section class="view" data-view="signup">
          <h2>Create your account</h2>
          <p class="sub">Join CIC as a volunteer and connect with your community</p>

          <form id="signupForm" novalidate>
            <div class="row">
              <div class="field">
                <input type="text" id="firstName" placeholder="First name" autocomplete="given-name" required />
              </div>
              <div class="field">
                <input type="text" id="lastName" placeholder="Last name" autocomplete="family-name" required />
              </div>
            </div>
            <div class="field">
              <input type="email" id="signupEmail" placeholder="Email" autocomplete="email" required />
            </div>
            <div class="field">
              <input type="tel" id="phone" placeholder="Phone number (optional)" autocomplete="tel" />
            </div>
            <div class="field">
              <input type="password" id="signupPassword" placeholder="Password (8+ characters)" autocomplete="new-password" required />
              <button type="button" class="toggle-pw" data-toggle="signupPassword" aria-label="Show password">&#128065;</button>
            </div>
            <div class="msg" id="signupMsg" role="alert"></div>
            <button type="submit" class="btn btn-primary full">Create account</button>
          </form>

          <p class="switch-line">Already have an account? <button type="button" class="link bold" data-goto="login">Log in</button></p>
          <p class="legal">
            By continuing, you agree to our
            <a href="#">Terms &amp; Conditions</a> &middot; <a href="#">Privacy Policy</a>
          </p>
        </section>

        <!-- ===== FORGOT PASSWORD ===== -->
        <section class="view" data-view="forgot">
          <h2>Reset your password</h2>
          <p class="sub">Enter your email and we'll send you a link to reset it</p>

          <form id="forgotForm" novalidate>
            <div class="field">
              <input type="email" id="forgotEmail" placeholder="Email" autocomplete="email" required />
            </div>
            <div class="msg" id="forgotMsg" role="alert"></div>
            <button type="submit" class="btn btn-primary full">Send reset link</button>
          </form>

          <p class="switch-line"><button type="button" class="link bold" data-goto="login">Back to log in</button></p>
        </section>
      </div>

      <aside class="modal-side">
        <img alt="" src="${LOGO}" />
        <h3>Connect hearts, transform lives, and belong.</h3>
        <ul class="perks">
          <li>Member Message Board</li>
          <li>Shared files &amp; resources</li>
          <li>Volunteer sign-ups &amp; events</li>
        </ul>
      </aside>
    </div>
  </div>`;

  document.body.insertAdjacentHTML('beforeend', MODAL_HTML);

  const overlay  = document.getElementById('loginOverlay');
  const openBtn  = document.getElementById('openLogin');
  const closeBtn = document.getElementById('closeLogin');
  let loggedIn = false;

  /* ---------- Helpers ---------- */
  async function api(path, payload) {
    const options = payload === undefined
      ? { credentials: 'same-origin' }
      : {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        };
    try {
      const res = await fetch(path, options);
      const data = await res.json().catch(() => ({}));
      return { status: res.status, ...data };
    } catch (err) {
      return { ok: false, error: 'Could not reach the server. Is it running?' };
    }
  }

  function setMsg(id, text, type) {
    const el = document.getElementById(id);
    el.textContent = text || '';
    el.className = 'msg' + (type ? ' ' + type : '');
  }

  function showView(name) {
    document.querySelectorAll('.view').forEach(v =>
      v.classList.toggle('active', v.dataset.view === name));
    ['loginMsg', 'signupMsg', 'forgotMsg'].forEach(id => setMsg(id, ''));
    const first = document.querySelector('.view.active input');
    if (first) first.focus();
  }

  function busy(form, isBusy) {
    form.querySelector('button[type="submit"]').disabled = isBusy;
  }

  const emailOk = (v) => /^\S+@\S+\.\S+$/.test(v.trim());

  /* ---------- Open / close popup ---------- */
  function openModal() {
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    showView('login');
  }

  function closeModal() {
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    if (openBtn) openBtn.focus();
  }

  function updateHeaderButton() {
    if (openBtn) openBtn.textContent = loggedIn ? 'Log out' : 'Login/Signup';
  }

  if (openBtn) {
    openBtn.addEventListener('click', async () => {
      if (loggedIn) {
        await api('/api/logout', {});
        loggedIn = false;
        updateHeaderButton();
        return;
      }
      openModal();
    });
  }
  closeBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay.classList.contains('open')) closeModal();
  });

  // Switch between views
  document.querySelectorAll('[data-goto]').forEach(btn =>
    btn.addEventListener('click', () => showView(btn.dataset.goto)));

  // Show / hide password
  document.querySelectorAll('[data-toggle]').forEach(btn =>
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.toggle);
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    }));

  /* ---------- Log in ---------- */
  document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;

    if (!emailOk(email)) return setMsg('loginMsg', 'Please enter a valid email address.', 'error');
    if (!password)       return setMsg('loginMsg', 'Please enter your password.', 'error');

    busy(form, true);
    setMsg('loginMsg', 'Logging in...');
    const res = await api('/api/login', { email, password });
    busy(form, false);

    if (!res.ok) return setMsg('loginMsg', res.error || 'Login failed.', 'error');

    loggedIn = true;
    form.reset();
    updateHeaderButton();
    closeModal();
    // TODO: send people to the right dashboard based on res.role
    // (e.g. 'volunteer' vs. an admin role)
    console.log('Logged in with role:', res.role);
  });

  /* ---------- Create account ---------- */
  document.getElementById('signupForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const payload = {
      first_name: document.getElementById('firstName').value,
      last_name:  document.getElementById('lastName').value,
      email:      document.getElementById('signupEmail').value,
      phone:      document.getElementById('phone').value,
      password:   document.getElementById('signupPassword').value,
    };

    if (!payload.first_name.trim() || !payload.last_name.trim())
      return setMsg('signupMsg', 'Please enter your first and last name.', 'error');
    if (!emailOk(payload.email))
      return setMsg('signupMsg', 'Please enter a valid email address.', 'error');
    if (payload.password.length < 8)
      return setMsg('signupMsg', 'Password must be at least 8 characters.', 'error');

    busy(form, true);
    setMsg('signupMsg', 'Creating your account...');
    const res = await api('/api/signup', payload);
    busy(form, false);

    if (!res.ok) return setMsg('signupMsg', res.error || 'Could not create account.', 'error');

    form.reset();
    showView('login');
    setMsg('loginMsg', 'Account created! Check your email to confirm it if asked, then log in.', 'ok');
  });

  /* ---------- Forgot password ---------- */
  document.getElementById('forgotForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const email = document.getElementById('forgotEmail').value;

    if (!emailOk(email)) return setMsg('forgotMsg', 'Please enter a valid email address.', 'error');

    busy(form, true);
    await api('/api/reset-password', { email });
    busy(form, false);
    setMsg('forgotMsg', 'If an account exists for that email, a reset link is on its way.', 'ok');
  });

  /* ---------- Google / Facebook (not set up yet) ---------- */
  document.querySelectorAll('[data-provider]').forEach(btn =>
    btn.addEventListener('click', () =>
      setMsg('loginMsg', btn.dataset.provider + " sign in isn't set up yet. Please use email.", 'error')));

  /* ---------- On page load: am I already logged in? ---------- */
  (async () => {
    const res = await api('/api/me');
    if (res.logged_in) {
      loggedIn = true;
      updateHeaderButton();
    }
  })();
})();
