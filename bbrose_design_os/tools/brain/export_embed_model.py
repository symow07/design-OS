"""§BH42(a) — put the static embedding model under var/brain/ as DATA.

The suite's virtualenv gains no package: this script runs from a scratch environment,
downloads the published static model once and writes a vocabulary and a matrix to
var/brain/embed_model.npz. tools/brain/embed.py then does inference with numpy and the
standard library alone.

    python3.11 -m venv ~/scratch_venv
    ~/scratch_venv/bin/pip install model2vec
    ~/scratch_venv/bin/python bbrose_design_os/tools/brain/export_embed_model.py

Run it with no gate running: §BH35's first run was refused for installing tooling
beside one. var/brain/ is git-ignored, so the file is derived and never tracked.
"""
import json, pathlib, sys

MODEL = "minishlab/potion-retrieval-32M"
OUT = pathlib.Path(__file__).resolve().parents[3] / "var" / "brain"


def main():
    try:
        import numpy as np
        from model2vec import StaticModel
    except ImportError as exc:
        print("needs model2vec in a scratch environment (see this file's header): %s" % exc, file=sys.stderr)
        return 2
    m = StaticModel.from_pretrained(MODEL)
    tj = json.loads(m.tokenizer.to_str())
    vocab = tj["model"]["vocab"]
    order = sorted(vocab, key=lambda t: vocab[t])
    if [vocab[t] for t in order] != list(range(len(order))):
        print("the vocabulary's ids are not dense; the export refuses", file=sys.stderr)
        return 1
    E = np.asarray(m.embedding, dtype=np.float32)
    if E.shape[0] != len(order):
        print("matrix rows %d against vocabulary %d; the export refuses" % (E.shape[0], len(order)), file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"model": MODEL, "dim": int(E.shape[1]), "vocab": len(order),
            "unk_token": tj["model"]["unk_token"],
            "continuing_subword_prefix": tj["model"]["continuing_subword_prefix"],
            "max_input_chars_per_word": tj["model"]["max_input_chars_per_word"],
            "normalizer": tj["normalizer"], "pre_tokenizer": tj["pre_tokenizer"]["type"],
            "pooling": "mean of the token rows, then L2 normalise"}
    np.savez(OUT / "embed_model.npz", matrix=E.astype(np.float16),
             tokens=np.array(order, dtype=object), meta=np.array([json.dumps(meta)], dtype=object))
    path = OUT / "embed_model.npz"
    print("wrote %s  %.1f MB  matrix %s  vocab %d" % (path, path.stat().st_size / 1e6, E.shape, len(order)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
