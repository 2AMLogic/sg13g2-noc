"""Rewrite absolute host paths in klt JSON envelopes to portable ones.

Mechanical prefix substitution only; no value is changed otherwise.
  <repo root>/...  -> repo-relative
  <PDK_ROOT>/...   -> $PDK_ROOT/...
usage: python3 -I sanitize.py REPO_ROOT PDK_ROOT FILE...
"""
import json
import sys


def fix(v, repo, pdk):
    if isinstance(v, str):
        if v.startswith(repo + "/"):
            return v[len(repo) + 1:]
        if v.startswith(pdk + "/"):
            return "$PDK_ROOT/" + v[len(pdk) + 1:]
        return v
    if isinstance(v, list):
        return [fix(x, repo, pdk) for x in v]
    if isinstance(v, dict):
        return {k: fix(x, repo, pdk) for k, x in v.items()}
    return v


repo, pdk = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/")
for path in sys.argv[3:]:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fix(doc, repo, pdk), f, indent=2)
        f.write("\n")
