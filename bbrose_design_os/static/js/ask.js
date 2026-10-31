/* [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (4): "No browser pop-ups anywhere ("127.0.0.1 says…"). Any
   confirmation happens inside the page, in plain words, in the house style."] ONE in-page dialog for every page
   (templates/base.html loads this file first): askInPage asks — a promise of true for yes, false for no, Escape or a
   click outside; sayInPage tells — a promise kept when it is closed. Never the browser's own confirm, alert or prompt:
   a test reads every script for them. */
(function () {
  'use strict';
  var dialog = null;
  var settle = null;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text) { n.textContent = text; }
    return n;
  }

  function build() {
    if (dialog) { return dialog; }
    dialog = el('dialog', 'ask-dialog');
    dialog.id = 'ask-dialog';
    dialog.setAttribute('aria-labelledby', 'ask-words');
    var words = el('p', 'ask-words');
    words.id = 'ask-words';
    var actions = el('div', 'ask-actions');
    var no = el('button', 'btn quiet');
    no.type = 'button';
    no.id = 'ask-no';
    var yes = el('button', 'btn primary');
    yes.type = 'button';
    yes.id = 'ask-yes';
    actions.appendChild(no);
    actions.appendChild(yes);
    dialog.appendChild(words);
    dialog.appendChild(actions);
    no.addEventListener('click', function () { done(false); });
    yes.addEventListener('click', function () { done(true); });
    // Escape is "no", as is a click on the dimmed page round it
    dialog.addEventListener('cancel', function (ev) { ev.preventDefault(); done(false); });
    dialog.addEventListener('click', function (ev) { if (ev.target === dialog) { done(false); } });
    document.body.appendChild(dialog);
    return dialog;
  }

  function done(answer) {
    var s = settle;
    settle = null;
    if (dialog && dialog.open) { dialog.close(); }
    if (s) { s(answer); }
  }

  function open(words, yesWords, noWords) {
    var d = build();
    if (settle) { done(false); }             // a question still open is answered "no" — one at a time
    d.querySelector('#ask-words').textContent = words;
    var yes = d.querySelector('#ask-yes');
    var no = d.querySelector('#ask-no');
    yes.textContent = yesWords;
    no.textContent = noWords || '';
    no.hidden = !noWords;
    return new Promise(function (resolve) {
      settle = resolve;
      if (typeof d.showModal === 'function') { d.showModal(); } else { d.setAttribute('open', ''); }
      (noWords ? no : yes).focus();          // the quiet answer is where the cursor rests
    });
  }

  /** words: the question in plain words; opts: {yes: 'Approve', no: 'Not now'} */
  window.askInPage = function (words, opts) {
    opts = opts || {};
    return open(words, opts.yes || 'Yes', opts.no || 'Not now');
  };

  /** words: what happened, in plain words — one button closes it */
  window.sayInPage = function (words, opts) {
    opts = opts || {};
    return open(words, opts.ok || 'Close', '');
  };
})();
