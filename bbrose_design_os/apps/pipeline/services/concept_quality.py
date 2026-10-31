"""Owner's rescue quality policy. Computed verdicts, never model-owned passes."""
from __future__ import annotations

import hashlib
import json
import math

SCHEMA = 'concept_quality/1.0'
DIMENSIONS = ('colour_contrast', 'focal_hierarchy', 'negative_space',
              'pattern_support', 'typography', 'shelf_impact', 'premium_cues',
              'distinctiveness', 'trend_relevance', 'beauty')
CRITICAL = ('colour_contrast', 'focal_hierarchy', 'typography', 'shelf_impact', 'beauty')
PASS_SCORE = 8


def pending(reason):
    return {'schema_version': SCHEMA, 'review_status': 'review_pending',
            'passed': False, 'score': None, 'dimensions': {}, 'hard_failures': [],
            'observations': '', 'issues': [reason], 'recommendation': 'review pending'}


def evaluate(payload):
    """Invalid/missing evidence stays pending; numeric thresholds cannot be overridden."""
    if not isinstance(payload, dict):
        return pending('Vision review unavailable or invalid — review pending.')
    dimensions = payload.get('dimensions')
    hard = payload.get('hard_failures')
    if not isinstance(dimensions, dict) or not isinstance(hard, list) or any(not isinstance(x, str) for x in hard):
        return pending('The critic did not return a complete review — review pending.')
    scores, issues = {}, []
    for name in DIMENSIONS:
        row = dimensions.get(name)
        if not isinstance(row, dict):
            return pending(f'The critic did not review {name} — review pending.')
        score = row.get('score')
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 1 <= score <= 10 or not math.isfinite(score):
            return pending(f'The critic returned an invalid {name} score — review pending.')
        if any(not isinstance(row.get(k), str) or not row[k].strip() for k in ('observation', 'location')):
            return pending(f'The critic supplied no visual evidence for {name} — review pending.')
        if score < PASS_SCORE:
            if not isinstance(row.get('repair'), str) or not row['repair'].strip():
                return pending(f'The critic supplied no repair for {name} — review pending.')
            issues.append(f"{name}: {row['observation']} ({row['location']}). {row['repair']}")
        scores[name] = float(score)
    mean = sum(scores.values()) / len(DIMENSIONS)
    passed = mean >= PASS_SCORE and all(scores[k] >= 7 for k in CRITICAL) and not hard
    return {'schema_version': SCHEMA, 'review_status': 'accepted' if passed else 'rejected',
            'passed': passed, 'score': round(mean, 2), 'dimensions': dimensions,
            'hard_failures': hard, 'observations': str(payload.get('observations') or ''),
            'issues': hard + issues, 'recommendation': 'approve' if passed else 'designer review'}


def image_sha256(image):
    try:
        with image.image_file.open('rb') as source:
            h = hashlib.sha256()
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                h.update(chunk)
            return h.hexdigest()
    except (OSError, ValueError, AttributeError):
        return None


def image_verdict(image, *, verify_pixels=True):
    try:
        raw = json.loads(image.qa_notes or '{}')
    except (ValueError, TypeError, AttributeError):
        raw = {}
    if not isinstance(raw, dict) or raw.get('schema_version') != SCHEMA:
        return pending('This concept has no review against the current quality bar.')
    verdict = evaluate(raw)
    digest = raw.get('image_sha256')
    if not digest or (verify_pixels and image_sha256(image) != digest):
        return pending('The image has changed or is unavailable; it needs a new review.')
    if raw.get('review_status') == 'review_pending':
        return pending('; '.join(str(x) for x in (raw.get('issues') or ['Review pending.'])))
    return verdict


def summary(images):
    from .gate1_review import image_is_selectable
    rows = list(images)
    counts = {'accepted': 0, 'rejected': 0, 'review_pending': 0}
    for image in rows:
        verdict = image_verdict(image)
        state = verdict['review_status']
        if state == 'accepted' and not image_is_selectable(image, verify_pixels=True):
            state = 'rejected'
        counts[state] += 1
    state = 'ready' if counts['accepted'] else 'review_pending' if counts['review_pending'] else 'designer_review'
    words = {'ready': f"{counts['accepted']} concept(s) meet the quality bar.",
             'review_pending': 'Review pending — no unchecked concept can be approved.',
             'designer_review': 'Designer review needed — no concept meets the quality bar.'}
    return {'schema_version': SCHEMA, 'status': state, 'counts': counts, 'message': words[state]}


def repair_rounds_used(task):
    """Historical manual attempts remain consumed after rescue deployment."""
    return max(int((task.options or {}).get('rescue_repair_rounds', 0)), task.image_rerun_count)


def repair_state(task):
    """The same allowance for automatic repairs and explicit revision controls."""
    from django.conf import settings
    options = task.options or {}
    used = repair_rounds_used(task)
    remaining = max(0, min(2, settings.MAX_REVISION_PASSES) - used)
    blocked = bool(options.get('rescue_repair_inflight') or options.get('rescue_reference_review_required'))
    pending = bool(options.get('rescue_repair_pending'))
    reason = ('A saved paid attempt needs reconciliation before another revision.' if blocked else
              'Resume the saved repair before requesting different changes.' if pending else
              'The two-round repair allowance is used. Choose an accepted concept or request designer review.' if not remaining else '')
    return {'remaining': remaining, 'pending': pending, 'can_resume': pending and not blocked,
            'can_revise': bool(remaining) and not pending and not blocked, 'reason': reason}
