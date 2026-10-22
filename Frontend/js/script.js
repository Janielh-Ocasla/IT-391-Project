const openBtn = document.getElementById('login-button');
const closeBtn = document.getElementById('close-login');
const overlay = document.getElementById('login-overlay');

// Open popup (Fades in)
openBtn.addEventListener('click', () => {
  overlay.classList.add('active');
});

// Close popup via button (Fades out)
closeBtn.addEventListener('click', () => {
  overlay.classList.remove('active');
});

// Close popup if clicking outside the login box (Fades out)
overlay.addEventListener('click', (e) => {
  if (e.target === overlay) {
    overlay.classList.remove('active');
  }
});

