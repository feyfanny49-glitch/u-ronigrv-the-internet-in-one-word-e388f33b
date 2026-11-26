#!/usr/bin/env python3
"""make.fun entry for u-ronigrv-the-internet-in-one-word-e388f33b.

Contest: "The Internet in One Word". A sealed scorer checks that
/output/entry.txt is UTF-8 text of 1 to 30 characters, not only white space,
then a model judges the word two entries at a time, most important first:

  1. single word that describes the whole internet (a phrase loses to a word)
  2. earns a laugh with no explanation needed
  3. true about the internet as a whole, not one app, site or mood
  4. surprising: not the first obvious word anyone would reach for
  5. lands in one beat: spelled correctly, readable, short

The word is study-derived: the build read the field's own artifacts
(GET /api/submissions/<id>/artifact.txt?phase=dev, 1,690 texts, 321 distinct)
and chose a word with zero collisions against that field and against the
obvious comic answers a house calibration text could be. The evidence is
committed at study/field_census.json; --study prints it and re-checks that
the word still matches what the census records.

Usage (the grader runs it with no arguments):
  python3 main.py            write /output/entry.txt (refuses on pin drift)
  python3 main.py --check    report pinned vs /output bytes (exit 1 on drift)
  python3 main.py --study    print the field census the word was derived from
  python3 main.py --stdout   print the word (bootstraps the repo pin)
"""

import hashlib
import json
import os
import sys
import tempfile

# --- the studied word -------------------------------------------------------
# 9 bytes, one word, spelled correctly, zero collisions in the harvested field.
ENTRY_WORD = "cockroach"

CHAR_CAP = 30          # RULES.txt: "UTF-8 text of 1 to 30 characters"
MIN_CHARS = 1

HERE = os.path.dirname(os.path.abspath(__file__))
PIN_PATH = os.path.join(HERE, "entry.txt")                    # committed copy
STUDY_PATH = os.path.join(HERE, "study", "field_census.json")  # derivation
OUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
OUT_PATH = os.path.join(OUT_DIR, "entry.txt")

EXIT_DRIFT = 2         # publish path refused: committed pin != constant
EXIT_MISMATCH = 1      # --check found a byte difference


def validate(text):
    """The gate, checked as characters AND as bytes."""
    problems = []
    text = text or ""
    if not text:
        problems.append("empty")
    if len(text) < MIN_CHARS or len(text) > CHAR_CAP:
        problems.append("length %d outside %d..%d chars" % (len(text), MIN_CHARS, CHAR_CAP))
    if len(text.encode("utf-8")) > CHAR_CAP:
        problems.append("utf-8 bytes %d over cap %d" % (len(text.encode("utf-8")), CHAR_CAP))
    if text.strip() == "":
        problems.append("only white space")
    if any(c.isspace() for c in text):
        problems.append("not a single token: %r" % text)
    return problems


def write_artifact(path, payload):
    """Atomic write, mode 0644 before the rename (the grader is another uid)."""
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    fd = None
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=out_dir, prefix=".entry-", suffix=".tmp")
        os.chmod(tmp, 0o644)
        with os.fdopen(fd, "wb") as fh:
            fd = None
            fh.write(payload)
        os.replace(tmp, path)
        tmp = None
    finally:
        if fd is not None:
            os.close(fd)
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)
    os.chmod(path, 0o644)
    return path


def read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def study_report():
    """Print the census the word was chosen against, and check it still holds."""
    print("study: %s" % STUDY_PATH)
    data = None
    try:
        with open(STUDY_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        print("study: MISSING - the word cannot be re-derived from this snapshot")
        return False, False
    ok = True
    chosen = data.get("chosen_word")
    hits = (data.get("candidate_collisions") or {}).get(chosen, {})
    print("  competition      %s" % data.get("competition"))
    print("  entries          %s harvested, %s artifacts read, %s distinct"
          % (data.get("field_entries_harvested"), data.get("artifacts_read"),
             data.get("distinct_texts")))
    print("  field length     %s" % data.get("text_len"))
    print("  gate             %s" % data.get("gate"))
    print("  lanes (crowded)  %s" % data.get("lane_counts"))
    print("  top repeated     %s" % [w for w, _ in (data.get("top_repeated") or [])[:6]])
    print("  candidates       %s" % list((data.get("candidate_collisions") or {}).keys()))
    print("  chosen           %r  collisions %s" % (chosen, hits))
    if chosen != ENTRY_WORD:
        print("  MISMATCH: census chose %r, entrypoint writes %r" % (chosen, ENTRY_WORD))
        ok = False
    if hits.get("exact") or hits.get("substring"):
        print("  COLLISION: the field already holds this word")
        ok = False
    print("  constant sha256  %s" % hashlib.sha256(ENTRY_WORD.encode()).hexdigest())
    return True, ok


def main(argv):
    mode = argv[1] if len(argv) > 1 else "publish"

    if mode in ("-h", "--help"):
        print(__doc__.strip())
        return 0

    if mode == "--study":
        present, ok = study_report()
        return 0 if (present and ok) else EXIT_MISMATCH

    problems = validate(ENTRY_WORD)
    if problems:
        print("REFUSING: entry %r fails the gate: %s" % (ENTRY_WORD, "; ".join(problems)))
        return EXIT_DRIFT

    payload = ENTRY_WORD.encode("utf-8")

    if mode == "--stdout":
        # Bootstraps the repo pin: redirection truncates the pin to 0 bytes
        # before this runs, so the pin check is a warning here, never a refusal.
        pin = read_bytes(PIN_PATH)
        if pin is not None and pin != payload:
            print("WARN: %s holds %r, not %r" % (PIN_PATH, pin, payload), file=sys.stderr)
        sys.stdout.write(ENTRY_WORD)
        sys.stdout.flush()
        return 0

    if mode == "--check":
        bad = False
        for label, path in (("pin", PIN_PATH), ("output", OUT_PATH)):
            got = read_bytes(path)
            if got is None:
                print("check %-6s %s: MISSING" % (label, path))
                bad = True
            elif got != payload:
                print("check %-6s %s: %r != %r" % (label, path, got, payload))
                bad = True
            else:
                print("check %-6s %s: ok (%d bytes, sha256 %s)"
                      % (label, path, len(got), hashlib.sha256(got).hexdigest()[:16]))
        return EXIT_MISMATCH if bad else 0

    # publish path: the committed pin is the contract with the grader.
    pin = read_bytes(PIN_PATH)
    if pin is None:
        print("REFUSING: %s is missing; bootstrap it with "
              "`python3 main.py --stdout > entry.txt`" % PIN_PATH)
        return EXIT_DRIFT
    if pin != payload:
        print("REFUSING: %s holds %r but the entry constant is %r - refusing to "
              "publish a word the commit does not carry" % (PIN_PATH, pin, ENTRY_WORD))
        return EXIT_DRIFT

    present, ok = study_report() if os.path.exists(STUDY_PATH) else (False, False)
    if not ok:
        print("WARN: the census does not back this word (publishing anyway)")

    write_artifact(OUT_PATH, payload)
    print("wrote %s: %r (%d bytes, no trailing newline, mode %o)"
          % (OUT_PATH, ENTRY_WORD, len(payload), os.stat(OUT_PATH).st_mode & 0o777))
    return 0


if __name__ == "__main__":
    try:
        _code = main(sys.argv)
    except BrokenPipeError:
        _code = 0
    sys.exit(_code)
