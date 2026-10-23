"""Filler labels (Phase 7, nightly step 6b): how well does the model tell filler from meaningful?
Needs the GPU. Target from the decisions table: >= 90% of filler caught, <= 5% of meaningful
memories marked as filler.

    python -m scripts.filler_probes   # writes reports/phase7/filler_probes.{json,md}
"""

from __future__ import annotations

import json
from pathlib import Path

from hunch.consolidation.fade import said
from hunch.consolidation.filler import FILLER_MAX_NEW_TOKENS, build_filler_messages, parse_filler
from hunch.llm.model import ChatModel
from hunch.llm.types import SamplingSettings

ROOT = Path(__file__).resolve().parent.parent
PROBES = ROOT / "eval" / "probes" / "filler.json"
OUT = ROOT / "reports" / "phase7"


def main() -> None:
    cases = json.loads(PROBES.read_text(encoding="utf-8"))["cases"]
    model = ChatModel()
    greedy = SamplingSettings(max_new_tokens=FILLER_MAX_NEW_TOKENS, do_sample=False)
    rows = []
    for c in cases:
        raw = model.generate(build_filler_messages(said(c["summary"]), None), greedy).text
        rows.append({**c, "raw": raw, "filler": parse_filler(raw)})
    filler = [r for r in rows if r["label"] == "filler"]
    meaningful = [r for r in rows if r["label"] == "meaningful"]
    caught = sum(r["filler"] for r in filler)
    false = sum(r["filler"] for r in meaningful)
    summary = {"filler_caught": f"{caught}/{len(filler)}",
               "meaningful_faded": f"{false}/{len(meaningful)}"}  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "filler_probes.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8"
    )
    lines = ["# Filler probes", "", f"Filler caught: {caught}/{len(filler)}. "
             f"Meaningful faded: {false}/{len(meaningful)}.", "", "## Errors", ""]  # fmt: skip
    for r in rows:
        if r["filler"] != (r["label"] == "filler"):
            lines.append(f"- {r['id']} ({r['label']}, model: {r['raw'].strip()!r}): "
                         f"{said(r['summary'])} [{r['note']}]")  # fmt: skip
    (OUT / "filler_probes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
