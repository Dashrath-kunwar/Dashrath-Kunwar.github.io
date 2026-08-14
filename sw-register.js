// Service workers need a secure context; file:// and plain http fall through.
// Root-absolute and scoped to '/': this script is included from every depth
// (root pages and writings/*.html alike), and a page-relative path would
// resolve against the essay's URL instead of the site's, 404ing under /writings/.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {
      /* Offline support is a bonus, never a requirement. */
    });
  });
}
