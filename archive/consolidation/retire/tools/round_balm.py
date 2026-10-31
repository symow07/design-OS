#!/usr/bin/env python3
"""Run an explicit Round 1 section; paid sections use the owner's scoped ledger."""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('section',choices=['inspect','cut','check-marks','develop','final'])
    p.add_argument('--sketch')
    args=p.parse_args()
    import django
    django.setup()
    from apps.pipeline.services import round_balm_run as run
    actions={'inspect':run.inspect_sketches,'cut':run.cut,'check-marks':run.check_marks,'final':run.final_order}
    if args.section=='develop':
        if not args.sketch:p.error('--sketch is required')
        result=run.develop(args.sketch)
    else:result=actions[args.section]()
    print(result)


if __name__=='__main__':main()
