"""Claim an owner width amendment without replacing an execution or paid claim."""
from copy import deepcopy
from pathlib import Path

from . import round_flow as flow
from .round_calls import sha
from .round_files_job import digest, read


OWNER_ANSWER = 'Match the pictured widths; keep ≥90% pixel coverage'
UNCHANGED_LIMITS = {'budget_usd': 4, 'maximum_image_calls': 2,
                    'maximum_eye_looks': 2, 'maximum_repairs': 1}


def policy():
    return read(flow.REPO/'docs/rounds/files-build-policy.json')


def _pinned(path, expected):
    if (not isinstance(expected, str) or len(expected) != 64 or
            not path.is_file() or sha(path) != expected):
        raise ValueError('The owner width amendment no longer matches its retained input: '+path.name)


def claim_width_rule(ctx):
    """Return fixed mode, or claim/replay pictured widths on a later owner Retry.

    This writes only attempts/2/width-rule.json. Existing image responses,
    reservations, original execution authority and its claim remain untouched.
    """
    root = Path(ctx.root).resolve()
    base = root/'attempts/2'
    destination = base/'width-rule.json'
    rules = policy()
    approved = rules.get('width_amendments', {}).get(ctx.build.round.slug)
    if approved is None:
        if destination.exists():
            raise ValueError('The claimed pictured-width authority was removed.')
        return {'mode': 'fixed'}
    if not isinstance(approved, dict):
        raise ValueError('The width amendment must be a pinned owner record.')
    fixed = {'schema': 'owner_files_width_amendment/1', 'attempt': 2,
             'mode': 'pictured', 'minimum_pixel_coverage': .9,
             'owner_answer': OWNER_ANSWER, 'additional_budget_usd': 0,
             'additional_image_calls': 0, 'additional_eye_looks': 0,
             'additional_repairs': 0}
    if (any(approved.get(key) != value for key, value in fixed.items()) or
            any(type(approved.get(key)) is not int for key in
                ('attempt', 'source_retry_attempt', 'additional_budget_usd', 'additional_image_calls',
                 'additional_eye_looks', 'additional_repairs')) or
            approved['source_retry_attempt'] < 0 or
            approved.get('picture_sha256') != ctx.build.inputs['picture_sha256']):
        raise ValueError('Only the exact owner pictured-width choice, 90% coverage and unchanged limits are authorized.')
    claim_path = base/'claim.json'
    _pinned(root/'source.png', approved['picture_sha256'])
    _pinned(claim_path, approved.get('attempt_claim_sha256'))
    original = read(claim_path)
    execution = rules.get('execution_attempts', {}).get(ctx.build.round.slug)
    if (not isinstance(execution, dict) or original.get('authority') != execution or
            execution.get('attempt') != 2 or
            execution.get('picture_sha256') != approved['picture_sha256'] or
            any(type(execution.get(key)) is not int or execution.get(key) != value
                for key, value in UNCHANGED_LIMITS.items()) or
            type(original.get('owner_retry_attempt')) is not int or
            approved['source_retry_attempt'] < original['owner_retry_attempt']):
        raise ValueError('The original execution claim and its limits must remain unchanged.')
    failed_relative = approved.get('failed_fit_path')
    if not isinstance(failed_relative, str):
        raise ValueError('The width amendment needs the saved failed line-fit path.')
    failed = (root/failed_relative).resolve()
    if (not failed.is_relative_to(base.resolve()) or failed.name != 'line-fit.json' or
            str(failed.relative_to(root)) != failed_relative):
        raise ValueError('The failed line fit must belong to this execution attempt.')
    _pinned(failed, approved.get('failed_fit_sha256'))
    failure = read(failed)
    if failure.get('passed') is not False or failure.get('minimum_coverage') != .9:
        raise ValueError('The width amendment must retain the failed 90% pixel-coverage report.')
    owner_retry = ctx.build.steps['eye']['attempts']
    if type(owner_retry) is not int or owner_retry <= approved['source_retry_attempt']:
        raise ValueError('The pictured-width amendment requires the owner’s new app Retry.')
    expected = {'schema': 'files_width_rule/1', 'mode': 'pictured',
        'minimum_pixel_coverage': .9, 'owner_answer': OWNER_ANSWER,
        'authority': deepcopy(approved), 'authority_sha256': digest(approved),
        'execution_limits': deepcopy(UNCHANGED_LIMITS),
        'pins': {'source.png': approved['picture_sha256'],
                 'attempts/2/claim.json': approved['attempt_claim_sha256'],
                 failed_relative: approved['failed_fit_sha256']}}
    if destination.exists():
        retained = read(destination)
        claimed_retry = retained.get('owner_retry_attempt')
        if (type(claimed_retry) is not int or
                not approved['source_retry_attempt'] < claimed_retry <= owner_retry or
                retained != dict(expected, owner_retry_attempt=claimed_retry)):
            raise ValueError('The retained pictured-width claim changed; no authority or paid-cache reset.')
        return retained
    if (base/'bundle.json').exists() or (base/'review').exists():
        raise ValueError('A new width rule cannot be claimed after attempt output or review exists.')
    result = dict(expected, owner_retry_attempt=owner_retry)
    flow.write_json(destination, result)
    return result
