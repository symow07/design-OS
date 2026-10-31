/* staged_references.js — B4b-2A-1: the canonical staged-file inventory.
 *
 * One place in the browser knows which reference files are selected. The
 * file inputs, the cards (2A-2) and the multipart payload (2A-3) will all
 * read THIS inventory, so they cannot drift into three different file lists —
 * which is the failure mode the B4b briefs keep circling.
 *
 * Deliberately pure: no DOM, no fetch, no template knowledge. Configuration
 * (category keys, labels, previewable extensions, the server field mapping)
 * arrives from the caller — production code will parse #reference-config
 * once and pass it in; tests pass it directly. The module never carries a
 * second copy of the allowlist or the size limit.
 *
 * The File object is the authoritative binary source. Nothing here copies
 * bytes into base64/JSON/storage, parses file contents, renders a PDF, or
 * touches the network. Server signature validation stays authoritative.
 *
 * Classic script, like every other module in static/js — no build system.
 */
(function () {
  'use strict';

  function normaliseExt(name) {
    var i = (name || '').lastIndexOf('.');
    return i > 0 ? name.slice(i).toLowerCase() : '';
  }

  /**
   * DesignOSStagedReferences.create(options) -> inventory
   *
   * options:
   *   categories            [{key, label}, ...]   required; the five
   *                         persisted keys (container/logo/label/
   *                         inspiration/color — the KEY is 'color')
   *   previewableExtensions ['.png', ...]         extensions that get a local
   *                         object URL; everything else is a file-card
   *   serverFields          {category: fieldName} optional; default is the
   *                         existing contract, field name == category key
   *   referenceOnlyLabel    string                badge text for snapshots
   *   urlApi                {create, revoke}      injectable URL API — the
   *                         test seam for the object-URL lifecycle
   */
  function create(options) {
    var opts = options || {};
    var categories = {};
    (opts.categories || []).forEach(function (c) { categories[c.key] = c; });
    if (!Object.keys(categories).length) {
      throw new Error('StagedReferences: categories configuration is required');
    }
    var previewable = (opts.previewableExtensions || [])
      .map(function (e) { return String(e).toLowerCase(); });
    var serverFields = opts.serverFields || null;
    var urlApi = opts.urlApi || {
      create: function (f) { return URL.createObjectURL(f); },
      revoke: function (u) { URL.revokeObjectURL(u); },
    };
    var badge = opts.referenceOnlyLabel || 'REFERENCE ONLY';

    var entries = [];
    var nextId = 1;      // ids are never reused, even after removal
    var nextOrder = 0;   // insertion order is monotonic and never renumbered
    var submitting = false;
    var disposed = false;

    function fieldFor(category) {
      return serverFields ? (serverFields[category] || category) : category;
    }

    // External code gets frozen copies. The internal array is the single
    // authority for mutation and is never handed out.
    function snapshot(e) {
      return Object.freeze({
        id: e.id,
        file: e.file,
        category: e.category,
        categoryLabel: (categories[e.category] || {}).label || e.category,
        name: e.name,
        mime: e.mime,
        size: e.size,
        ext: e.ext,
        previewKind: e.previewKind,
        objectUrl: e.objectUrl,
        order: e.order,
        referenceOnly: badge,
      });
    }

    // Nulling after revoke is what makes repeated clear()/dispose() unable
    // to revoke the same URL twice.
    function revokeEntry(e) {
      if (e.objectUrl) {
        urlApi.revoke(e.objectUrl);
        e.objectUrl = null;
      }
    }

    function revokeAll() { entries.forEach(revokeEntry); }

    return {
      /** Stage files under an explicit category. All-or-nothing per call is
       *  NOT needed here — validation UX belongs to B4b-2B; the server stays
       *  authoritative regardless. */
      addFiles: function (category, files) {
        if (disposed) return { ok: false, error: 'DISPOSED', entries: [] };
        if (submitting) return { ok: false, error: 'SUBMITTING', entries: [] };
        if (!categories[category]) {
          return { ok: false, error: 'UNKNOWN_CATEGORY', entries: [] };
        }
        var added = [];
        Array.prototype.forEach.call(files || [], function (file) {
          var ext = normaliseExt(file.name);
          var raster = previewable.indexOf(ext) !== -1;
          var entry = {
            id: 'ref-' + (nextId++),
            file: file,                    // authoritative binary; not copied
            category: category,
            name: file.name,
            mime: file.type || '',
            size: file.size,
            ext: ext,
            previewKind: raster ? 'raster' : 'file-card',
            // one URL per previewable entry; documents never get one, so a
            // PDF can never end up behind an <img>
            objectUrl: raster ? urlApi.create(file) : null,
            order: nextOrder++,
          };
          entries.push(entry);
          added.push(snapshot(entry));
        });
        return { ok: true, entries: added };
      },

      /** Remove exactly one entry by id. Duplicates by filename survive —
       *  identity is the id, never the name. */
      remove: function (id) {
        if (disposed) return { ok: false, removed: false, error: 'DISPOSED' };
        if (submitting) {
          return { ok: false, removed: false, error: 'SUBMITTING' };
        }
        for (var i = 0; i < entries.length; i++) {
          if (entries[i].id === id) {
            revokeEntry(entries[i]);
            entries.splice(i, 1);
            return { ok: true, removed: true };
          }
        }
        return { ok: true, removed: false };
      },

      list: function () { return entries.map(snapshot); },

      get: function (id) {
        for (var i = 0; i < entries.length; i++) {
          if (entries[i].id === id) return snapshot(entries[i]);
        }
        return null;
      },

      count: function () { return entries.length; },

      /** Ordinary clear refuses during submission; the confirmed-success
       *  cleanup path (2A-3 will call this after the server confirms the
       *  task) passes {confirmedSuccess: true} and is allowed through. */
      clear: function (o) {
        if (submitting && !(o && o.confirmedSuccess)) {
          return { ok: false, error: 'SUBMITTING' };
        }
        revokeAll();
        entries = [];
        return { ok: true };
      },

      /** Append every staged File to the given FormData, exactly once, in
       *  insertion order, under the existing server field contract. Appends
       *  nothing else — no ids, no urls, no metadata — and never submits. */
      appendToFormData: function (formData) {
        entries.forEach(function (e) {
          formData.append(fieldFor(e.category), e.file, e.name);
        });
        return entries.length;
      },

      setSubmitting: function (b) { submitting = !!b; },
      isSubmitting: function () { return submitting; },

      /** Teardown. Always allowed (it is the unload path), idempotent, and
       *  cannot double-revoke because revoked URLs are nulled. */
      dispose: function () {
        revokeAll();
        entries = [];
        disposed = true;
        return { ok: true };
      },
    };
  }

  window.DesignOSStagedReferences = { create: create };
})();
