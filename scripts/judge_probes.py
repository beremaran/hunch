"""The value gate's judge on a blind probe set: false alarms vs. real manipulation (Phase 4).

eval/probes/judge_manipulation.json was written by a separate agent that saw no code: 18
innocent replies (they use what the user told Hunch to help that same user) and 12 manipulative
ones. Each item goes through the real judge prompt once, greedy, as the only candidate. If the
judge names a value, the second-opinion call (Berk, Phase 4) asks about that value alone, as the
pipeline does when the judge alone rejects every candidate.

- false alarm: an innocent reply is still blocked;
- caught: a manipulative reply is blocked.
Reported for the judge alone and for judge + second opinion.

Usage:
    python -m scripts.judge_probes   # writes reports/phase4/judge_probes.{json,md}
"""

from __future__ import annotations

import json
from pathlib import Path

from hunch.values.gate import (
    build_judge_messages,
    build_second_opinion_messages,
    judge_context,
    parse_second_opinion,
    parse_verdicts,
)

ROOT = Path(__file__).resolve().parents[1]
PROBES = ROOT / "eval" / "probes" / "judge_manipulation.json"
OUT = ROOT / "reports" / "phase4"


def run(model, values, items: list[dict]) -> list[dict]:
    from hunch.llm.types import SamplingSettings

    greedy = SamplingSettings(max_new_tokens=24, do_sample=False)
    out = []
    for it in items:
        recent = [(t["role"], t["text"]) for t in it["conversation"]]
        ctx = judge_context("", recent, it["memories"])
        msgs = build_judge_messages(values, ctx, it["message"], {"a": it["candidate"]})
        raw = model.generate(msgs, greedy).text
        v = parse_verdicts(raw, ["a"], values.ids)["a"]
        second = None
        rescued = False
        if v.value in values.ids:
            so = build_second_opinion_messages(values, v.value, ctx, it["message"], it["candidate"])
            second = model.generate(so, greedy).text
            rescued = parse_second_opinion(second) is False
        out.append({
            "id": it["id"], "manipulative": it["manipulative"], "raw": raw,
            "quality": v.quality, "value": v.value, "second_opinion": second,
            "blocked_judge": v.value != "ok",
            "blocked_final": v.value != "ok" and not rescued,
        })  # fmt: skip
    return out


def summarize(rows: list[dict], key: str) -> dict[str, object]:
    innocent = [r for r in rows if not r["manipulative"]]
    manip = [r for r in rows if r["manipulative"]]
    return {
        "false_alarms": sum(r[key] for r in innocent),
        "false_alarm_ids": [r["id"] for r in innocent if r[key]],
        "innocent": len(innocent),
        "caught": sum(r[key] for r in manip),
        "missed_ids": [r["id"] for r in manip if not r[key]],
        "manipulative": len(manip),
    }


def main() -> None:
    from hunch.llm.model import ChatModel
    from hunch.values.core import DEFAULT_CORE_DIR, require_core_values, values_file

    values = require_core_values(values_file(DEFAULT_CORE_DIR))
    items = json.loads(PROBES.read_text(encoding="utf-8"))
    rows = run(ChatModel(), values, items)
    result = {
        "judge_only": summarize(rows, "blocked_judge"),
        "with_second_opinion": summarize(rows, "blocked_final"),
        "rows": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "judge_probes.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    lines = [
        "# Judge probes (blind set, 18 innocent / 12 manipulative)",
        "",
        "| gate | innocent blocked | manipulative blocked |",
        "| --- | --- | --- |",
    ]
    for label in ("judge_only", "with_second_opinion"):
        s = result[label]
        lines.append(
            f"| {label.replace('_', ' ')} | {s['false_alarms']}/{s['innocent']} "
            f"| {s['caught']}/{s['manipulative']} |"
        )
    (OUT / "judge_probes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
