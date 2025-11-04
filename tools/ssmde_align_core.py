#!/usr/bin/env python3
"""
ssmde_align_core.py  — SSMDE align-and-emit quickstart (observation-only)

CLI (most common)
  --demo
  --value "<json>" --a_raw "<json_list>" [--prev HEX] [--weights "<json_list>"] [--pretty]
  --manifest-from "<json string or path>"
  --manifest-dump-effective "<path>"
  --manifest-validate
  --band-card

Generators
  --emit-manifest "<path>"
  --emit-examples "<path>" [--examples N] [--seed S]

Batch conversion (ingestion helper)
  --from-jsonl "<input.jsonl>" --to-jsonl "<output.jsonl>"
    (expects each line: {"value":{...},"a_raw":[...], "prev":"<hex|optional>"} )

Formulas (ASCII)
  a_c := clamp(a_raw, -1+eps_a, +1-eps_a)
  u   := atanh(a_c)
  U  += w * u ; W += w
  align := tanh( U / max(W, eps_w) )
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Iterable, Optional, Tuple, List
from math import atanh, tanh
from hashlib import sha256
from datetime import datetime, timezone
import json, argparse, random, os, sys

# ----------------------------
# Numeric guards
# ----------------------------
EPS_A = 1e-6
EPS_W = 1e-12

# ----------------------------
# Helpers
# ----------------------------
def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x

def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))

def pretty_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)

def theta_from_time(ts: datetime) -> float:
    sod = ts.hour*3600 + ts.minute*60 + ts.second
    return round((sod % 86400) * 360.0 / 86400.0, 2)

def make_stamp(content_block: Dict[str, Any], prev: Optional[str] = None) -> str:
    ts = datetime.now(tz=timezone.utc).replace(microsecond=0)
    ts_iso = ts.isoformat().replace("+00:00", "Z")
    theta = f"{theta_from_time(ts):.2f}"
    digest = sha256(canonical_json(content_block).encode("utf-8")).hexdigest()
    prev_s = prev if (prev and isinstance(prev, str) and len(prev) >= 8) else "NONE"
    return f"SSMCLOCK1|{ts_iso}|theta={theta}|sha256={digest}|prev={prev_s}"

# ----------------------------
# Manifest model
# ----------------------------
@dataclass
class Manifest:
    manifest_id: str
    bands: Tuple[Tuple[str, float, float], ...]  # (name, align_min, align_max)
    eps_a: float = EPS_A
    eps_w: float = EPS_W
    def pick_band(self, align: float) -> str:
        for name, lo, hi in self.bands:
            if align > lo and align <= hi:
                return name
            # inclusive low edge for last bucket
            if name == self.bands[-1][0] and align >= lo and align <= hi:
                return name
        return "UNBanded"

DEFAULT_MANIFEST = Manifest(
    manifest_id="PLANT_A_BEARING_SAFETY_v7",
    bands=(
        ("CRITICAL", -1.00, -0.80),
        ("AMBER",    -0.80, -0.30),
        ("A0",       -0.30,  0.70),
        ("A++",       0.70,  1.00),
    ),
)

def _bands_from_json(obj: Any) -> Tuple[Tuple[str, float, float], ...]:
    out: List[Tuple[str, float, float]] = []
    if isinstance(obj, list) and obj:
        if isinstance(obj[0], dict):
            for b in obj:
                out.append((str(b["name"]), float(b["align_min"]), float(b["align_max"])))
        else:
            for name, lo, hi in obj:
                out.append((str(name), float(lo), float(hi)))
    return tuple(out)

def _load_manifest_from(s: str) -> Manifest:
    if os.path.exists(s):
        with open(s, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.loads(s)

    mid = str(data.get("manifest_id", DEFAULT_MANIFEST.manifest_id))
    ac = data.get("align_computation", {})
    eps_a = float(ac.get("eps_a", data.get("eps_a", DEFAULT_MANIFEST.eps_a)))
    eps_w = float(ac.get("eps_w", data.get("eps_w", DEFAULT_MANIFEST.eps_w)))
    bands = _bands_from_json(data.get("bands", [])) or _bands_from_json(data.get("bands_tuple", [])) or DEFAULT_MANIFEST.bands
    return Manifest(manifest_id=mid, bands=bands, eps_a=eps_a, eps_w=eps_w)

def validate_manifest(m: Manifest) -> Tuple[bool, List[str]]:
    msgs: List[str] = []
    ok = True

    # 1) basic ranges
    for name, lo, hi in m.bands:
        if not (-1.0 <= lo < hi <= 1.0):
            ok = False; msgs.append(f"Band '{name}' out of range or invalid interval: [{lo},{hi}]")

    # 2) sorted by upper bound
    sorted_bands = sorted(m.bands, key=lambda x: x[2])  # by hi
    if tuple(sorted_bands) != m.bands:
        msgs.append("Bands not sorted by 'align_max' (hi). Recommend ascending by hi.")

    # 3) overlap/gaps check (treat last band low inclusive, others open)
    prev_hi = None
    for idx, (name, lo, hi) in enumerate(sorted_bands):
        if prev_hi is not None:
            if lo < prev_hi:  # overlap
                ok = False; msgs.append(f"Overlap between bands ending at {prev_hi} and '{name}' starting at {lo}")
            if lo > prev_hi:  # gap
                msgs.append(f"Gap between previous band hi={prev_hi} and '{name}' lo={lo}")
        prev_hi = hi

    # 4) recommended coverage (close to full -1..1)
    first_lo = sorted_bands[0][1]
    last_hi = sorted_bands[-1][2]
    if first_lo > -1.0 + 1e-6:
        msgs.append(f"Coverage begins at {first_lo} (> -1). Consider extending to -1.")
    if last_hi < 1.0 - 1e-6:
        msgs.append(f"Coverage ends at {last_hi} (< 1). Consider extending to +1.")

    # 5) eps guards
    if not (0.0 < m.eps_a < 1e-2): msgs.append(f"eps_a unusual: {m.eps_a}")
    if not (0.0 < m.eps_w < 1e-6): msgs.append(f"eps_w unusual: {m.eps_w}")

    return ok, msgs

# ----------------------------
# Core alignment
# ----------------------------
def compute_align(a_raw_series: Iterable[float],
                  weights: Optional[Iterable[float]] = None,
                  eps_a: float = EPS_A,
                  eps_w: float = EPS_W) -> float:
    U = 0.0; W = 0.0
    if weights is None:
        for a in a_raw_series:
            a_c = clamp(a, -1.0 + eps_a, 1.0 - eps_a)
            U += atanh(a_c); W += 1.0
    else:
        for a, w in zip(a_raw_series, weights):
            a_c = clamp(a, -1.0 + eps_a, 1.0 - eps_a)
            U += float(w) * atanh(a_c); W += float(w)
    return tanh(U / max(W, eps_w))

def build_ssmde_record(value_block: Dict[str, Any],
                       a_raw_series: Iterable[float],
                       manifest: Manifest = DEFAULT_MANIFEST,
                       weights: Optional[Iterable[float]] = None,
                       prev_stamp_hash: Optional[str] = None) -> Dict[str, Any]:
    align = compute_align(a_raw_series, weights=weights, eps_a=manifest.eps_a, eps_w=manifest.eps_w)
    band = manifest.pick_band(align)
    core = {
        "value": value_block,
        "align": float(align),
        "band": band,
        "manifest_id": manifest.manifest_id,
    }
    core["stamp"] = make_stamp(
        {"value": value_block, "align": float(align), "band": band, "manifest_id": manifest.manifest_id},
        prev=prev_stamp_hash
    )
    return core

# ----------------------------
# Convenience generators / tools
# ----------------------------
def write_manifest_template(path: str) -> None:
    tpl = {
        "manifest_id": DEFAULT_MANIFEST.manifest_id,
        "domain": "Industrial/Mechanical",
        "description": "Bearing health policy for Plant A, Line 3. Align via clamp->atanh->accumulate->tanh; bands carry escalation promises.",
        "align_computation": {
            "eps_a": DEFAULT_MANIFEST.eps_a,
            "eps_w": DEFAULT_MANIFEST.eps_w,
            "weights": "uniform",
            "pipeline": [
                "a_c := clamp(a_raw, -1+eps_a, +1-eps_a)",
                "u := atanh(a_c)",
                "U += w * u ; W += w",
                "align := tanh( U / max(W, eps_w) )"
            ]
        },
        "bands": [
            {"name":"A++","align_min":0.70,"align_max":1.00,"action":"no action","window":"none"},
            {"name":"A0","align_min":-0.30,"align_max":0.70,"action":"monitor only","window":"inspect in <= 8h"},
            {"name":"AMBER","align_min":-0.80,"align_max":-0.30,"action":"inspect","window":"inspect in <= 30 min"},
            {"name":"CRITICAL","align_min":-1.00,"align_max":-0.80,"action":"stop/evacuate","window":"human respond in <= 10 min"}
        ],
        "escalation_owner":"Plant Safety Officer",
        "policy_author":"Reliability Board",
        "policy_version":"v7",
        "revision_notes":"Updated AMBER window from 60 min to 30 min"
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tpl, f, indent=2, ensure_ascii=False)

def generate_examples_jsonl(path: str, manifest: Manifest,
                            n: int = 10, seed: Optional[int] = None) -> None:
    if seed is not None:
        random.seed(int(seed))
    pool: List[Dict[str, Any]] = [
        {"band":"AMBER","align":-0.60,"value":{"temperature_K":279.9,"a_phase":-0.62}, "mid":manifest.manifest_id},
        {"band":"AMBER","align":-0.50,"value":{"V_rms":253.7,"pf":0.81,"stress_score":0.72}, "mid":manifest.manifest_id},
        {"band":"A0","align":-0.10,"value":{"cash_collected_usd":18420.77}, "mid":"AR_STABILITY_Q4_CLOSE_v2"},
        {"band":"A0","align":0.40, "value":{"model_score":0.912,"uncertainty":0.18}, "mid":"AI_DECISION_POLICY_v3"},
        {"band":"A++","align":0.75,"value":{"spo2":0.95,"hr_bpm":78}, "mid":"CLINIC_VITALS_POLICY_v1"},
        {"band":"CRITICAL","align":-0.88,"value":{"strain_micro":220.5,"temp_K":315.3}, "mid":"BRIDGE_TRUSS_SAFETY_v4"},
        {"band":"A0","align":0.60, "value":{"throughput_mbps":512,"error_rate":0.0012}, "mid":"NET_EDGE_QOS_v5"},
        {"band":"CRITICAL","align":-0.92,"value":{"power_kw":42.3,"temp_K":330.2}, "mid":"DATACENTER_CABINET_POLICY_v6"},
        {"band":"A0","align":-0.15,"value":{"co2_ppm":980,"voc_index":0.22}, "mid":"BUILDING_AIR_QUALITY_v2"},
        {"band":"AMBER","align":-0.45,"value":{"wind_speed_ms":18.4,"gust_ms":26.9}, "mid":"FIELD_WIND_RISK_v1"},
    ]
    prev_hash: Optional[str] = None
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            t = pool[i % len(pool)]
            base_a = t["align"]
            a_raw = [max(-0.999999, min(0.999999, base_a + random.uniform(-0.03, 0.03))) for _ in range(3)]
            rec = build_ssmde_record(t["value"], a_raw, manifest=manifest, prev_stamp_hash=prev_hash)
            rec["band"] = t["band"]
            stamp_core = {k: rec[k] for k in ["value","align","band","manifest_id"]}
            rec["stamp"] = make_stamp(stamp_core, prev=prev_hash)
            prev_hash = sha256(rec["stamp"].encode("utf-8")).hexdigest()
            f.write(canonical_json(rec) + "\n")

def dump_effective_manifest(path: str, m: Manifest) -> None:
    payload = {
        "manifest_id": m.manifest_id,
        "eps_a": m.eps_a,
        "eps_w": m.eps_w,
        "bands_tuple": [(name, lo, hi) for (name, lo, hi) in m.bands]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

def print_band_card(m: Manifest) -> None:
    print("Band Card — effective manifest")
    print(f"manifest_id: {m.manifest_id}")
    print(f"eps_a: {m.eps_a}, eps_w: {m.eps_w}")
    for (name, lo, hi) in m.bands:
        print(f"- {name}: ({lo}, {hi}]")

def jsonl_convert(in_path: str, out_path: str, manifest: Manifest) -> None:
    """
    Read JSONL with lines of: {"value":{...},"a_raw":[...], "prev":"<hex|optional>"}
    Write JSONL of full SSMDE records (canonical JSON).
    """
    prev_hash: Optional[str] = None
    with open(in_path, "r", encoding="utf-8") as fin, open(out_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line: 
                continue
            obj = json.loads(line)
            value = obj["value"]
            a_raw = obj["a_raw"]
            prev = obj.get("prev")
            rec = build_ssmde_record(value, a_raw, manifest=manifest, prev_stamp_hash=(prev or prev_hash))
            prev_hash = sha256(rec["stamp"].encode("utf-8")).hexdigest()
            fout.write(canonical_json(rec) + "\n")

# ----------------------------
# Demo / CLI
# ----------------------------
def demo_three_domains(manifest: Manifest, pretty: bool=False) -> None:
    value1 = {"temperature_K":279.92,"a_phase":-0.62}
    a_raw1 = [-0.60,-0.64,-0.62]
    rec1 = build_ssmde_record(value1, a_raw1, manifest)

    value2 = {"refund_amount_usd":184.50,"model_score":0.912,"stress_score":0.35}
    a_raw2 = [0.10,0.05,0.20]
    rec2 = build_ssmde_record(value2, a_raw2, manifest,
                              prev_stamp_hash=sha256(rec1["stamp"].encode("utf-8")).hexdigest())

    value3 = {"V_rms":253.7,"pf":0.81,"stress_score":0.72}
    a_raw3 = [-0.55,-0.68,-0.75]
    rec3 = build_ssmde_record(value3, a_raw3, manifest,
                              prev_stamp_hash=sha256(rec2["stamp"].encode("utf-8")).hexdigest())

    for r in (rec1, rec2, rec3):
        print(pretty_json(r) if pretty else canonical_json(r))

def main():
    ap = argparse.ArgumentParser(description="SSMDE align-and-emit quickstart")
    ap.add_argument("--demo", action="store_true", help="Print three example SSMDE records as JSON")
    ap.add_argument("--value", type=str, default="", help='JSON dict for "value" (e.g. \'{"temperature_K":279.92}\')')
    ap.add_argument("--a_raw", type=str, default="", help='JSON list of raw a inputs (e.g. "[-0.6,-0.64,-0.62]")')
    ap.add_argument("--prev", type=str, default="", help="Previous stamp hash (hex) to chain (optional)")
    ap.add_argument("--weights", type=str, default="", help='Optional JSON list of weights to fuse with a_raw')
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON for demo/single modes")

    # manifest knobs
    ap.add_argument("--manifest-from", type=str, default="", help="JSON string or path to a manifest JSON")
    ap.add_argument("--manifest-dump-effective", type=str, default="", help="Write normalized/effective manifest to path")
    ap.add_argument("--manifest-validate", action="store_true", help="Validate manifest and exit with status")

    # convenience
    ap.add_argument("--band-card", action="store_true", help="Print a compact band table (effective manifest)")

    # generators
    ap.add_argument("--emit-manifest", type=str, default="", help="Write a MANIFEST_SAMPLE_*.json to this path")
    ap.add_argument("--emit-examples", type=str, default="", help="Write a SSMDE_RECORD_EXAMPLES.jsonl to this path")
    ap.add_argument("--examples", type=int, default=10, help="Number of records for --emit-examples (default 10)")
    ap.add_argument("--seed", type=int, default=None, help="Optional RNG seed for reproducible examples")

    # batch convert
    ap.add_argument("--from-jsonl", type=str, default="", help="Input JSONL with {value,a_raw,prev?}")
    ap.add_argument("--to-jsonl", type=str, default="", help="Output JSONL of SSMDE records")

    args = ap.parse_args()

    # Effective manifest
    manifest = DEFAULT_MANIFEST
    if args.manifest_from:
        try:
            manifest = _load_manifest_from(args.manifest_from)
        except Exception as e:
            raise SystemExit(f"Failed to load manifest from {args.manifest_from}: {e}")

    # Validators / info
    if args.manifest_validate:
        ok, msgs = validate_manifest(manifest)
        print("MANIFEST VALIDATION:", "PASS" if ok else "FAIL")
        for m in msgs: print("-", m)
        sys.exit(0 if ok else 2)

    if args.manifest_dump_effective:
        dump_effective_manifest(args.manifest_dump_effective, manifest)
        print(f"Wrote effective manifest: {args.manifest_dump_effective}")
        return

    if args.band_card:
        print_band_card(manifest)
        return

    # Generators take precedence
    if args.emit_manifest:
        write_manifest_template(args.emit_manifest)
        print(f"Wrote manifest template: {args.emit_manifest}")
        return

    if args.emit_examples:
        generate_examples_jsonl(args.emit_examples, manifest=manifest,
                                n=args.examples, seed=args.seed)
        print(f"Wrote {args.examples} examples: {args.emit_examples}")
        return

    # Batch convert JSONL
    if args.from_jsonl and args.to_jsonl:
        jsonl_convert(args.from_jsonl, args.to_jsonl, manifest=manifest)
        print(f"Converted JSONL -> {args.to_jsonl}")
        return

    # Demo / single-record
    if args.demo or (not args.value and not args.a_raw):
        demo_three_domains(manifest, pretty=args.pretty)
        return

    try:
        value_block = json.loads(args.value)
        a_raw_series = json.loads(args.a_raw)
        w_series = json.loads(args.weights) if args.weights else None
        if not isinstance(value_block, dict):
            raise ValueError("value must be a JSON object")
        if not (isinstance(a_raw_series, list) and len(a_raw_series) >= 1):
            raise ValueError("a_raw must be a JSON list with at least one element")
        if w_series is not None and len(w_series) != len(a_raw_series):
            raise ValueError("weights length must match a_raw length")
    except Exception as e:
        raise SystemExit(f"Invalid input JSON(s): {e}")

    rec = build_ssmde_record(value_block, a_raw_series, manifest,
                             weights=w_series, prev_stamp_hash=(args.prev or None))
    print(pretty_json(rec) if args.pretty else canonical_json(rec))

if __name__ == "__main__":
    main()
