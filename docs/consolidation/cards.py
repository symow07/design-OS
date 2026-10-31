"""Writes docs/consolidation/engines/<nn>-<slug>.md, one card per row of docs/ENGINE_MAP.md, from the card texts
(cards_a/b/c.py, read from each engine's code) and the run each probe recorded (engines/runs/<nn>.json); then checks
coverage: one card per map row, none missing.

    python3 docs/consolidation/cards.py"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cards_a import CARDS as A  # noqa: E402
from cards_b import CARDS as B  # noqa: E402
from cards_c import CARDS as C  # noqa: E402

CARDS = {**A, **B, **C}
MAP = HERE.parent / 'ENGINE_MAP.md'
VERDICTS = ('GOOD', 'PARTLY', 'BROKEN', 'UNUSED BY THE GOAL')


def map_rows():
    rows = {}
    for line in MAP.read_text().splitlines():
        cells = [c.strip() for c in line.split('|')]
        if len(cells) > 4 and cells[1].isdigit():
            rows[int(cells[1])] = {'name': cells[2], 'path': cells[3].strip('`')}
    return rows


def short(value, limit=230):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = ' '.join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


def outcome(run):
    """What came out, as lines: each top-level result, each nested result one level down, then the tests."""
    if not run.get('ok'):
        return ['- **The probe itself failed:** ' + short(run.get('error', ''))]
    result = dict(run.get('result') or {})
    tests = result.pop('tests', None)
    lines = []
    for key, value in result.items():
        if isinstance(value, dict) and value and all(isinstance(v, dict) for v in value.values()) and len(value) <= 12:
            lines.append('- `%s`:' % key)
            lines += ['  - %s: %s' % (k, short(v, 200)) for k, v in value.items()]
        else:
            lines.append('- `%s`: %s' % (key, short(value)))
    if tests:
        lines.append('- own tests (%s%s): **%s**' % (', '.join(Path(t).name for t in tests['tests']),
                                                   ', -k "%s"' % tests['k'] if tests.get('k') else '', tests['summary']))
        lines += ['  - failed: `%s`' % f.split('::')[-1] for f in tests.get('failed', [])[:9]]
    lines.append('- seconds: %s; files written: %d (kept in the run folder, not committed)' % (run.get('seconds'),
                                                                                               len(run.get('files', []))))
    return lines


def card(n, row, text, run):
    verdict = text['verdict']
    assert verdict in VERDICTS, (n, verdict)
    parts = ['# %d · %s' % (n, row['name']), '',
             '`%s` · chain step: **%s**' % (row['path'], text['step']), '',
             '## What it does today (read from its code)', text['does'].strip(), '',
             '## The run ($0)', text['run'].strip(),
             'Recorded in [runs/%02d.json](runs/%02d.json), made by `docs/consolidation/probe.py %d`. What came out:' % (n, n, n),
             *outcome(run), '',
             '## Verdict: %s' % verdict]
    for key in ('partly', 'finding', 'broken'):
        if text.get(key):
            parts.append(text[key].strip())
    parts += ['', '## Parts worth keeping', text['keep'].strip(), '']
    return '\n'.join(parts)


def main():
    rows = map_rows()
    folder = HERE / 'engines'
    written = []
    for n, row in sorted(rows.items()):
        if n not in CARDS:
            continue
        run = json.loads((folder / 'runs' / ('%02d.json' % n)).read_text())
        path = folder / ('%02d-%s.md' % (n, CARDS[n]['slug']))
        path.write_text(card(n, row, CARDS[n], run))
        written.append(path.name)
    cards = sorted(p.name for p in folder.glob('[0-9][0-9]-*.md'))
    missing = sorted(set(rows) - {int(name[:2]) for name in cards})
    counts = {}
    for n in rows:
        if n in CARDS:
            counts[CARDS[n]['verdict']] = counts.get(CARDS[n]['verdict'], 0) + 1
    print('map rows %d · cards %d · missing %s · verdicts %s' % (len(rows), len(cards), missing or 'none', counts))
    if missing or len(cards) != len(rows):
        sys.exit('coverage check FAILED: the cards do not cover every row of the map')


if __name__ == '__main__':
    main()
