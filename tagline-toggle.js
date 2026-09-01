// clicking the tagline swaps its own text between Hindi and English in place.
// toggling `lang` (not a class) is what matters -- .tagline:lang(hi) in the
// CSS is what switches the typography, so English falls back to the same
// bold/uppercase/stroke treatment as the rest of the masthead automatically.
(function () {
  var el = document.querySelector('.tagline');
  if (!el) return;

  el.addEventListener('click', function () {
    var showingHindi = el.lang === 'hi';
    el.lang = showingHindi ? 'en' : 'hi';
    el.textContent = showingHindi ? el.dataset.en : el.dataset.hi;
  });
})();
