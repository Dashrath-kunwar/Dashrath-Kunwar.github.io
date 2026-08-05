/* Client-side search over the catalogue. No dependencies.
   The list is real HTML, so it works fine with JS off — this only filters it. */

(function () {
  'use strict';

  var form = document.getElementById('search-form');
  var input = document.getElementById('q');
  var countEl = document.getElementById('count');
  var noResults = document.getElementById('no-results');
  var collectionIndex = document.getElementById('collection-index');
  var library = document.getElementById('library');

  if (!form || !input || !library) return;

  // Case- and accent-insensitive: "levi" matches "Lévi", "SACRED" matches "Sacred".
  function normalise(s) {
    return s
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '');
  }

  // Build the index once. Each entry carries its collection name too, so
  // searching "mathematics" surfaces that whole shelf.
  var sections = [];
  var entries = [];

  Array.prototype.forEach.call(library.querySelectorAll('.collection'), function (section) {
    var heading = section.querySelector('h2');
    var name = heading ? heading.firstChild.textContent : '';
    var items = [];

    Array.prototype.forEach.call(section.querySelectorAll('li'), function (li) {
      // Join the author/title/year elements with spaces — textContent alone
      // would run them together and invent words like "GuenonIntroduction".
      var fields = [];
      Array.prototype.forEach.call(li.children, function (child) {
        fields.push(child.textContent);
      });
      var entry = {
        el: li,
        text: normalise(fields.join(' ') + ' ' + name),
        shown: true
      };
      entries.push(entry);
      items.push(entry);
    });

    sections.push({ el: section, items: items, shown: true });
  });

  var total = entries.length;

  function plural(n) {
    return n === 1 ? '1 book' : n.toLocaleString('en') + ' books';
  }

  function apply(query) {
    var tokens = normalise(query).split(/\s+/).filter(Boolean);
    var visible = 0;

    for (var i = 0; i < sections.length; i++) {
      var section = sections[i];
      var sectionVisible = 0;

      for (var j = 0; j < section.items.length; j++) {
        var entry = section.items[j];
        var show = true;

        for (var k = 0; k < tokens.length; k++) {
          if (entry.text.indexOf(tokens[k]) === -1) {
            show = false;
            break;
          }
        }

        // Only touch the DOM when the state actually flips — keeps typing smooth
        // across a couple of thousand nodes.
        if (show !== entry.shown) {
          entry.el.hidden = !show;
          entry.shown = show;
        }
        if (show) sectionVisible++;
      }

      var sectionShow = sectionVisible > 0;
      if (sectionShow !== section.shown) {
        section.el.hidden = !sectionShow;
        section.shown = sectionShow;
      }

      // Collections are collapsed by default. While a search is running, open
      // the ones that matched so the hits are actually visible; clearing the
      // box collapses everything again.
      var shouldOpen = tokens.length > 0 && sectionShow;
      if (section.el.open !== shouldOpen) section.el.open = shouldOpen;

      visible += sectionVisible;
    }

    var searching = tokens.length > 0;
    noResults.hidden = visible !== 0;
    if (collectionIndex) collectionIndex.hidden = searching;

    if (!searching) {
      countEl.textContent = plural(total) + ' in ' + sections.length + ' collections';
    } else {
      countEl.textContent = plural(visible) + ' of ' + total.toLocaleString('en');
    }

    // Keep the search shareable.
    try {
      var url = new URL(window.location.href);
      if (searching) {
        url.searchParams.set('q', query);
      } else {
        url.searchParams.delete('q');
      }
      window.history.replaceState(null, '', url);
    } catch (e) {
      /* Older browsers just don't get shareable URLs. */
    }
  }

  input.addEventListener('input', function () {
    apply(input.value);
  });

  input.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      input.value = '';
      apply('');
    }
  });

  form.addEventListener('submit', function (event) {
    event.preventDefault();
  });

  // Search is live, so reveal the control now that we know it works.
  form.hidden = false;

  var initial = '';
  try {
    initial = new URL(window.location.href).searchParams.get('q') || '';
  } catch (e) {
    initial = '';
  }
  if (initial) input.value = initial;
  apply(initial);

  // Jumping to #some-collection from the index should open it, not scroll to a
  // closed heading. Browsers don't expand <details> for a fragment on their own.
  function openTarget() {
    var id = window.location.hash.slice(1);
    if (!id) return;
    var target = document.getElementById(id);
    if (target && target.tagName === 'DETAILS') {
      target.open = true;
      target.scrollIntoView();
    }
  }

  window.addEventListener('hashchange', openTarget);
  openTarget();
})();
