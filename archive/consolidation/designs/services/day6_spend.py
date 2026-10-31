"""Day 6 spend record from the reservation ledger: critic calls only, inside the owner's 10 USD allowance."""
from pathlib import Path
import json
from .spend_reservation import _connect, totals
from . import fidelity_assets as fa

ROOT = fa.ROOT / 'docs/audit/day-6'
DAY = '2026-10-19'
PREFIX = 'day6/'


def usd(micro):
    return round(micro / 1_000_000, 6)


def build():
    with _connect() as db:
        rows = [dict(r) for r in db.execute('SELECT * FROM calls WHERE day=? ORDER BY started_at', (DAY,))]
    mine = [r for r in rows if r['operation'].startswith(PREFIX)]
    other = [r for r in rows if not r['operation'].startswith(PREFIX)]
    calls = []
    for r in mine:
        calls.append({k: r[k] for k in ('id', 'day', 'provider', 'operation', 'model', 'state', 'started_at', 'settled_at')}
                     | {'reserved_usd': usd(r['reserved']), 'accounted_usd': usd(r['accounted']),
                        'usage': json.loads(r['usage']) if r['usage'] else None})
    record = {'date': DAY, 'timezone': 'Asia/Shanghai', 'status': 'Day 6: critic calls only; no image generation; invoice reconciliation pending',
              'day6_allowance_usd': 10, 'day6_calls': len(mine), 'day6_reserved_usd': usd(sum(r['reserved'] for r in mine)),
              'day6_accounted_usd': usd(sum(r['accounted'] for r in mine)),
              'same_day_day5_calls': len(other), 'same_day_day5_accounted_usd': usd(sum(r['accounted'] for r in other)),
              'shanghai_day_accounted_usd': usd(sum(r['accounted'] for r in rows)),
              'build_total_accounted_usd': totals()['total_usd_accounted'], 'unresolved_calls': totals()['unresolved_calls'],
              'limits': {'day6_critic_allowance': 10, 'Shanghai_day': 25, 'build_total': 250},
              'image_generation_calls_day6': 0, 'paid_calls': calls,
              'journal_policy': 'No holds released or journal rows rewritten. Raw responses are archived by spend_reservation before interpretation; invoices remain unknown.'}
    (ROOT / 'spend.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record
