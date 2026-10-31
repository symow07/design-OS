"""Dead ends of apps/pipeline/services/product_drawing.py, moved here verbatim (the owner's goal of 2026-10-29, §1: any function nothing calls is
listed and removed; nothing deleted). Nothing live or in the tests called them at the move: write_record."""


def write_record(rec, path):
    Path(path).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
