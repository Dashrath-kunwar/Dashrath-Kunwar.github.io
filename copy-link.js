// minimal successor to the old share.js: one button, copies the permalink, that's it
(function () {
  var btn = document.querySelector('.copy-link');
  if (!btn) return;

  var label = btn.textContent;
  var timer = null;

  btn.addEventListener('click', function () {
    if (!navigator.clipboard) return; // e.g. opened over file:// instead of https
    navigator.clipboard.writeText(location.href).then(function () {
      btn.textContent = 'copied';
      btn.classList.add('copied');
      clearTimeout(timer);
      timer = setTimeout(function () {
        btn.textContent = label;
        btn.classList.remove('copied');
      }, 1500);
    }).catch(function () {});
  });
})();
