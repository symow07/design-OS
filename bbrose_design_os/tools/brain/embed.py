"""§BH42(a) — semantic vectors for the brain's text documents.

Inference here is numpy and the standard library. The model is DATA, not code: a
vocabulary and a matrix exported once to var/brain/embed_model.npz, so the suite's
virtualenv gains no package (§BH35's lesson, and §BH40(c)'s standard-library server).

Encoding repeats the three steps the exporting library performs, and the agreement is
measured against that library's own tokenizer rather than asserted:
  1. normalise   — clean, pad CJK, strip accents, lowercase  (BertNormalizer)
  2. split       — on whitespace, then isolate punctuation    (BertPreTokenizer)
                   then greedy longest-match word pieces      (WordPiece, "##", [UNK])
  3. pool        — mean of the token rows, then L2 normalise  (cosine 1.0 vs the library)

The window is the model's own published default of 512 pieces. Measured over the whole
text corpus, 24.0% of documents run longer, and pooling the whole document instead of
its first 512 pieces moved no top-four hit on the probes tried — so the library's
setting is kept, and the tail of a long document stays reachable by the FTS half of the
answer, which indexes all of it.

A document whose every piece is unknown has no direction to point in; it is recorded
with a zero vector and reported as UNEMBEDDED rather than given a false neighbour.
"""
import json
import pathlib
import unicodedata

import numpy as np

MODEL_FILE = "embed_model.npz"
MAX_PIECES = 512
REBUILD_BOUND_SECONDS = 300           # §BH42(a) raised the bound from two minutes to five                      # the model's published window; see the note above
VECTORS_FILE = "vectors.npy"
VECTOR_IDS_FILE = "vector_ids.npy"
# the owner's sentence names the text sources: "rulings, lessons, reports, prompts,
# WATCH notes". The materials rows are the tier record's join, not text, and are the
# captions' subject in (b)/(d); they are not embedded here.
# §BH42(d): "brain.search ranks across text and captions together", so the captions join
# the semantic layer beside the text. The materials ROWS stay out: they are the tier
# record's join, and what they show is what the caption says.
TEXT_KINDS = ("register", "queue", "sitting", "launcher", "watch", "prompt", "caption")


def _is_control(ch: str) -> bool:
    if ch in ("\t", "\n", "\r"):
        return False
    return not ch.isspace() and unicodedata.category(ch).startswith("C")


def _is_cjk(cp: int) -> bool:
    return ((0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF) or (0x20000 <= cp <= 0x2A6DF)
            or (0x2A700 <= cp <= 0x2B73F) or (0x2B740 <= cp <= 0x2B81F) or (0x2B820 <= cp <= 0x2CEAF)
            or (0xF900 <= cp <= 0xFAFF) or (0x2F800 <= cp <= 0x2FA1F))


def _is_punct(ch: str) -> bool:
    cp = ord(ch)
    if 33 <= cp <= 47 or 58 <= cp <= 64 or 91 <= cp <= 96 or 123 <= cp <= 126:
        return True
    return unicodedata.category(ch).startswith("P")


def normalise(text: str) -> str:
    """BertNormalizer with clean_text, handle_chinese_chars, strip_accents and lowercase."""
    out = []
    for ch in text:
        cp = ord(ch)
        if cp == 0 or cp == 0xFFFD or _is_control(ch):
            continue
        if ch.isspace():
            out.append(" ")
        elif _is_cjk(cp):
            out.append(" "); out.append(ch); out.append(" ")
        else:
            out.append(ch)
    lowered = "".join(out).lower()
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def pre_tokenise(text: str):
    """BertPreTokenizer: split on whitespace, then isolate each punctuation character."""
    words = []
    for chunk in text.split():
        buf = ""
        for ch in chunk:
            if _is_punct(ch):
                if buf:
                    words.append(buf); buf = ""
                words.append(ch)
            else:
                buf += ch
        if buf:
            words.append(buf)
    return words


def word_pieces(word: str, vocab: dict, unk_id: int, prefix: str, max_chars: int):
    """Greedy longest-match-first, the WordPiece rule; an over-long or unmatchable word is [UNK]."""
    if len(word) > max_chars:
        return [unk_id]
    ids = []
    start = 0
    n = len(word)
    while start < n:
        end = n
        found = None
        while end > start:
            piece = word[start:end]
            if start > 0:
                piece = prefix + piece
            got = vocab.get(piece)
            if got is not None:
                found = got
                break
            end -= 1
        if found is None:
            return [unk_id]
        ids.append(found)
        start = end
    return ids


class Encoder:
    """The exported model, loaded as data."""

    def __init__(self, brain_dir):
        path = pathlib.Path(brain_dir) / MODEL_FILE
        with np.load(path, allow_pickle=True) as z:
            self.matrix = np.asarray(z["matrix"], dtype=np.float32)
            tokens = list(z["tokens"])
            self.meta = json.loads(str(z["meta"][0]))
        self.vocab = {str(t): i for i, t in enumerate(tokens)}
        self.unk_id = self.vocab[self.meta["unk_token"]]
        self.prefix = self.meta["continuing_subword_prefix"]
        self.max_chars = int(self.meta["max_input_chars_per_word"])
        self.dim = int(self.meta["dim"])

    def ids(self, text: str):
        out = []
        for word in pre_tokenise(normalise(text)):
            out.extend(word_pieces(word, self.vocab, self.unk_id, self.prefix, self.max_chars))
        return out

    def encode(self, texts):
        """Returns (vectors, unembedded) — a zero row for a document with no known piece."""
        vecs = np.zeros((len(texts), self.dim), dtype=np.float32)
        unembedded = []
        for i, text in enumerate(texts):
            ids = [t for t in self.ids(text)[:MAX_PIECES] if t != self.unk_id]
            if not ids:
                unembedded.append(i)
                continue
            v = self.matrix[ids].mean(axis=0)
            n = float(np.linalg.norm(v))
            if n == 0.0:
                unembedded.append(i)
                continue
            vecs[i] = v / n
        return vecs, unembedded


def model_present(brain_dir) -> bool:
    return (pathlib.Path(brain_dir) / MODEL_FILE).is_file()


def build(con, brain_dir):
    """Embed every text document in the index. Returns a record for the freshness file.

    With no exported model on disk the index is still built and the semantic layer reports
    itself NO_MODEL — stated, not skipped in silence. tools/brain/export_embed_model.py
    says how to put one there.
    """
    brain_dir = pathlib.Path(brain_dir)
    if not model_present(brain_dir):
        for stale in (brain_dir / VECTORS_FILE, brain_dir / VECTOR_IDS_FILE):
            if stale.is_file(): stale.unlink()
        return {"state": "NO_MODEL", "model": None, "vectors": 0, "kinds": list(TEXT_KINDS),
                "note": "no %s in %s — run tools/brain/export_embed_model.py" % (MODEL_FILE, brain_dir)}
    rows = list(con.execute(
        "SELECT id, COALESCE(title,'') || ' ' || COALESCE(text,'') FROM docs WHERE kind IN (%s)"
        % ",".join("?" * len(TEXT_KINDS)), TEXT_KINDS))
    enc = Encoder(brain_dir)
    ids = np.array([r[0] for r in rows], dtype=np.int64)
    vecs, unembedded = enc.encode([r[1] for r in rows])
    # np.save appends ".npy" to a name that lacks it, so the temporary files are written
    # through open handles and renamed under the names actually chosen (found by running it)
    tmp_v = brain_dir / (VECTORS_FILE + ".tmp")
    tmp_i = brain_dir / (VECTOR_IDS_FILE + ".tmp")
    with open(tmp_v, "wb") as fh:
        np.save(fh, vecs.astype(np.float16))
    with open(tmp_i, "wb") as fh:
        np.save(fh, ids)
    tmp_v.replace(brain_dir / VECTORS_FILE)
    tmp_i.replace(brain_dir / VECTOR_IDS_FILE)
    return {"state": "BUILT", "model": enc.meta["model"], "dim": enc.dim, "vectors": int(len(ids)),
            "kinds": list(TEXT_KINDS), "unembedded": len(unembedded), "max_pieces": MAX_PIECES}


def load_vectors(brain_dir):
    brain_dir = pathlib.Path(brain_dir)
    v = brain_dir / VECTORS_FILE
    i = brain_dir / VECTOR_IDS_FILE
    if not (v.is_file() and i.is_file()):
        return None, None
    return np.asarray(np.load(v), dtype=np.float32), np.load(i)


def nearest(query: str, brain_dir, limit=10):
    """(doc_id, cosine) for the closest documents; an empty list when nothing is built."""
    vecs, ids = load_vectors(brain_dir)
    if vecs is None or not len(ids):
        return []
    q, missing = Encoder(brain_dir).encode([query])
    if missing:
        return []
    scores = vecs @ q[0]
    top = np.argsort(-scores)[:limit]
    return [(int(ids[t]), float(scores[t])) for t in top]
