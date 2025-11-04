# SSMDE — Shunyaya Symbolic Mathematical Data Exchange
*Portable truth. Verifiable data. Human-aligned governance.*

[![License — Open Standard / Open Source](https://img.shields.io/badge/license-Open%20Standard%20%2F%20Open%20Source-brightgreen?style=flat&logo=open-source-initiative)](#license--usage)
[![SSMDE Verification](https://github.com/OMPSHUNYAYA/Symbolic-Mathematical-Data-Exchange/actions/workflows/verify.yml/badge.svg)](https://github.com/OMPSHUNYAYA/Symbolic-Mathematical-Data-Exchange/actions/workflows/verify.yml)

**Executive overview**  
SSMDE is an open, vendor-neutral way to move truth between systems. 
Each record travels with its stability dial, policy label, policy ID, and a stamped chain — so decisions are auditable, timelines are defensible, and integration is simple. 
*Observation-only.*

---

## Quick Links
- **Docs:** [`docs/SSMDE_ver2.1.pdf`](docs/SSMDE_ver2.1.pdf) · [`docs/Brief-SSMDE_ver2.1.pdf`](docs/Brief-SSMDE_ver2.1.pdf)
- **Tools:** [`tools/ssmde_align_core.py`](tools/ssmde_align_core.py) · [`tools/ssmde_verify.py`](tools/ssmde_verify.py)
- **Guides:** [`guides/GETTING_STARTED_SSMDE.txt`](guides/GETTING_STARTED_SSMDE.txt) · [`guides/MANIFEST_AND_BANDS_SSMDE.txt`](guides/MANIFEST_AND_BANDS_SSMDE.txt) · [`guides/README_PUBLIC_SSMDE.txt`](guides/README_PUBLIC_SSMDE.txt)
- **Manifests:** [`manifests/MANIFEST_SAMPLE_PLANT_A_BEARING_SAFETY_v7.json`](manifests/MANIFEST_SAMPLE_PLANT_A_BEARING_SAFETY_v7.json) · [`manifests/EFFECTIVE_MANIFEST.json`](manifests/EFFECTIVE_MANIFEST.json)
- **Examples:** [`examples/OUTPUT_SSMDE.jsonl`](examples/OUTPUT_SSMDE.jsonl)

---

## Core definitions (ASCII)

**Align (canonical fusion)**  
`a_c := clamp(a_raw, -1+eps_a, +1-eps_a)`  
`u := atanh(a_c)`  
`U += w * u ; W += w`  
`align := tanh( U / max(W, eps_w) )`

**Band mapping (policy)**  
Your manifest defines labeled ranges over `align`, each with an action/time window.  
Example order (by `align_max`): `CRITICAL < AMBER < A0 < A++`

**Stamp (portable chain)**  
Stamp exactly this content block:  
`{ "value": {...}, "align": <float>, "band": "<label>", "manifest_id": "<id>" }`  
Format (single line):  
`SSMCLOCK1|<utc_iso>|theta=<deg>|sha256=<hex>|prev=<hex|NONE>`  
- `sha256` is over canonical JSON of the content block (sorted keys, tight separators)  
- `prev = sha256(previous_stamp)` exposes timeline edits

**Record shape (canonical JSON; compact)**  
`{"value":{"temperature_K":279.92,"a_phase":-0.62},"align":-0.6202688929891665,"band":"AMBER","manifest_id":"PLANT_A_BEARING_SAFETY_v7","stamp":"SSMCLOCK1|2025-11-03T09:31:45Z|theta=142.88|sha256=bca3e9f492ded295defcdbdaa0abc92d17793ed46d0190333d0f6efe5c1486f1|prev=NONE"}`

---

## Quick Start

Run a local demo to see how `align`, `band`, and `stamp` are computed.

### Windows
python tools\ssmde_align_core.py --demo --pretty
python tools\ssmde_verify.py

### macOS / Linux
python3 tools/ssmde_align_core.py --demo --pretty
python3 tools/ssmde_verify.py

You should see a sample record with a bounded `align` (−1 < align < +1), correct `band` mapping, and valid `stamp` chain — ending with:

**ALL CHECKS PASSED**

---

## Verification and Manifest Lock

After running:
python tools/ssmde_verify.py

you should see:

**ALL CHECKS PASSED**

This confirms:
- `align` stays strictly bounded (−1 < align < 1)  
- Fusion is order-invariant (batch == reversed)  
- Band mapping matches manifest cutpoints  
- Each record carries `manifest_id`, correct stamp format, and `prev = sha256(previous_stamp)`

---

### Manifest Lock
Declare once, then freeze.  
Example:
manifest_id: PLANT_A_BEARING_SAFETY_v7
eps_a=1e-6
eps_w=1e-12
weights="uniform"
bands:
CRITICAL (-1.00, -0.80] → stop/evacuate ≤ 10 min
AMBER (-0.80, -0.30] → inspect ≤ 30 min
A0 (-0.30, 0.70] → monitor ≤ 8 h
A++ ( 0.70, 1.00] → no action

If you adjust any range or timing, bump the `policy_version` and document the reason.  
Consistency of the manifest is what gives SSMDE its evidential strength.

---

## License / Usage

**Open standard · Open source**  
Any organization — public, industrial, municipal, academic, or commercial — may implement SSMDE with no registration or fees, provided the formulas and stamp are implemented exactly as declared in a published manifest.

**Minimum citation requirement**  
When adapting or deploying, cite the concept name **“Shunyaya Symbolic Mathematical Data Exchange (SSMDE)”** as the origin of the symbolic mathematical data-exchange approach.

**Non-exclusivity**  
Implementations are independent. No central registry or approval is required.  
No individual or organization may claim exclusive ownership, endorsement, or stewardship of the standard.

**Integrity requirement**  
The alignment fusion (`clamp -> atanh -> accumulate -> tanh`), band cutpoints, action windows, and stamp discipline must preserve their defined meaning.  
If any formula or range is modified, the change must be clearly declared in your manifest and downstream documentation.

**Warranty / Safety disclaimer**  
Provided strictly *“as-is.”*  
This is an **observation-only** symbolic layer and governance scaffold.  
Do not use SSMDE as the sole gate in life-critical systems without independent verification and domain-appropriate redundancies.

---

## Topics

Shunyaya Symbolic Mathematical Data Exchange (SSMDE), symbolic data exchange, open standard, auditability, manifest discipline, bounded alignment, tamper-evident stamping, portable governance layer, observation-only framework.


