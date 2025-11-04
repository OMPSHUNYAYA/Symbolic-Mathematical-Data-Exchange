SSMDE — Shunyaya Symbolic Mathematical Data Exchange

License: Open standard, open source. (See “Full License / Usage” below.)

Version: Public Demo Bundle (v2.1)

Intro (brief)

This bundle provides a minimal, observation-only data exchange standard.
Every record carries five inseparable parts so truth can travel with policy and proof:

value — your original signal(s), unchanged

align — bounded stability/risk dial in (-1,+1)

band — human label from a declared policy (manifest)

manifest_id — which policy/version defined these cutpoints/actions

stamp — portable, chainable proof of when/what was declared

Dictionary-Optional Design (manifest = contract)

No global dictionary is required. Semantics (bands, action windows, fusion knobs) live in the manifest.
Verification is structural/math + stamp chain; SSMS naming can be added later for cross-vendor search.

Core definitions (ASCII)

Align (canonical fusion):

a_c := clamp(a_raw, -1+eps_a, +1-eps_a)
u   := atanh(a_c)
U  += w * u ; W += w
align := tanh( U / max(W, eps_w) )


Band mapping (policy):
Your manifest defines labeled ranges over align, each with an action/time window.
Example (sorted by align_max): CRITICAL < AMBER < A0 < A++

Stamp (portable chain):
Stamp exactly the content block:

{ "value": {...}, "align": <float>, "band": "<label>", "manifest_id": "<id>" }


Format (single line):

SSMCLOCK1|<utc_iso>|theta=<deg>|sha256=<hex>|prev=<hex|NONE>


sha256 is over canonical_json(content_block) (sorted keys, tight separators)

prev = sha256(previous_stamp) to make timeline manipulation visible

Folder layout
.
├─ docs/
│  ├─ SSMDE_ver2.1.pdf
│  └─ Brief-SSMDE_ver2.1.pdf
├─ tools/
│  ├─ ssmde_align_core.py
│  └─ ssmde_verify.py
├─ manifests/
│  ├─ MANIFEST_SAMPLE_PLANT_A_BEARING_SAFETY_v7.json
│  └─ EFFECTIVE_MANIFEST.json
├─ guides/
│  ├─ GETTING_STARTED_SSMDE.txt
│  ├─ MANIFEST_AND_BANDS_SSMDE.txt
│  └─ README_PUBLIC_SSMDE.txt
├─ examples/
│  └─ OUTPUT_SSMDE.jsonl
└─ evidence/
   └─ (optional: partner/pack templates)

Quick Start
Windows
python tools\ssmde_align_core.py --demo --pretty
python tools\ssmde_align_core.py --emit-manifest "manifests\MANIFEST_SAMPLE.json"
python tools\ssmde_align_core.py --emit-examples "examples\SSMDE_RECORD_EXAMPLES.jsonl" --examples 10 --seed 42
python tools\ssmde_align_core.py --manifest-from "manifests\MANIFEST_SAMPLE.json" --manifest-validate
python tools\ssmde_align_core.py --manifest-from "manifests\MANIFEST_SAMPLE.json" --band-card
python tools\ssmde_align_core.py --from-jsonl "examples\INPUT.jsonl" --to-jsonl "examples\OUTPUT_SSMDE.jsonl"
python tools\ssmde_verify.py

macOS / Linux
python3 tools/ssmde_align_core.py --demo --pretty
python3 tools/ssmde_align_core.py --emit-manifest "manifests/MANIFEST_SAMPLE.json"
python3 tools/ssmde_align_core.py --emit-examples "examples/SSMDE_RECORD_EXAMPLES.jsonl" --examples 10 --seed 42
python3 tools/ssmde_align_core.py --manifest-from "manifests/MANIFEST_SAMPLE.json" --manifest-validate
python3 tools/ssmde_align_core.py --manifest-from "manifests/MANIFEST_SAMPLE.json" --band-card
python3 tools/ssmde_align_core.py --from-jsonl "examples/INPUT.jsonl" --to-jsonl "examples/OUTPUT_SSMDE.jsonl"
python3 tools/ssmde_verify.py


Expected output (demo)

{
  "value": { ... },
  "align": <float in (-1,+1)>,
  "band": "A0|AMBER|CRITICAL|A++",
  "manifest_id": "YOUR_POLICY_vN",
  "stamp": "SSMCLOCK1|2025-11-03T09:31:45Z|theta=142.88|sha256=...|prev=..."
}

Verification / CI-style check

Run:

python tools/ssmde_verify.py


You should see: ALL CHECKS PASSED

This confirms:

Align stays strictly bounded: -1 < align < 1

Fusion is order-invariant (batch vs reversed)

Band mapping matches manifest cutpoints

manifest_id exists; stamp format is correct

Chain discipline: prev = sha256(previous_stamp)

Manifest Lock (before deployment)

Declare once, then freeze (example fields):

manifest_id: PLANT_A_BEARING_SAFETY_v7
align_computation:
  eps_a=1e-6
  eps_w=1e-12
  weights="uniform"
bands (sorted by align_max):
  CRITICAL: (-1.00, -0.80] → action="stop/evacuate"   window="human respond in <= 10 min"
  AMBER   : (-0.80, -0.30] → action="inspect"        window="inspect in <= 30 min"
  A0      : (-0.30,  0.70] → action="monitor only"   window="inspect in <= 8h"
  A++     : ( 0.70,  1.00] → action="no action"      window="none"
escalation_owner="Plant Safety Officer"
policy_author="Reliability Board"
policy_version="v7"
revision_notes="Updated AMBER window from 60 min to 30 min"


Do not silently change knobs mid-run. If you change a cutpoint or window, bump policy_version and document why.

Pooling / fleets

When combining many sources, use rapidity-space pooling so one rogue signal cannot dominate:

a_c      := clamp(a_in, -1+eps_a, +1-eps_a)
u_i      := atanh(a_c_i)
U        := sum_i( w_i * u_i )
W        := max( sum_i( w_i ), eps_w )
a_pooled := tanh( U / W )

Examples

Single record (canonical JSON; compact)

{"value":{"temperature_K":279.92,"a_phase":-0.62},"align":-0.6202688929891665,"band":"AMBER","manifest_id":"PLANT_A_BEARING_SAFETY_v7","stamp":"SSMCLOCK1|2025-11-03T09:31:45Z|theta=142.88|sha256=bca3e9f492ded295defcdbdaa0abc92d17793ed46d0190333d0f6efe5c1486f1|prev=NONE"}


Batch JSONL conversion (input → output)

python tools/ssmde_align_core.py --from-jsonl "examples/INPUT.jsonl" --to-jsonl "examples/OUTPUT_SSMDE.jsonl"


One-line chain verification (Windows CMD)

python -c "import json,hashlib; L=open('examples\\OUTPUT_SSMDE.jsonl','r',encoding='utf-8').read().splitlines(); s0=json.loads(L[0])['stamp']; prev1=json.loads(L[1])['stamp'].split('|')[-1].split('=')[1]; h0=hashlib.sha256(s0.encode()).hexdigest(); print('CHAIN OK' if h0==prev1 else 'MISMATCH')"

Stamp Spec (summary)
SSMCLOCK1|<utc_iso>|theta=<deg>|sha256=<hex>|prev=<hex|NONE>


sha256 over canonical_json({value,align,band,manifest_id})

prev = sha256(previous_stamp) to expose timeline edits

theta is informative; utc_iso is authoritative time

Full License / Usage

Open standard / open source.
May be implemented by any organization — public, industrial, municipal, national, academic, commercial, or off-world habitat — with no registration or fees, 
provided formulas and stamp are implemented exactly as declared in a published manifest.

Minimum citation requirement:
Cite the concept name “Shunyaya Symbolic Mathematical Data Exchange (SSMDE)” when implementing or adapting.

Non-exclusivity:
Implementations are independent. No central registry or maintainer approval is required.
No implementer may claim exclusive ownership, stewardship, endorsement, or representation of the standard.

Integrity requirement:
The alignment fusion (clamp → atanh → accumulate → tanh), band cutpoints, action windows, and stamp discipline must preserve their defined meaning.
If you alter any formula, cutpoint, or window, you must clearly declare that change in your manifest and downstream documentation.

Warranty / Safety disclaimer:
This bundle is provided strictly “as-is,” with no warranty and no safety guarantee.
This is an observation-only symbolic layer and governance scaffold.
Do not use SSMDE as the sole gate in life-critical systems without independent verification and domain-appropriate redundancies.

Quick Links

Docs: docs/SSMDE_ver2.1.pdf, docs/Brief-SSMDE_ver2.1.pdf

Tools: tools/ssmde_align_core.py, tools/ssmde_verify.py

Guides: guides/GETTING_STARTED_SSMDE.txt, guides/MANIFEST_AND_BANDS_SSMDE.txt

Examples: examples/OUTPUT_SSMDE.jsonl

Manifests: manifests/MANIFEST_SAMPLE_PLANT_A_BEARING_SAFETY_v7.json, manifests/EFFECTIVE_MANIFEST.json