/* staged_reference_ui.js — B4b-2A-2/2A-3: DOM, cards and announcements.
 *
 * Thin by design. Everything stateful — ids, ordering, object URLs, the
 * submitting lock, FormData — lives in staged_references.js; this module
 * parses the server-rendered configuration once, binds the five category
 * zones, renders cards from controller.list(), and announces changes.
 * It never calls URL.createObjectURL/revokeObjectURL itself.
 *
 * Submission integration (2A-3): poll.js appends staged files through
 * window.DesignOSReferenceUI.appendToFormData — the canonical inventory is
 * the ONLY payload source. Native file inputs are picker controls and nothing
 * more: their value is cleared as soon as a selection is staged (so the same
 * file can be chosen again), and input.files is never assigned or read as
 * state — no browser file-transfer capability is required. The temporary
 * 2A-2 compatibility bridge is gone; docs/roadmap/b4b_2_progress.json keeps
 * its history.
 */
(function () {
  'use strict';

  var controller = null;
  var section = null;
  var liveEl = null;
  var errorsEl = null;
  var categoryLabels = {};
  // Rendered configuration (B4b-2B §3): the size limit and the allowlist come
  // from #reference-config and nowhere else — no second literal, ever.
  var cfg = {maxBytes: 0, maxMb: 0, allowed: []};
  // Validation state. clientErrors are files refused BEFORE staging (they own
  // no entry and no object URL); cardErrors map a staged entry id to the
  // server's verdict — the entry itself stays staged, previewed and removable.
  var clientErrors = [];
  var cardErrors = {};
  var generalError = null;
  // B4b-2C §2/§3: whether the Product Container editor is the visible target.
  // poll.js drives this on every target switch; while false, the canonical
  // inventory is HELD (nothing is cleared by a switch) and the held-reference
  // notice speaks for it.
  var containerVisible = true;
  var heldNoticeEl = null;

  // ---- helpers ------------------------------------------------------------

  function humanSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function announce(msg) {
    if (liveEl) liveEl.textContent = msg;
  }

  // ---- preliminary validation (B4b-2B §4/§5) ------------------------------
  // Browser checks are a courtesy, not a verdict: no signature is read here
  // and nothing the client accepts is final until the server confirms the
  // whole task. The checks use ONLY the rendered configuration.

  function extOf(name) {
    var i = (name || '').lastIndexOf('.');
    return i > 0 ? name.slice(i).toLowerCase() : '';
  }

  function allowedList() {
    return cfg.allowed.map(function (e) {
      return e.replace('.', '').toUpperCase();
    }).join(', ');
  }

  function preValidate(kind, file) {
    if (!categoryLabels[kind]) {
      return {code: 'REFERENCE_CATEGORY_INVALID',
              message: 'This reference category is not valid.'};
    }
    if (!file.size) {
      return {code: 'REFERENCE_FILE_EMPTY',
              message: 'This file is empty and was not added.'};
    }
    var ext = extOf(file.name);
    if (!ext || cfg.allowed.indexOf(ext) === -1) {
      return {code: 'REFERENCE_EXTENSION_NOT_ALLOWED',
              message: 'This file type is not supported. Use ' +
                       allowedList() + '.'};
    }
    if (cfg.maxBytes && file.size > cfg.maxBytes) {
      return {code: 'REFERENCE_FILE_TOO_LARGE',
              message: 'This file exceeds the configured ' + cfg.maxMb +
                       ' MB per-file limit and was not added.'};
    }
    return null;
  }

  // Owner-facing wording for the authoritative server verdicts (B4b-2B §9).
  // Codes the map does not know fall back to the server's own message.
  var SERVER_MESSAGES = {
    REFERENCE_FILE_TOO_LARGE: function () {
      return 'This file exceeds the ' + cfg.maxMb + ' MB per-file limit.';
    },
    REFERENCE_EXTENSION_NOT_ALLOWED: function () {
      return 'This file type is not supported. Use ' + allowedList() + '.';
    },
    REFERENCE_SIGNATURE_INVALID: function () {
      return 'The file content could not be recognized as the selected ' +
             'format.';
    },
    REFERENCE_EXTENSION_TYPE_MISMATCH: function () {
      return 'The filename extension does not match the detected file ' +
             'content.';
    },
    REFERENCE_FILENAME_INVALID: function () {
      return 'The filename could not be accepted safely. Rename the file, ' +
             'remove this entry and select it again.';
    },
    REFERENCE_CATEGORY_INVALID: function () {
      return 'This reference category is not valid.';
    },
    REFERENCE_STORAGE_FAILED: function () {
      return 'The reference could not be stored. No task was created. ' +
             'Try again.';
    },
  };

  function serverMessage(err) {
    var known = SERVER_MESSAGES[err.code];
    return known ? known() : (err.message || 'This file was rejected.');
  }

  // ---- error rendering ----------------------------------------------------

  function buildErrorRow(err, dismissable) {
    var row = document.createElement('div');
    row.className = 'ref-error-row';
    row.setAttribute('tabindex', '-1');
    row.setAttribute('role', 'alert');

    var badge = document.createElement('span');
    badge.className = 'ref-error-badge';
    badge.textContent = 'NOT ADDED';
    row.appendChild(badge);

    var what = document.createElement('span');
    what.className = 'ref-error-what';
    what.textContent = err.filename
      ? err.filename + ' — ' + (categoryLabels[err.category] || err.category)
      : (categoryLabels[err.category] || err.category || 'References');
    what.title = err.filename || '';
    row.appendChild(what);

    var msg = document.createElement('span');
    msg.className = 'ref-error-msg';
    msg.textContent = err.message;
    row.appendChild(msg);

    if (dismissable) {
      var dismiss = document.createElement('button');
      dismiss.type = 'button';
      dismiss.className = 'ref-error-dismiss';
      dismiss.textContent = '×';
      dismiss.setAttribute('aria-label', 'Dismiss error for ' +
                           (err.filename || 'references'));
      dismiss.addEventListener('click', function () {
        var i = clientErrors.indexOf(err);
        if (i !== -1) clientErrors.splice(i, 1);
        renderErrors();
      });
      row.appendChild(dismiss);
    }
    return row;
  }

  function renderErrors() {
    if (!errorsEl) return;
    errorsEl.textContent = '';
    var rejectedCards = Object.keys(cardErrors).length;
    if (generalError) {
      var g = document.createElement('div');
      g.className = 'ref-error-row ref-error-general';
      g.setAttribute('tabindex', '-1');
      g.setAttribute('role', 'alert');
      g.textContent = generalError.message;
      errorsEl.appendChild(g);
    }
    if (rejectedCards) {
      var s = document.createElement('div');
      s.className = 'ref-error-row ref-error-summary';
      s.setAttribute('tabindex', '-1');
      s.setAttribute('role', 'alert');
      s.textContent = rejectedCards + ' staged file' +
        (rejectedCards === 1 ? ' was' : 's were') +
        ' rejected by validation. No task was created — remove or replace ' +
        'the marked files below. They are still staged in your browser.';
      errorsEl.appendChild(s);
    }
    clientErrors.forEach(function (err) {
      errorsEl.appendChild(buildErrorRow(err, true));
    });
  }

  function focusFirstError() {
    // a rejected STAGED card's remove control first (the actionable fix),
    // then the first error row, per B4b-2B §13
    var ids = Object.keys(cardErrors);
    if (ids.length) {
      var card = section.querySelector(
        '.ref-card[data-ref-id="' + ids[0] + '"] .ref-card-remove');
      if (card) { card.focus(); return true; }
    }
    var row = errorsEl && errorsEl.querySelector('.ref-error-row');
    if (row) { row.focus(); return true; }
    return false;
  }

  // ---- card rendering (createElement + textContent only — filenames are
  //      user input and must never travel through innerHTML) ---------------

  function buildCard(entry) {
    var card = document.createElement('div');
    card.className = 'ref-card';
    card.dataset.refId = entry.id;

    if (entry.previewKind === 'raster') {
      var img = document.createElement('img');
      img.className = 'ref-card-thumb';
      img.src = entry.objectUrl;
      img.alt = entry.name;
      card.appendChild(img);
    } else {
      // neutral document card: the extension, plainly, never an <img>
      var doc = document.createElement('span');
      doc.className = 'ref-card-doc';
      doc.textContent = entry.ext.replace('.', '').toUpperCase();
      doc.setAttribute('aria-hidden', 'true');
      card.appendChild(doc);
    }

    var meta = document.createElement('span');
    meta.className = 'ref-card-meta';

    var name = document.createElement('span');
    name.className = 'ref-card-name';
    name.textContent = entry.name;
    name.title = entry.name;               // the complete name, always
    meta.appendChild(name);

    var detail = document.createElement('span');
    detail.className = 'ref-card-detail';
    detail.textContent = entry.categoryLabel + ' · ' +
      (entry.mime || entry.ext.replace('.', '').toUpperCase()) + ' · ' +
      humanSize(entry.size);
    meta.appendChild(detail);

    var badge = document.createElement('span');
    badge.className = 'ref-card-badge';
    badge.textContent = entry.referenceOnly;
    meta.appendChild(badge);

    // server-error state (B4b-2B §7): the file stays staged, previewed and
    // removable — the card wears the verdict, it does not vanish
    var verdict = cardErrors[entry.id];
    if (verdict) {
      card.classList.add('server-error');
      var errEl = document.createElement('span');
      errEl.className = 'ref-card-error';
      errEl.setAttribute('role', 'alert');
      errEl.textContent = 'REJECTED — ' + verdict.message;
      meta.appendChild(errEl);
    }

    card.appendChild(meta);

    var remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'ref-card-remove';
    remove.textContent = '×';
    remove.setAttribute('aria-label', 'Remove ' + entry.name + ' from ' +
                        entry.categoryLabel);
    remove.disabled = controller.isSubmitting();
    remove.addEventListener('click', function () {
      if (controller.isSubmitting()) return;
      var r = controller.remove(entry.id);
      if (r.removed) {
        delete cardErrors[entry.id];   // removal clears the verdict with it
        rerender();
        renderErrors();
        announce('Removed ' + entry.name + '.');
      }
    });
    card.appendChild(remove);
    return card;
  }

  function rerender() {
    if (!section || !controller) return;
    var byKind = {};
    var live = {};
    controller.list().forEach(function (e) {
      (byKind[e.category] = byKind[e.category] || []).push(e);
      live[e.id] = true;
    });
    // a verdict belongs to its entry — when the entry is gone (removed
    // through ANY path), the verdict and its summary row go with it
    Object.keys(cardErrors).forEach(function (id) {
      if (!live[id]) delete cardErrors[id];
    });
    section.querySelectorAll('.ref-cards').forEach(function (host) {
      var kind = host.dataset.kind;
      host.textContent = '';
      (byKind[kind] || []).forEach(function (e) {
        host.appendChild(buildCard(e));
      });
      host.closest('.ref-category')
          .classList.toggle('populated', !!(byKind[kind] || []).length);
    });
    renderHeldNotice();
  }

  // ---- held-reference notice (B4b-2C §3) -----------------------------------
  // Shown only while another target is selected AND canonical entries exist.
  // The count is read from the controller alone — never from DOM cards,
  // inputs or error rows (preliminary refusals own no entry, so they can
  // never inflate it).

  function focusReferences() {
    var first = section && section.querySelector('.ref-card .ref-card-remove');
    if (first) { first.focus(); return; }
    var legend = section && section.querySelector('legend');
    if (legend) {
      legend.setAttribute('tabindex', '-1');
      legend.focus();
    }
  }

  function returnToProductContainer() {
    var chip = document.querySelector(
      '.target-chip[data-target="product_container"]');
    if (chip) chip.click();   // poll.js owns the switch; this just requests it
    focusReferences();
  }

  function renderHeldNotice() {
    if (!heldNoticeEl || !controller) return;
    var n = controller.count();
    if (containerVisible || n === 0) {
      heldNoticeEl.hidden = true;
      heldNoticeEl.textContent = '';
      return;
    }
    heldNoticeEl.textContent = '';
    var msg = document.createElement('span');
    msg.className = 'ref-held-msg';
    msg.textContent = n + ' Product Container reference file' +
      (n === 1 ? ' is' : 's are') + ' being held. ' +
      (n === 1 ? 'It' : 'They') + ' will not be attached to this ' +
      'Packaging task.';
    heldNoticeEl.appendChild(msg);
    if (Object.keys(cardErrors).length) {
      var warn = document.createElement('span');
      warn.className = 'ref-held-correction';
      warn.textContent = ' Some held files were rejected by validation and ' +
        'need correction.';
      heldNoticeEl.appendChild(warn);
    }
    var back = document.createElement('button');
    back.type = 'button';
    back.className = 'ref-held-return';
    back.textContent = 'Return to Product Container';
    back.addEventListener('click', returnToProductContainer);
    heldNoticeEl.appendChild(back);
    heldNoticeEl.hidden = false;
  }

  // ---- staging ------------------------------------------------------------

  function addFrom(kind, files) {
    if (!files || !files.length) return;
    // partition: valid siblings stage locally, refused files become error
    // rows — a bad neighbour must not block a good file from STAGING (the
    // server still applies its all-or-nothing rule at submission)
    var valid = [], refused = [];
    Array.prototype.forEach.call(files, function (file) {
      var bad = preValidate(kind, file);
      if (bad) {
        refused.push({code: bad.code, message: bad.message,
                      filename: file.name, category: kind});
      } else {
        valid.push(file);
      }
    });

    if (valid.length) {
      var r = controller.addFiles(kind, valid);
      if (!r.ok) {
        announce(r.error === 'SUBMITTING'
          ? 'Files cannot be changed while the task is being created.'
          : 'Those files could not be staged (' + r.error + ').');
        return;
      }
      rerender();
    }
    if (refused.length) {
      refused.forEach(function (e) { clientErrors.push(e); });
      renderErrors();
      announce((valid.length
                 ? 'Added ' + valid.length + ' file' +
                   (valid.length === 1 ? '' : 's') + ' to ' +
                   (categoryLabels[kind] || kind) + '. '
                 : '') +
               refused.length + ' file' +
               (refused.length === 1 ? ' was' : 's were') +
               ' not added: ' + refused[0].message);
      focusFirstError();
    } else if (valid.length) {
      announce('Added ' + valid.length + ' file' +
               (valid.length === 1 ? '' : 's') + ' to ' +
               (categoryLabels[kind] || kind) + '.');
    }
  }

  function bindCategory(block) {
    var kind = block.dataset.kind;
    var input = block.querySelector('input.ref-input');
    var zone = block.querySelector('.ref-zone');
    var dropText = zone.querySelector('.ref-zone-drop');

    input.addEventListener('change', function () {
      addFrom(kind, input.files);
      // the input is a picker, not state: clearing it lets the same file be
      // chosen again and leaves the canonical inventory as the only record
      input.value = '';
    });

    function setActive(on) {
      zone.classList.toggle('drag-active', on);
      // state change in text as well as colour
      dropText.textContent = on ? 'Release to add files'
                                : dropText.dataset.idle;
    }
    zone.addEventListener('dragover', function (ev) {
      ev.preventDefault();
      setActive(true);
    });
    zone.addEventListener('dragenter', function (ev) {
      ev.preventDefault();
      setActive(true);
    });
    zone.addEventListener('dragleave', function () { setActive(false); });
    zone.addEventListener('dragend', function () { setActive(false); });
    zone.addEventListener('drop', function (ev) {
      ev.preventDefault();
      setActive(false);
      if (controller.isSubmitting()) return;
      if (ev.dataTransfer && ev.dataTransfer.files) {
        addFrom(kind, ev.dataTransfer.files);
      }
    });
  }

  // ---- init ---------------------------------------------------------------

  function init() {
    section = document.getElementById('reference-section');
    if (!section || !window.DesignOSStagedReferences) return;
    liveEl = document.getElementById('ref-live');

    var cfgEl = document.getElementById('reference-config');
    var catEl = document.getElementById('reference-categories');
    if (!cfgEl || !catEl) return;
    errorsEl = document.getElementById('ref-errors');
    heldNoticeEl = document.getElementById('ref-held-notice');
    // initial target from the server-rendered active chip; poll.js keeps it
    // current from here on via setTargetVisibility
    var activeChip = document.querySelector('.target-chip.active');
    containerVisible = !activeChip ||
      activeChip.dataset.target === 'product_container';
    var categories = JSON.parse(catEl.textContent);
    categories.forEach(function (c) { categoryLabels[c.key] = c.label; });
    // one limit, one allowlist — both rendered by the server (§3)
    cfg.maxBytes = parseInt(cfgEl.dataset.maxBytes, 10) || 0;
    cfg.maxMb = cfgEl.dataset.maxMb || '';
    cfg.allowed = (cfgEl.dataset.allowed || '').split(',')
      .filter(function (e) { return e; });

    var inventory = window.DesignOSStagedReferences.create({
      categories: categories,
      previewableExtensions: (cfgEl.dataset.previewable || '').split(','),
      referenceOnlyLabel: 'REFERENCE ONLY',
    });
    // B4b-2C: every count mutation must repaint cards, errors and the held
    // notice no matter where it came from — this module's own handlers or a
    // direct call through the public handle. The decorated view delegates
    // state to the pure inventory and adds only the repaint.
    controller = Object.create(inventory);
    ['addFiles', 'remove', 'clear'].forEach(function (m) {
      controller[m] = function () {
        var result = inventory[m].apply(inventory, arguments);
        rerender();
        renderErrors();
        return result;
      };
    });

    section.querySelectorAll('.ref-category').forEach(bindCategory);

    // The narrow public handle poll.js submits through (2A-3).
    window.DesignOSReferenceUI = {
      controller: controller,
      list: function () { return controller.list(); },
      count: function () { return controller.count(); },
      appendToFormData: function (fd) {
        return controller.appendToFormData(fd);
      },
      setSubmitting: function (b) {
        controller.setSubmitting(b);
        section.classList.toggle('is-submitting', !!b);
        section.querySelectorAll('input.ref-input, .ref-card-remove')
          .forEach(function (el) { el.disabled = !!b; });
      },
      clearAfterSuccess: function () {
        controller.clear({confirmedSuccess: true});
        section.querySelectorAll('input.ref-input')
          .forEach(function (i) { i.value = ''; });
        clientErrors = [];
        cardErrors = {};
        generalError = null;
        rerender();
        renderErrors();
        announce('References cleared after successful submission.');
      },

      // ---- error API (B4b-2B §16) — poll.js interprets responses and hands
      //      the verdicts here; this module owns their presentation ---------

      clearErrors: function () {
        clientErrors = [];
        cardErrors = {};
        generalError = null;
        rerender();
        renderErrors();
      },

      showClientErrors: function (errors) {
        (errors || []).forEach(function (e) { clientErrors.push(e); });
        renderErrors();
        announce('Some files were not added.');
      },

      /** Server verdicts, correlated by category + request-local file_index —
       *  never by filename, which duplicates make ambiguous (§10). */
      showServerErrors: function (errors) {
        var byCat = {};
        controller.list().forEach(function (e) {
          (byCat[e.category] = byCat[e.category] || []).push(e);
        });
        var matched = 0;
        (errors || []).forEach(function (err) {
          var entry = (byCat[err.category] || [])[err.file_index];
          if (entry) {
            cardErrors[entry.id] = {code: err.code,
                                    message: serverMessage(err)};
            matched++;
          } else {
            clientErrors.push({code: err.code, message: serverMessage(err),
                               filename: err.filename || '',
                               category: err.category || ''});
          }
        });
        rerender();
        renderErrors();
        announce(matched
          ? 'The task was not created: ' + matched + ' staged file' +
            (matched === 1 ? ' was' : 's were') + ' rejected. The files ' +
            'are still staged — remove or replace the marked ones.'
          : 'The task was not created because reference validation failed.');
        // poll.js calls this before its finally block releases the submit
        // lock, so the remove buttons are still disabled — and a disabled
        // element cannot take focus. Defer one tick, past the release.
        setTimeout(focusFirstError, 0);
      },

      showGeneralError: function (code, message) {
        generalError = {code: code, message: message};
        renderErrors();
        announce(message);
        focusFirstError();
      },

      focusFirstError: focusFirstError,

      // ---- target switching (B4b-2C §2/§3) — poll.js reports which target
      //      is visible; the inventory itself is never touched by a switch --

      setTargetVisibility: function (isContainer) {
        containerVisible = !!isContainer;
        renderHeldNotice();
      },

      returnToProductContainer: returnToProductContainer,
    };

    window.addEventListener('beforeunload', function () {
      controller.dispose();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
