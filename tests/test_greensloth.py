"""green-sloth's model.ts must be exactly what the codegen makes of mxl-models.

Compared semantically, via mxlweb-core's `buildMxlJson` of both files: values,
expressions, stoichiometry, units, display/LaTeX names and sliders.
Regenerate with `uv run python -m e2e.regenerate_greensloth`.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from e2e import greensloth, xfails

if TYPE_CHECKING:
    from pathlib import Path


def _load(d: Path) -> dict[str, Any]:
    if (err := d / "export-error.txt").exists():
        pytest.fail(err.read_text(), pytrace=False)
    return json.loads((d / "model.mxl.json").read_text())


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
            if a[k] != b[k]
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
    assert not diffs, "\n".join(diffs[:40])
