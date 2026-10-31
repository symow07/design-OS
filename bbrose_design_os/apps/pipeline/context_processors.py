"""Template context: the frontend build actually being served (2A-6E-CORR-3).

The regeneration-click incident chain ended at a browser running a stale
gates.js — invisible, because nothing on the page said which build the
browser had loaded and the asset URL never changed between commits. Every
dashboard render now carries the SERVED process revision (current_revision
is resolved once per process — the running code, never repository HEAD
queried separately): it stamps a visible build line, seeds
window.__BBROSE_FRONTEND_BUILD__, and cache-busts every static asset URL so
a new commit is a new URL — hard refresh is not a deployment strategy.
"""
from apps.pipeline.services.revision import current_revision


def frontend_build(request):
    return {"FRONTEND_BUILD": current_revision()}
