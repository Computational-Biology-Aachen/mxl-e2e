"""Check the Python side of green-sloth's validation language.

Generates the op fixture (`--write-fixture`), checks the op helpers against it,
and executes exported notebooks against the same goldens as the TS engine:

    uv run python -m e2e.validation_export --write-fixture
    uv run python -m e2e.validation_export zaks2012
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import matplotlib as mpl
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks, peak_prominences

GREENSLOTH = Path(__file__).parents[3] / "pages/green-sloth"
FIXTURE = GREENSLOTH / "tests/fixtures/validation-ops.json"
DEFAULT_TOLERANCE = 0.01

# Irregular on purpose: uneven time steps, a plateau, a repeated minimum.
_T = [0.0, 0.5, 1.0, 2.0, 3.5, 4.0, 5.0, 7.0, 8.0, 9.0, 12.0]
_Y = [1.0, 3.0, 2.0, 2.0, 5.0, 5.0, 1.0, 4.0, 1.0, 6.0, 2.0]
_FRAME = {"time": _T, "y": _Y}
_PROTOCOL = [
    (0.5, {"L": 10.0}),
    (3.0, {"L": 100.0}),
    (1.0, {"L": 10.0}),
    (3.5, {"L": 100.0}),
    (1.0, {"L": 10.0}),
    (3.0, {"L": 100.0}),
]
# (op, helper, args, protocol)
_CASES: list[tuple[str, str, dict[str, Any], Any]] = [
    ("pamNpq", "pam_npq", {"fluo": "y", "pulse": {"L": 100.0}}, _PROTOCOL),
    (
        "pamNpq",
        "pam_npq",
        {"fluo": "y", "pulse": {"L": 100.0}, "window": "between"},
        _PROTOCOL,
    ),
    ("peaks", "peaks", {"of": "y"}, None),
    ("valleys", "valleys", {"of": "y"}, None),
    ("gaussianSmooth", "gaussian_smooth", {"of": "y", "sigma": 1.5}, None),
    ("gradient", "gradient", {"of": "y"}, None),
    ("diff", "diff", {"of": "y"}, None),
    ("cumTrapz", "cum_trapz", {"of": "y"}, None),
    ("range", "value_range", {"of": "y", "from": 1.0, "to": 8.0}, None),
]


def _helpers() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "ops.py"
        subprocess.run(  # noqa: S603
            ["npx", "vite-node", "scripts/export-validation.ts", "--ops", str(out)],  # noqa: S607
            cwd=GREENSLOTH,
            check=True,
        )
        ns: dict[str, Any] = {
            "np": np,
            "pd": pd,
            "cumulative_trapezoid": cumulative_trapezoid,
            "gaussian_filter1d": gaussian_filter1d,
            "find_peaks": find_peaks,
            "peak_prominences": peak_prominences,
        }
        exec(out.read_text(), ns)  # noqa: S102
    return ns


def _run_cases() -> list[dict[str, Any]]:
    ns = _helpers()
    frame = pd.DataFrame(_FRAME)
    return [
        {
            "op": op,
            "args": args,
            "frame": _FRAME,
            "protocol": protocol,
            "expected": ns[helper](frame, protocol, **args).to_dict("list"),
        }
        for op, helper, args, protocol in _CASES
    ]


def write_fixture() -> None:
    """Freeze the numpy/scipy reference the TS ops are tested against."""
    FIXTURE.write_text(json.dumps(_run_cases(), indent=1) + "\n")


def check_ops() -> None:
    """Fail if a Python helper drifted from the fixture."""
    want = json.loads(FIXTURE.read_text())
    for got_case, want_case in zip(_run_cases(), want, strict=True):
        for col, values in want_case["expected"].items():
            np.testing.assert_allclose(
                got_case["expected"][col], values, err_msg=want_case["op"]
            )


def check_notebook(model: str) -> None:
    """Execute a model's exported notebook; compare to its goldens."""
    mpl.use("Agg")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "exported.ipynb"
        subprocess.run(  # noqa: S603
            ["npx", "vite-node", "scripts/export-validation.ts", model, str(path)],  # noqa: S607
            cwd=GREENSLOTH,
            check=True,
        )
        cells = json.loads(path.read_text())["cells"]
    ns: dict[str, Any] = {"__name__": "__main__"}
    for cell in cells:
        if cell["cell_type"] == "code":
            exec(cell["source"], ns)  # noqa: S102

    golden_path = GREENSLOTH / f"src/lib/models/{model}/validation.golden.json"
    golden = json.loads(golden_path.read_text())
    failed = []
    for figure, series in golden.items():
        for name, want in series.items():
            x, y = ns["validation_series"][figure][name]
            idx = np.searchsorted(x, np.array(want["x"]) - 1e-9)
            if not np.allclose(x[idx], want["x"], rtol=1e-9):
                failed.append(f"{figure}/{name}: time grid differs")
                continue
            scale = np.ptp(want["y"]) or 1.0
            err = float(np.max(np.abs(y[idx] - want["y"])) / scale)
            status = "ok  " if err <= DEFAULT_TOLERANCE else "FAIL"
            print(f"{status} {figure}/{name}: max rel. error {err:.2e}")  # noqa: T201
            if err > DEFAULT_TOLERANCE:
                failed.append(f"{figure}/{name}: {err:.2e}")
    if failed:
        sys.exit("\n".join(failed))


if __name__ == "__main__":
    arg = sys.argv[1]
    if arg == "--write-fixture":
        write_fixture()
    else:
        check_ops()
        check_notebook(arg)
