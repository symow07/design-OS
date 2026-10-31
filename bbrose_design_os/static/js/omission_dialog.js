// Packaging omission confirmation controller (B4b-2C §4/§5/§10).
//
// One narrow job: present the server-rendered #omission-dialog as a modal
// question and hand EXACTLY ONE outcome — cancel, return, or submit — back to
// whoever opened it. It owns no reference state and no submission logic;
// poll.js decides what each outcome means.
//
// The dialog element is native: showModal() gives the top-layer focus trap,
// inert background and Escape handling for free, so none of that is
// reimplemented here. Approval is one-shot by construction — the callbacks
// are dropped the moment an outcome fires, and every later submission
// attempt must open the dialog again.
(function () {
  'use strict';

  var callbacks = null;   // live only while the dialog is open
  var opener = null;      // element to give focus back to on cancel
  var settled = false;    // guards double clicks / Enter-key repeats

  function dialogEl() {
    return document.getElementById('omission-dialog');
  }

  function settle(outcome) {
    // first outcome wins; the buttons stay clickable for a tick after
    // close() so this guard is what actually prevents double dispatch
    if (settled || !callbacks) return;
    settled = true;
    var cbs = callbacks;
    callbacks = null;
    var dlg = dialogEl();
    if (dlg && dlg.open) dlg.close();
    if (outcome === 'cancel') {
      // §10: focus returns to the control that opened the dialog
      if (opener && opener.focus) opener.focus();
      if (cbs.onCancel) cbs.onCancel();
    } else if (outcome === 'return') {
      if (cbs.onReturn) cbs.onReturn();
    } else if (outcome === 'submit') {
      if (cbs.onSubmit) cbs.onSubmit();
    }
    opener = null;
  }

  function bind() {
    var dlg = dialogEl();
    if (!dlg) return;
    document.getElementById('omission-cancel')
      .addEventListener('click', function () { settle('cancel'); });
    document.getElementById('omission-return')
      .addEventListener('click', function () { settle('return'); });
    document.getElementById('omission-submit')
      .addEventListener('click', function () { settle('submit'); });
    // Escape fires the native cancel event — route it through the same
    // single-outcome door instead of letting the browser just close
    dlg.addEventListener('cancel', function (ev) {
      ev.preventDefault();
      settle('cancel');
    });
    // showModal makes the background inert, but sequential focus can still
    // rest on <body> between the last and first control — wrap explicitly so
    // Tab and Shift+Tab never leave the dialog (§10)
    dlg.addEventListener('keydown', function (ev) {
      if (ev.key !== 'Tab') return;
      var first = document.getElementById('omission-cancel');
      var last = document.getElementById('omission-submit');
      if (ev.shiftKey && document.activeElement === first) {
        ev.preventDefault();
        last.focus();
      } else if (!ev.shiftKey && document.activeElement === last) {
        ev.preventDefault();
        first.focus();
      }
    });
  }

  window.DesignOSOmissionDialog = {
    /** opts: {count, needsCorrection, opener, onCancel, onReturn, onSubmit} */
    open: function (opts) {
      var dlg = dialogEl();
      if (!dlg || dlg.open) return false;
      settled = false;
      callbacks = opts || {};
      // the element focus goes back to on cancel. Passed explicitly by the
      // opener because the triggering control may be disabled (and therefore
      // unfocused) at this exact moment.
      opener = (opts && opts.opener) || document.activeElement;
      var n = opts.count || 0;
      document.getElementById('omission-desc').textContent =
        n + ' staged Product Container reference file' +
        (n === 1 ? '' : 's') + ' will NOT be attached to this Packaging ' +
        'task. ' + (n === 1 ? 'It stays' : 'They stay') + ' held in your ' +
        'browser for a Product Container task.';
      document.getElementById('omission-correction').hidden =
        !opts.needsCorrection;
      dlg.showModal();
      // initial focus on the safest, non-destructive action (§10)
      document.getElementById('omission-cancel').focus();
      return true;
    },
    isOpen: function () {
      var dlg = dialogEl();
      return !!(dlg && dlg.open);
    },
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
