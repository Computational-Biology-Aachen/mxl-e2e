"""Known, accepted differences: `xfails.toml` maps phase -> model -> check -> reason.

Every entry becomes a strict xfail, so a difference that disappears turns the
suite red until its entry is removed.
"""

from __future__ import annotations

import tomllib

import pytest

from e2e.pipeline import ROOT

XFAILS: dict[str, dict[str, dict[str, str]]] = tomllib.loads(
    (ROOT / "xfails.toml").read_text()
)


def params(phase: str, models: list[str], check: str) -> list[object]:
    """`models` as pytest params, each marked xfail if `xfails.toml` lists it."""
    known = XFAILS.get(phase, {})
    return [
        pytest.param(
            m,
            id=m,
            marks=[pytest.mark.xfail(reason=reason, strict=True)]
            if (reason := known.get(m, {}).get(check))
            else [],
        )
        for m in models
    ]
