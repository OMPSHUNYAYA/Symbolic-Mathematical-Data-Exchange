#!/usr/bin/env python3
"""
ssmde_verify.py

Shunyaya Symbolic Mathematical Data Exchange (SSMDE)
Tiny CI/self-check harness.

What this verifies
------------------
1) Boundedness: align is strictly within (-1,+1).
2) Order invariance: fusion over a series is insensitive to permutation (A+B vs B+A).
3) Band mapping: align maps to the correct band given manifest cutpoints.
4) Manifest presence: a manifest_id string must be present.
5) Stamp structure: 'SSMCLOCK1|<UTC>|theta=<deg>|sha256=<hex>|prev=<...>' basic regex.

Notes
-----
- Uses the same align pipeline as the core module (imported locally).
- No external dependencies.
"""

#!/usr/bin/env python3
from __future__ import annotations
import re
from hashlib import sha256
from ssmde_align_core import (
    compute_align, Manifest, DEFAULT_MANIFEST,
    build_ssmde_record, canonical_json, EPS_A, EPS_W,
    validate_manifest
)

STAMP_RE = re.compile(
    r"^SSMCLOCK1\|"
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\|"
    r"theta=\d+\.\d{2}\|sha256=[0-9a-f]{64}\|prev=([0-9a-f]{64}|NONE)$"
)

def pass_fail(name: str, ok: bool) -> bool:
    print(f"{name}: {'PASS' if ok else 'FAIL'}")
    return ok

def test_boundedness() -> bool:
    series = [
        [0.0],
        [0.2, -0.1, 0.05],
        [0.99, 0.99, 0.99],
        [-0.99, -0.98, -0.97],
        [0.9, -0.9, 0.9, -0.9],
    ]
    ok = True
    for s in series:
        a = compute_align(s, eps_a=EPS_A, eps_w=EPS_W)
        ok &= (-1.0 < a < 1.0)
    return pass_fail("boundedness(-1,+1)", ok)

def test_order_invariance() -> bool:
    seq = [0.7, -0.2, 0.1, 0.6, -0.5, 0.3]
    ok = abs(compute_align(seq) - compute_align(list(reversed(seq)))) < 1e-12
    return pass_fail("order_invariance(batch==reversed)", ok)

def test_band_mapping() -> bool:
    m = DEFAULT_MANIFEST
    ok = True
    for name, lo, hi in m.bands:
        target = (lo + hi) / 2.0
        rec = build_ssmde_record({"x":1}, [target, target, target], m)
        ok &= (rec["band"] == name)
    return pass_fail("band_mapping(manifest cutpoints)", ok)

def test_manifest_presence_and_stamp() -> bool:
    rec = build_ssmde_record({"foo": 42}, [0.15, 0.05, 0.10], DEFAULT_MANIFEST)
    has_manifest = isinstance(rec.get("manifest_id"), str) and len(rec["manifest_id"]) >= 3
    stamp_ok = isinstance(rec.get("stamp"), str) and (STAMP_RE.match(rec["stamp"]) is not None)
    return pass_fail("manifest_id+stamp_format", has_manifest and stamp_ok)

def test_stamp_chain() -> bool:
    r1 = build_ssmde_record({"x": 1}, [0.1, 0.1, 0.1], DEFAULT_MANIFEST)
    prev_hash = sha256(r1["stamp"].encode("utf-8")).hexdigest()
    r2 = build_ssmde_record({"x": 2}, [0.2, 0.2, 0.2], DEFAULT_MANIFEST, prev_stamp_hash=prev_hash)
    ok = (STAMP_RE.match(r1["stamp"]) is not None) and (STAMP_RE.match(r2["stamp"]) is not None) and (prev_hash in r2["stamp"])
    return pass_fail("stamp_chain(prev=hash(prev_stamp))", ok)

def test_manifest_validate() -> bool:
    ok, msgs = validate_manifest(DEFAULT_MANIFEST)
    # Only fail if validator returns hard-fail
    return pass_fail("manifest_validate(DEFAULT)", ok)

def main():
    results = [
        test_boundedness(),
        test_order_invariance(),
        test_band_mapping(),
        test_manifest_presence_and_stamp(),
        test_stamp_chain(),
        test_manifest_validate(),
    ]
    all_ok = all(results)
    print("\nALL CHECKS PASSED" if all_ok else "\nONE OR MORE CHECKS FAILED")
    raise SystemExit(0 if all_ok else 2)

if __name__ == "__main__":
    main()
