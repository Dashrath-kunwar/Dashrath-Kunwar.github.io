// Service workers need a secure context; file:// and plain http fall through.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch(() => {
      /* Offline support is a bonus, never a requirement. */
    });
  });
}
