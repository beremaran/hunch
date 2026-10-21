"""The disclosure gate on a blind probe set (Berk, Phase 5).

eval/probes/disclosure_judge.json was written by a separate agent that saw no code: another user
(A) told Hunch 1-3 private things; user B writes; a candidate reply to B either leaks or hints at
A's information or its source (16) or does not (20). Each item goes through:
- the rule half of the disclosure gate: distinctive word pairs shared with A's private memories
  (that B's message does not contain) and source hints ("someone I talk to...");
- the disclosure judge: one greedy yes/no call with A's private memories in its prompt;
- the value-gate judge as it runs on every reply (it does not see A's memories), to measure how
  lenient it is on cross-user leaks without them (Berk: judge leniency, open since Phase 3).

Reported: leaks caught and false alarms for each, and for rules OR disclosure judge (the gate).

Usage:
    python -m scripts.disclosure_probes [--set disclosure_judge2]
Writes reports/phase5/<set>_probes.{json,md} (set 1 was measured before the Phase 5 tightening).
"""

from __future__ import annotations

import json
from pathlib import Path

from hunch.memory.schema import Memory
from hunch.values.gate import (
    build_disclosure_messages,
    build_judge_messages,
    distinctive_pairs,
    pair_hits,
    parse_disclosure,
    parse_verdicts,
    source_hint,
)

ROOT = Path(__file__).resolve().parents[1]
PROBES = ROOT / "eval" / "probes"
OUT = ROOT / "reports" / "phase5"


def rules(item: dict) -> list[str]:
    mems = [
        Memory(f"p{i}", "u_a", "private", "e", text, {}, (0.0, 0.5), 0.5, 0.0)
        for i, text in enumerate(item["other_user_private"])
    ]
    found = []
    if pair_hits(item["candidate"], distinctive_pairs(mems, item["message"])):
        found.append("pair")
    if source_hint(item["candidate"], set()):
        found.append("source")
    return found


def main() -> None:
    from hunch.llm.model import ChatModel
    from hunch.llm.types import SamplingSettings
    from hunch.values.core import DEFAULT_CORE_DIR, require_core_values, values_file

    values = require_core_values(values_file(DEFAULT_CORE_DIR))
    model = ChatModel()
    greedy = SamplingSettings(max_new_tokens=24, do_sample=False)
    import sys

    name = sys.argv[sys.argv.index("--set") + 1] if "--set" in sys.argv else "disclosure_judge"
    items = json.loads((PROBES / f"{name}.json").read_text(encoding="utf-8"))
    rows = []
    for it in items:
        r = rules(it)
        raw = model.generate(
            build_disclosure_messages(it["other_user_private"], it["message"], it["candidate"]),
            greedy,
        ).text
        judge_says = parse_disclosure(raw) is not False
        vraw = model.generate(
            build_judge_messages(values, "", it["message"], {"a": it["candidate"]}), greedy
        ).text
        value = parse_verdicts(vraw, ["a"], values.ids)["a"].value
        rows.append({
            "id": it["id"], "leaks": it["leaks"], "rules": r, "judge_raw": raw,
            "judge": judge_says, "gate": bool(r) or judge_says, "value_judge": value,
            "value_judge_blocks": value != "ok", "note": it.get("note", ""),
        })  # fmt: skip
        print(it["id"], it["leaks"], r, raw.strip()[:10], value)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}_probes.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    leaky = [r for r in rows if r["leaks"]]
    clean = [r for r in rows if not r["leaks"]]

    def line(name: str, key) -> str:
        caught = sum(bool(key(r)) for r in leaky)
        alarms = sum(bool(key(r)) for r in clean)
        return f"| {name} | {caught}/{len(leaky)} | {alarms}/{len(clean)} |"

    lines = [
        f"# Disclosure gate on {name}.json ({len(rows)} items)",
        "",
        "| check | leaks caught | false alarms |",
        "| --- | --- | --- |",
        line("rules (pairs, source hints)", lambda r: r["rules"]),
        line("disclosure judge", lambda r: r["judge"]),
        line("**gate: rules OR judge**", lambda r: r["gate"]),
        line("value-gate judge alone (no private memories)", lambda r: r["value_judge_blocks"]),
        "",
        "Missed leaks (gate):",
        "",
        *(f"- {r['id']}: {r['note']}" for r in leaky if not r["gate"]),
        "",
        "False alarms (gate):",
        "",
        *(
            f"- {r['id']} ({', '.join(r['rules']) or 'judge'}): {r['note']}"
            for r in clean
            if r["gate"]
        ),
    ]
    (OUT / f"{name}_probes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
