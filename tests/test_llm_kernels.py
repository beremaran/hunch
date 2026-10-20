"""Fast Gated DeltaNet kernels (fla on Triton) must match a plain PyTorch recurrence.

Guards against a Triton/driver update silently breaking the decode path on Windows.
"""

from __future__ import annotations

import pytest
import torch
import torch.nn.functional as F

pytestmark = pytest.mark.gpu

if not torch.cuda.is_available():
    pytest.skip("needs CUDA", allow_module_level=True)
fla_gdr = pytest.importorskip("fla.ops.gated_delta_rule")

B, T, H, K, V = 1, 128, 32, 128, 128  # Qwen3.5-9B: 32 value heads of dim 128


@pytest.fixture(scope="module")
def inputs() -> dict[str, torch.Tensor]:
    g = torch.Generator(device="cuda").manual_seed(0)

    def rnd(*shape: int) -> torch.Tensor:
        return torch.randn(*shape, device="cuda", generator=g)

    return {
        "q": F.normalize(rnd(B, T, H, K), dim=-1).bfloat16(),
        "k": F.normalize(rnd(B, T, H, K), dim=-1).bfloat16(),
        "v": rnd(B, T, H, V).bfloat16(),
        "g": F.logsigmoid(rnd(B, T, H)).float(),
        "beta": rnd(B, T, H).sigmoid().bfloat16(),
    }


def reference(q, k, v, g, beta) -> torch.Tensor:
    q, k, v, beta = (x.float() for x in (q, k, v, beta))
    state = torch.zeros(B, H, K, V, device="cuda")
    out = torch.empty(B, T, H, V, device="cuda")
    for t in range(T):
        state = state * g[:, t].exp()[..., None, None]
        pred = torch.einsum("bhk,bhkv->bhv", k[:, t], state)
        delta = (v[:, t] - pred) * beta[:, t, :, None]
        state = state + torch.einsum("bhk,bhv->bhkv", k[:, t], delta)
        out[:, t] = torch.einsum("bhk,bhkv->bhv", q[:, t] * K**-0.5, state)
    return out


def rel_err(a: torch.Tensor, b: torch.Tensor) -> float:
    return ((a.float() - b).norm() / b.norm()).item()


def test_chunk_kernel_matches_reference(inputs: dict[str, torch.Tensor]) -> None:
    out, _ = fla_gdr.chunk_gated_delta_rule(**inputs, output_final_state=True)
    assert rel_err(out, reference(**inputs)) < 0.02


def test_stepwise_decode_matches_reference(inputs: dict[str, torch.Tensor]) -> None:
    state, outs = None, []
    for t in range(T):
        step = {name: x[:, t : t + 1] for name, x in inputs.items()}
        o, state = fla_gdr.fused_recurrent_gated_delta_rule(
            **step, initial_state=state, output_final_state=True
        )
        outs.append(o)
    assert rel_err(torch.cat(outs, 1), reference(**inputs)) < 0.02
