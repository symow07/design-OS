"""High-confidence brief conflicts, checked before creation or any paid work."""
import re


def target_conflict(target, brief):
    text = str(brief or '').lower()
    tabletop = re.search(r'\b(?:countertop|tabletop|counter-top|table-top)\b.{0,45}\b(?:stand|display)\b', text)
    booth = re.search(r'\b(?:exhibition|trade[- ]?show)\s+booth\b|\bbooth\s+(?:design|footprint)\b', text)
    graphics = bool(re.search(r'\bgraphics[- ]only\b|\bartwork only\b', text))
    if target == 'exhibition_booth' and tabletop and not booth:
        return {'error': 'TARGET_BRIEF_CONFLICT', 'words': 'This brief asks for a countertop display. Choose Display; Booth graphics supplies wall and counter artwork only.', 'suggested_target': 'display_stand'}
    if target == 'display_stand' and booth and not tabletop:
        return {'error': 'TARGET_BRIEF_CONFLICT', 'words': 'This brief asks for a booth. Booth graphics supplies artwork only; spatial planning and construction are outside this release.', 'suggested_target': 'exhibition_booth'}
    structural = re.search(r'\b(?:floor[- ](?:standing|stand)|tester stand|floor plan|circulation|load[- ]bearing|storage|stepped|steps|holes|tiers)\b', text)
    if target in ('display_stand', 'exhibition_booth') and structural and not graphics:
        return {'error': 'CONSTRUCTION_UNRESOLVED', 'words': 'This request needs a physical assembly that is not ready yet. The current target supplies graphics only. Your dimensions must be resolved before starting; no images have been purchased.'}
    return None


def read_intake(value):
    import json
    if isinstance(value, str):
        value = json.loads(value)
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError('Measurements and required content must be an object.')
    keys = ('dimensions', 'count', 'material', 'method', 'languages', 'copy')
    if any(k not in keys or not isinstance(v, str) or len(v) > 10000 for k, v in value.items()):
        raise ValueError('Each measurement or copy field must be text, at most 10,000 characters.')
    return {'schema_version': 'rescue_intake/1.0', 'fields': value,
            'unresolved': [k for k in keys if not value.get(k, '').strip()]}
