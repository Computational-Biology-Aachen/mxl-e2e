"""green-sloth's model.ts must be exactly what the codegen makes of mxl-models.

Compared semantically, via mxlweb-core's `buildMxlJson` of both files: values,
expressions, stoichiometry, units, display/LaTeX names and sliders.
Numbers match to 1e-12 relative: data computed with numpy (pfennig2024's
`np.exp` light spectra) differs in the last bit between CPUs.
Regenerate with `uv run python -m e2e.regenerate_greensloth`.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any

import pytest

from e2e import greensloth, xfails

if TYPE_CHECKING:
    from pathlib import Path


def _load(d: Path) -> dict[str, Any]:
    if (err := d / "export-error.txt").exists():
        pytest.fail(err.read_text(), pytrace=False)
    return json.loads((d / "model.mxl.json").read_text())


def _same(a: object, b: object) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        if isinstance(a, bool) or isinstance(b, bool):
            return a == b
        if not isinstance(a, int | float) or not isinstance(b, int | float):
            return False
        return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-300)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(map(_same, a, b))
    return a == b


def _diff(committed: dict[str, Any], generated: dict[str, Any]) -> list[str]:
    diffs = []
    for section in sorted(committed.keys() | generated.keys()):
        a, b = committed.get(section, {}), generated.get(section, {})
        if missing := sorted(b.keys() - a.keys()):
            diffs.append(f"{section}: only generated {missing}")
        if extra := sorted(a.keys() - b.keys()):
            diffs.append(f"{section}: only committed {extra}")
        diffs.extend(
            f"{section}.{k}: differs"
            for k in sorted(a.keys() & b.keys())
            if not _same(a[k], b[k])
        )
    return diffs


@pytest.mark.parametrize(
    "slug", xfails.params("greensloth", list(greensloth.SLUGS), "generated")
)
def test_generated(slug: str, greensloth_json: dict[str, tuple[Path, Path]]) -> None:
    committed_dir, generated_dir = greensloth_json[slug]
    committed = _load(committed_dir)["model"]
    generated = _load(generated_dir)["model"]
    diffs = _diff(committed, generated)
    committed_data, generated_data = (
        json.loads(p.read_text()) if (p := d / "data.mxl.json").exists() else {}
        for d in (committed_dir, generated_dir)
    )
    diffs += _diff({"data": committed_data}, {"data": generated_data})
    assert not diffs, "\n".join(diffs[:40])
