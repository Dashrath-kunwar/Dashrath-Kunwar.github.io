/* Wires up the light/dark toggle. The theme itself is applied by a tiny inline
   snippet in each page's <head> — it has to run before first paint, otherwise
   a reader who chose light mode gets a black flash on every navigation. */

(function () {
  'use strict';

  var root = document.documentElement;
  var button = document.getElementById('theme-toggle');
  if (!button) return;

  function current() {
    return root.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  }

  function paint() {
    var goingTo = current() === 'light' ? 'dark' : 'light';
    button.textContent = goingTo === 'light' ? '☀ Light' : '☾ Dark';
    button.setAttribute('aria-label', 'Switch to ' + goingTo + ' theme');

    // Keep the browser chrome (mobile address bar) in step with the page.
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', current() === 'light' ? '#fbfaf8' : '#000000');
  }

  button.addEventListener('click', function () {
    var next = current() === 'light' ? 'dark' : 'light';
    if (next === 'light') {
      root.setAttribute('data-theme', 'light');
    } else {
      root.removeAttribute('data-theme');
    }
    try {
      localStorage.setItem('theme', next);
    } catch (e) {
      /* Private mode — the choice just won't survive the session. */
    }
    paint();
  });

  paint();
  button.hidden = false;
})();
