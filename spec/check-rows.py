#!/usr/bin/env python3
"""Drift check: spec/noc.md section 1 vs spec/noc.rows.json (issue #30).

Parses the section 1 parameter table of spec/noc.md and asserts that the
machine-readable rendering spec/noc.rows.json carries the same rows (same
order, parameter, target, fallback, stretch and source_status text), and that
spec/noc.not-applicable.json has exactly one entry per row id.

    python3 -I spec/check-rows.py            exit 0 = in sync; non-zero names the drift
    python3 -I spec/check-rows.py --write    regenerate the 'rows' array of noc.rows.json
                                             (ids come from the existing file, by position)
"""
import json
import sys
from pathlib import Path

SPEC = Path(__file__).resolve().parent
FIELDS = ("parameter", "target", "fallback", "stretch", "source_status")


def parse_table(md):
    lines = md.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("## 1. "))
    rows = []
    for l in lines[start + 1:]:
        if l.startswith("## "):
            break
        if not l.startswith("|"):
            continue
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if cells[0] in ("Parameter",) or set(cells[0]) <= {"-"}:
            continue
        if len(cells) != 5:
            sys.exit(f"check-rows: malformed section 1 row: {l!r}")
        rows.append(dict(zip(FIELDS, cells)))
    return rows


def main():
    table = parse_table((SPEC / "noc.md").read_text(encoding="utf-8"))
    rows_path = SPEC / "noc.rows.json"
    doc = json.loads(rows_path.read_text(encoding="utf-8"))
    if "--write" in sys.argv:
        ids = [r["id"] for r in doc["rows"]]
        if len(ids) != len(table):
            sys.exit(f"check-rows: --write needs ids for {len(table)} rows, have {len(ids)}")
        doc["rows"] = [{"id": i, **t} for i, t in zip(ids, table)]
        rows_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    errs = []
    got = doc["rows"]
    if len(got) != len(table):
        errs.append(f"row count: noc.md section 1 has {len(table)}, noc.rows.json has {len(got)}")
    for n, (t, g) in enumerate(zip(table, got)):
        for f in FIELDS:
            if t[f] != g.get(f):
                errs.append(f"row {n + 1} ({g.get('id')}): field {f!r} differs: md={t[f]!r} json={g.get(f)!r}")
    ids = [r.get("id") for r in got]
    if len(set(ids)) != len(ids):
        errs.append("duplicate ids in noc.rows.json")
    na = json.loads((SPEC / "noc.not-applicable.json").read_text(encoding="utf-8"))
    na_ids = [r["id"] for r in na["rows"]]
    if sorted(na_ids) != sorted(ids) or len(set(na_ids)) != len(na_ids):
        errs.append(f"not-applicable ids differ from spec ids: missing={sorted(set(ids) - set(na_ids))} extra={sorted(set(na_ids) - set(ids))}")
    for e in errs:
        print("DRIFT:", e, file=sys.stderr)
    if not errs:
        print(f"check-rows: ok, {len(table)} rows in sync")
    return 1 if errs else 0


sys.exit(main())
