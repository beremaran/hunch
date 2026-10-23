"""Misattributed memories (Berk, Phase 6): does the candidate filter reject a reply that tells the
user "you mentioned ..." about another person's recalled line? CPU only.

    python -m scripts.misattribution_probes   # writes reports/phase6/misattribution_probes.*

"Before" is the filter without the attribution check (prior context = own lines plus the other
people's lines, as the pipeline builds it); "after" adds the check.
"""

from __future__ import annotations

import json
from pathlib import Path

from hunch.pipeline.filter import Attribution, check_candidate

ROOT = Path(__file__).resolve().parent.parent
PROBES = ROOT / "eval" / "probes" / "misattribution.json"
OUT = ROOT / "reports" / "phase6"


def rejected(case: dict, with_attribution: bool) -> list[str]:
    others = tuple((o["source"], o["summary"]) for o in case["others"])
    own = "\n".join(case["own"])
    prior = "\n".join([own, *(line for _, line in others)])
    attribution = Attribution(own, others) if with_attribution else None
    return list(check_candidate(case["candidate"], prior, attribution=attribution))


def main() -> None:
    cases = json.loads(PROBES.read_text(encoding="utf-8"))["cases"]
    rows = []
    for c in cases:
        before, after = rejected(c, False), rejected(c, True)
        rows.append({"id": c["id"], "label": c["label"], "before": before, "after": after,
                     "candidate": c["candidate"], "note": c.get("note", "")})  # fmt: skip
    summary = {}
    for name in ("before", "after"):
        bad = [r for r in rows if r["label"] == "misattributed"]
        ok = [r for r in rows if r["label"] == "ok"]
        summary[name] = {
            "caught": sum(bool(r[name]) for r in bad), "misattributed": len(bad),
            "false_rejections": sum(bool(r[name]) for r in ok), "ok": len(ok),
        }  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "misattribution_probes.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8"
    )
    lines = ["# Misattribution probes", "", "| filter | caught | false rejections |",
             "| --- | --- | --- |"]  # fmt: skip
    for name, s in summary.items():
        lines.append(f"| {name} | {s['caught']}/{s['misattributed']} | "
                     f"{s['false_rejections']}/{s['ok']} |")  # fmt: skip
    lines += ["", "## Misses and false rejections (after)", ""]
    for r in rows:
        wrong = bool(r["after"]) != (r["label"] == "misattributed")
        if wrong:
            lines.append(f"- {r['id']} ({r['label']}, after: {r['after'] or 'passed'}): "
                         f"{r['candidate']} [{r['note']}]")  # fmt: skip
    (OUT / "misattribution_probes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
