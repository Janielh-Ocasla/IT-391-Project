/* Load completed member templates through the existing Bearer-token API.
   The initial document contains no protected markup or user data. */
(async function () {
  const status = document.getElementById('page-status');
  const page = document.body.dataset.cicPage;
  const result = await window.CICApi.request('/api/pages/' + encodeURIComponent(page));

  if (!result.ok) {
    if (result.status === 401) {
      window.location.replace('/?login=1');
      return;
    }
    status.textContent = result.status === 403
      ? 'You do not have access to this page.'
      : result.error || 'Could not load this page. Please try again.';
    return;
  }
  if (result.redirect === '/admin/history') {
    window.location.replace(result.redirect);
    return;
  }
  if (typeof result.html !== 'string' || !result.html) {
    status.textContent = 'Could not load this page. Please try again.';
    return;
  }

  // Render the authorized, same-origin Jinja document intact, including the
  // existing styles and scripts. Database values are escaped by the template.
  document.open();
  document.write(result.html);
  document.close();
})();
