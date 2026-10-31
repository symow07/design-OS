#!/usr/bin/env python3
"""Reproduce the Day 2 proof; optional real native Illustrator validation.

The output directory must be new. Existing deliverables are never replaced.
No database records, provider calls, migrations or credentials are needed.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import zipfile

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native", action="store_true", help="Open Illustrator to verify a new native file")
    args = parser.parse_args()
    args.output = args.output.resolve()
    from apps.pipeline.services.design_spec import make_spec, digest
    from apps.pipeline.services.hybrid_bottle_output import compile_bundle
    spec = make_spec()
    record = compile_bundle(spec.model_dump(), args.output)
    if args.native:
        from apps.ire.compose_hybrid_bottle import compose
        from apps.ire.emitters import native_ai
        doc, _ = compose(spec)
        result = native_ai.build(doc, str(args.output / "artwork-native.ai"), timeout_s=120,
                                 drawing=str(args.output / "artwork.pdf"))
        verified = bool(result.get("built") and not result.get("missing_fonts") and not result.get("not_carried")
                        and not result.get("effects_not_carried") and result.get("check", {}).get("state") == "PASS")
        if not verified and (args.output / "artwork-native.ai").exists():
            rejected = args.output / "rejected"; rejected.mkdir()
            (args.output / "artwork-native.ai").rename(rejected / "artwork-native.ai")
        record["preflight"]["native_ai"] = "verified" if verified else "not_verified"
        record["preflight"]["native_validation"] = result
        (args.output / "preflight.json").write_text(json.dumps(record["preflight"], indent=2, ensure_ascii=False) + "\n")
        (args.output / "native-validation.json").write_text(json.dumps(result, indent=2) + "\n")
        record["native_validation"] = result
        with (args.output / "READ-ME.txt").open("a") as readme:
            readme.write("\nNative Illustrator: " + ("verified file included; see native-validation.json.\n" if verified
                                                     else "not verified; no native file offered. See native-validation.json.\n"))
        with zipfile.ZipFile(args.output / "editable-master.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(args.output.rglob("*")):
                if path.is_file() and path.name != "editable-master.zip" and "rejected" not in path.relative_to(args.output).parts and path.suffix != ".jsx":
                    archive.write(path, path.relative_to(args.output))
    record["artifact_hashes"] = {p.name: digest(p.read_bytes()) for p in args.output.iterdir() if p.is_file()}
    (args.output / "build-record.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(args.output), "spend_usd": 0, "native_built": record.get("native_validation", {}).get("built"),
                      "production_ready": False, "creative_acceptance": "review_pending"}))


if __name__ == "__main__":
    main()
