"""Invariant 2: the lower layer never reaches a model prompt as content.

Captures every prompt the pipeline sends to the model in a session where memories land in all
layers (upper, lower, capped above the per-turn limit) and the drive vector and hunch flag are
not neutral, then checks that no prompt contains a lower trace, a memory id, an activation or
drive value, or anything from the turn logs. Only the upper memories' summaries, the coarse mood
label and the hunch flag in words may appear.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from hunch.memory.store import MemoryStore
from hunch.observability.turn_log import DETAILS_FILE, TURNS_FILE
from hunch.pipeline.prompt import PERSONA, SUMMARY_PROMPT
from hunch.recall.cues import SYSTEM_PROMPT as CUE_PROMPT
from hunch.values.gate import JUDGE_PROMPT
from tests.fakes import FakeLLM, HashEmbedder
from tests.pipeline_support import DIM, seed_memory

_NUMBER = re.compile(r"-?\d+\.\d+")
STATIC_NUMBERS = set(_NUMBER.findall(CUE_PROMPT + JUDGE_PROMPT + PERSONA + SUMMARY_PROMPT))


def _all_prompt_text(llm: FakeLLM) -> str:
    return "\n".join(m["content"] for p in llm.prompts for m in p)


def test_no_lower_trace_drive_value_or_log_content_in_any_prompt(
    make, pipe_store: MemoryStore, tmp_path: Path
) -> None:
    # Upper candidates: 4 strong song memories; the per-turn cap (3) pushes one into "capped".
    for i in range(4):
        seed_memory(pipe_store, f"up{i}", f"UPPER-{i}: sang tune {i} at the party.",
                    {f"song:tune_{i}": 1.0}, 2, affect=(-0.8, 0.9), salience=0.9)  # fmt: skip
    # Lower layer: emotional, sharing only the weak emotion cue, between the thresholds.
    for i in range(3):
        seed_memory(pipe_store, f"lo{i}", f"LOWER-{i}: the night everything went wrong.",
                    {"emotion:sad": 1.0}, 60, affect=(-0.9, 0.9), salience=0.6)  # fmt: skip
    cues = [{"type": "song", "value": f"tune {i}", "strength": 1.0} for i in range(4)]
    cues.append({"type": "emotion", "value": "sad", "strength": 1.0})
    llm = FakeLLM(cues=cues)
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    results = []
    for text in ("tune 0, tune 1, tune 2 and tune 3 played and I felt sad", "still sad"):
        r = pipe.turn(session, text)
        pipe.after_reply(session, r)
        results.append(r)

    first = results[0]
    layers = {a["memory"]: a for a in first.details["activation"]}
    upper = {m for m, a in layers.items() if a["layer"] == "upper"}
    hidden = {m for m, a in layers.items() if a["layer"] != "upper"}
    assert len(upper) == 3 and any(a["capped"] for a in layers.values())
    assert any(layers[m]["layer"] == "lower" for m in hidden if m.startswith("lo"))
    assert first.log["hunch"] is not None and first.log["drive"]["warmth"] < 0.5

    text = _all_prompt_text(llm)
    for mid in hidden:
        assert pipe_store.memory(mid).summary not in text, mid
    for mid in layers:
        assert mid not in text  # memory ids never reach a prompt
    # No number from the pipeline at all: every decimal in a prompt comes from a fixed template.
    assert set(_NUMBER.findall(text)) <= STATIC_NUMBERS
    for r in results:
        log = r.log
        for word in ("warmth", "caution", "curiosity", "drive", "activation", r.turn_id):
            assert word not in text.casefold()
        if log["hunch"]:
            assert log["hunch"]["id"] not in text
    # Nothing from the log files either.
    for name in (TURNS_FILE, DETAILS_FILE):
        for line in (tmp_path / "logs" / name).read_text(encoding="utf-8").splitlines():
            assert json.loads(line)["turn_id"] not in text
    # What is allowed: the upper summaries, the mood label and the hunch flag in words.
    for mid in upper:
        assert pipe_store.memory(mid).summary in text
    assert "How you feel right now: calm." in text
    assert "hunch about this" in text and "just a hunch" in text
