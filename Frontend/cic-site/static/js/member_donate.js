/* =====================================================
   Member donate page:
   Members-only guard: visitors who aren't logged in go to the home page.
   "Copy email" button for the Zelle address.
   ===================================================== */
(function () {
  /* Members-only: no login means back to the home page */
  const HOME_URL = '/';   // the home page has the login popup
  const hasToken = () => !!sessionStorage.getItem('cic.access_token');
  const goHome = () => window.location.replace(HOME_URL);

  // site.js clears the token when "Log out" is clicked but doesn't change pages,
  // so watch for that and leave this page once the token is gone.
  const authButton = document.getElementById('login-button');
  if (authButton) {
    authButton.addEventListener('click', () => {
      let tries = 0;
      const timer = setInterval(() => {
        if (!hasToken()) { clearInterval(timer); goHome(); }
        // give up after ~5 seconds
        else if (++tries > 25) clearInterval(timer);   
      }, 200);
    });
  }

  if (!hasToken()) { goHome(); return; }

  const button = document.getElementById('zelle-copy');
  const emailEl = document.getElementById('zelle-email');
  const msg = document.getElementById('zelle-copy-msg');
  if (!button || !emailEl || !msg) return;

  const email = emailEl.textContent.trim();
  // show the button only when JS is running
  button.hidden = false; 
  function show(text) {
    msg.textContent = text;
    setTimeout(() => { msg.textContent = ''; }, 2500);
  }

  // If the copy button doesn't work, highlight the email so the person can copy it by hand
  function selectEmail() {
    const range = document.createRange();
    range.selectNodeContents(emailEl);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }

  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(email);
      show('Copied!');
    } catch (err) {
      selectEmail();
      show('Press Ctrl/Cmd + C to copy.');
    }
  });
})();