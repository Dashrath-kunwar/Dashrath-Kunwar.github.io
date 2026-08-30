// bar at the top of a post that fills up as you scroll. that's the whole feature.
(function () {
  var bar = document.querySelector('.progress-bar');
  if (!bar) return; // not a post page, nothing to do

  function update() {
    var scrollable = document.documentElement.scrollHeight - window.innerHeight;
    var pct = scrollable > 0 ? (window.scrollY / scrollable) * 100 : 0;
    bar.style.width = pct + '%';
  }

  document.addEventListener('scroll', update, { passive: true }); // passive: don't block scrolling to run this
  window.addEventListener('resize', update);
  update(); // set initial width, don't wait for the first scroll event
})();
