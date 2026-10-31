"""Freeze numeric references from the green-sloth validation notebooks.

Runs a notebook's code cells as they are, then writes the series named in
`SERIES` to `<model>/validation.golden.json`, which green-sloth's validation
tests compare against without any Python in the loop. Run one model at a time,
with limits, e.g.:

    systemd-run --user --scope -p MemoryMax=8G -p RuntimeMaxSec=1800 \
        uv run python -m e2e.validation_goldens zaks2012
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib as mpl
import mxlmodels
import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable

MODELS = Path(__file__).parents[3] / "pages/green-sloth/src/lib/models"
MAX_POINTS = 200

type Namespace = dict[str, Any]
type Extract = Callable[[Namespace], tuple[Any, Any]]


def _pair(name: str, col: str) -> Extract:
    return lambda ns: (ns[name].index, ns[name][col])


def _qe(wt: str, ko: str) -> Extract:
    # As the notebook plots it: the npq4 pulse times, positional difference.
    return lambda ns: (ns[ko].index, ns[wt].to_numpy() - ns[ko].to_numpy())


SERIES: dict[str, dict[str, dict[str, Extract]]] = {
    "zaks2012": {
        "fig4": {
            "qE1000": _qe("PAM_1000_WT", "PAM_1000_npq4"),
            "qE100": _qe("PAM_100_WT", "PAM_100_npq4"),
            "wt1000_pH": _pair("res_1000_WT", "pH_lumen"),
            "npq41000_pH": _pair("res_1000_npq4", "pH_lumen"),
        },
        "fig6": {
            "kQ1e10": _pair("res_kQ_1e10", "pH_lumen"),
            "kQ1e11": _pair("res_kQ_1e11", "pH_lumen"),
        },
    },
}


def run_notebook(model: str) -> Namespace:
    """Execute a notebook's code cells in one namespace, without display.

    Notebooks do `from <model> import get_model`; that resolves to the mxl-models
    original, which green-sloth's model.ts is generated from.
    """
    mpl.use("Agg")
    shim = types.ModuleType(model)
    shim.get_model = getattr(mxlmodels, f"get_{model}")  # type: ignore[attr-defined]
    sys.modules[model] = shim
    path = MODELS / model / "validation.ipynb"
    ns: Namespace = {"__name__": "__main__", "display": lambda *_: None}
    cells = json.loads(path.read_text())["cells"]
    for cell in cells:
        if cell["cell_type"] == "code":
            exec("".join(cell["source"]), ns)  # noqa: S102
    return ns


def downsample(x: np.ndarray, y: np.ndarray) -> dict[str, list[float]]:
    """Keep at most MAX_POINTS evenly-indexed points, including both ends."""
    keep = np.unique(np.linspace(0, len(x) - 1, min(len(x), MAX_POINTS)).astype(int))
    return {"x": x[keep].tolist(), "y": y[keep].tolist()}


def main(model: str) -> None:
    """Write the golden file of one model."""
    ns = run_notebook(model)
    golden = {
        figure: {
            name: downsample(*(np.asarray(v, dtype=float) for v in extract(ns)))
            for name, extract in series.items()
        }
        for figure, series in SERIES[model].items()
    }
    out = MODELS / model / "validation.golden.json"
    out.write_text(json.dumps(golden) + "\n")
    print(f"{out}: {out.stat().st_size} bytes")  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1])
