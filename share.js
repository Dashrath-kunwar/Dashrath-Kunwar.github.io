/* Sharing for essays — the whole post, or a passage the reader has selected.

   Whole post: native share sheet where the browser has one (that's the route
   to Instagram, WhatsApp, etc. on a phone), otherwise copy-link and an X
   intent link that already works without any JavaScript.

   Passage: select text inside the article and a small toolbar appears offering
   copy, a deep link that scrolls the recipient straight to the passage, and
   share/post options. */

(function () {
  'use strict';

  var article = document.querySelector('.post');
  var shareBar = document.querySelector('[data-share]');
  if (!article && !shareBar) return;

  var pageUrl = (document.querySelector('link[rel=canonical]') || {}).href || location.href;
  var pageTitle = (document.querySelector('.post-header h1') || document.querySelector('h1') || {}).textContent || document.title;
  pageTitle = pageTitle.trim();

  // --- announcements ------------------------------------------------------

  var live = document.createElement('p');
  live.className = 'visually-hidden';
  live.setAttribute('role', 'status');
  live.setAttribute('aria-live', 'polite');
  document.body.appendChild(live);

  function announce(message) {
    live.textContent = '';
    // Reassigning after a tick makes screen readers re-announce a repeat.
    setTimeout(function () { live.textContent = message; }, 50);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    // Fallback for non-secure contexts and older browsers.
    return new Promise(function (resolve, reject) {
      var field = document.createElement('textarea');
      field.value = text;
      field.setAttribute('readonly', '');
      field.style.position = 'absolute';
      field.style.left = '-9999px';
      document.body.appendChild(field);
      var previous = document.getSelection().rangeCount
        ? document.getSelection().getRangeAt(0)
        : null;
      field.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      document.body.removeChild(field);
      if (previous) {
        document.getSelection().removeAllRanges();
        document.getSelection().addRange(previous);
      }
      ok ? resolve() : reject();
    });
  }

  function flash(button, message) {
    // Capture the real label only when no flash is already running — clicking
    // twice inside the window would otherwise "restore" the flash message and
    // leave the button permanently reading "Copied".
    if (button._flashTimer) {
      clearTimeout(button._flashTimer);
    } else {
      button._flashLabel = button.textContent;
    }
    button.textContent = message;
    announce(message);
    button._flashTimer = setTimeout(function () {
      button.textContent = button._flashLabel;
      button._flashTimer = null;
    }, 1600);
  }

  // --- deep link to a passage --------------------------------------------

  // Text fragments (#:~:text=) let a link scroll to and highlight an exact
  // passage. Supported in Chrome, Edge and Safari 16.4+; elsewhere the link
  // still opens the post, just without the highlight.
  function encodeFragment(s) {
    return encodeURIComponent(s).replace(/-/g, '%2D');
  }

  function passageLink(text) {
    var clean = text.replace(/\s+/g, ' ').trim();
    var fragment;
    if (clean.length <= 300) {
      fragment = encodeFragment(clean);
    } else {
      // Long passages use the start,end form rather than the whole string.
      var head = clean.slice(0, 60).split(' ').slice(0, -1).join(' ') || clean.slice(0, 60);
      var tail = clean.slice(-60).split(' ').slice(1).join(' ') || clean.slice(-60);
      fragment = encodeFragment(head) + ',' + encodeFragment(tail);
    }
    return pageUrl.split('#')[0] + '#:~:text=' + fragment;
  }

  function quoteFor(text) {
    var clean = text.replace(/\s+/g, ' ').trim();
    if (clean.length > 240) clean = clean.slice(0, 237).replace(/\s+\S*$/, '') + '…';
    return '“' + clean + '”';
  }

  function xIntent(text, url) {
    return 'https://twitter.com/intent/tweet?text=' +
      encodeURIComponent(text) + '&url=' + encodeURIComponent(url);
  }

  // --- whole-post share bar ----------------------------------------------

  if (shareBar) {
    var nativeButton = shareBar.querySelector('[data-share-native]');
    var copyButton = shareBar.querySelector('[data-share-copy]');

    if (nativeButton && navigator.share) {
      nativeButton.hidden = false;
      nativeButton.addEventListener('click', function () {
        navigator.share({ title: pageTitle, text: pageTitle, url: pageUrl })
          .catch(function () { /* dismissed */ });
      });
    }

    if (copyButton) {
      copyButton.hidden = false;
      copyButton.addEventListener('click', function () {
        copyText(pageUrl).then(
          function () { flash(copyButton, 'Copied'); },
          function () { flash(copyButton, 'Press Ctrl+C'); }
        );
      });
    }
  }

  // --- passage toolbar ----------------------------------------------------

  if (!article) return;

  var popup = document.createElement('div');
  popup.className = 'selection-share';
  popup.setAttribute('role', 'group');
  popup.setAttribute('aria-label', 'Share selected passage');
  popup.hidden = true;

  function addButton(label, handler) {
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = label;
    b.addEventListener('click', function () { handler(b); });
    popup.appendChild(b);
    return b;
  }

  var selectedText = '';

  addButton('Copy', function (button) {
    copyText(quoteFor(selectedText) + '\n\n— ' + pageTitle + '\n' + passageLink(selectedText))
      .then(
        function () { flash(button, 'Copied'); },
        function () { flash(button, 'Failed'); }
      );
  });

  addButton('Copy link', function (button) {
    copyText(passageLink(selectedText)).then(
      function () { flash(button, 'Link copied'); },
      function () { flash(button, 'Failed'); }
    );
  });

  addButton('Post', function () {
    window.open(xIntent(quoteFor(selectedText), passageLink(selectedText)),
      '_blank', 'noopener,noreferrer');
  });

  var nativePassage = addButton('Share', function () {
    navigator.share({
      title: pageTitle,
      text: quoteFor(selectedText),
      url: passageLink(selectedText)
    }).catch(function () { /* dismissed */ });
  });
  nativePassage.hidden = !navigator.share;

  document.body.appendChild(popup);

  // Set when the reader dismisses the toolbar with Escape. Without it the
  // keyup handler would re-open the toolbar milliseconds after keydown closed
  // it, because the text is still selected.
  var dismissed = false;

  function hide() {
    popup.hidden = true;
  }

  function show() {
    if (dismissed) return;

    var selection = window.getSelection();
    if (!selection || selection.isCollapsed || selection.rangeCount === 0) return hide();

    var text = selection.toString();
    if (text.replace(/\s+/g, ' ').trim().length < 4) return hide();

    // Only offer this for the essay body, not nav, footer or the share bar.
    var range = selection.getRangeAt(0);
    if (!article.contains(range.commonAncestorContainer)) return hide();

    selectedText = text;

    var rect = range.getBoundingClientRect();
    if (!rect.width && !rect.height) return hide();

    popup.hidden = false;

    // Never let the toolbar grow wider than the viewport — an absolutely
    // positioned element that does will stretch the document and give the
    // whole page a horizontal scrollbar on narrow screens.
    var available = document.documentElement.clientWidth - 16;
    popup.style.maxWidth = available + 'px';

    var top = rect.top + window.pageYOffset - popup.offsetHeight - 8;
    var left = rect.left + window.pageXOffset + rect.width / 2 - popup.offsetWidth / 2;

    // If there's no room above the selection, sit below it instead.
    if (top < window.pageYOffset + 4) top = rect.bottom + window.pageYOffset + 8;

    var margin = 8;
    var maxLeft = document.documentElement.clientWidth - popup.offsetWidth - margin;
    if (left < margin) left = margin;
    if (left > maxLeft) left = Math.max(margin, maxLeft);

    popup.style.top = top + 'px';
    popup.style.left = left + 'px';
  }

  // Keep the selection alive when the toolbar itself is clicked.
  popup.addEventListener('mousedown', function (event) { event.preventDefault(); });

  // A fresh pointer gesture means the reader is selecting again, so drop the
  // dismissed state.
  document.addEventListener('mousedown', function (event) {
    if (!popup.contains(event.target)) dismissed = false;
  });

  document.addEventListener('touchstart', function (event) {
    if (!popup.contains(event.target)) dismissed = false;
  }, { passive: true });

  document.addEventListener('mouseup', function (event) {
    if (popup.contains(event.target)) return;
    setTimeout(show, 10);
  });

  document.addEventListener('touchend', function (event) {
    if (popup.contains(event.target)) return;
    setTimeout(show, 10);
  });

  // Shift+arrow extends a keyboard selection. Escape is deliberately not here:
  // it closes the toolbar, and re-showing it on the matching keyup would undo
  // that immediately.
  document.addEventListener('keyup', function (event) {
    if (event.key === 'Escape') return;
    if (event.shiftKey) setTimeout(show, 10);
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      dismissed = true;
      hide();
    }
  });

  document.addEventListener('selectionchange', function () {
    var selection = window.getSelection();
    if (!selection || selection.isCollapsed) hide();
  });

  window.addEventListener('resize', hide);
})();
