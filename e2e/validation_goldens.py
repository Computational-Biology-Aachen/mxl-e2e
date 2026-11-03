"""Freeze numeric references from the green-sloth validation notebooks.

Runs a notebook's code cells as they are, then writes the series named in
`SERIES` to `<model>/validation.golden.json`, which green-sloth's validation
tests compare against without any Python in the loop. Run one model at a time,
with limits, e.g.:

    systemd-run --user --scope -p MemoryMax=8G -p RuntimeMaxSec=1800 \
        uv run python -m e2e.validation_goldens zaks2012
"""

from __future__ import annotations

import functools
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib as mpl
import mxlpy
import mxlpy.parallel
import numpy as np
from mxlpy.runners import KineticRunner

if TYPE_CHECKING:
    from collections.abc import Callable

MODELS = Path(__file__).parents[3] / "pages/green-sloth/src/lib/models"
MAX_POINTS = 200

type Namespace = dict[str, Any]
type Extract = Callable[[Namespace], tuple[Any, Any]]


def _at(name: str, col: str, cell: int | None = None) -> Extract:
    """Column `col` of the result `name`, optionally as of a code cell."""

    def extract(ns: Namespace) -> tuple[Any, Any]:
        frame = (ns if cell is None else ns["_cells"][cell])[name]
        return frame.index, frame[col]

    return extract


def _qe(wt: str, ko: str) -> Extract:
    # As the notebook plots it: the npq4 pulse times, positional difference.
    return lambda ns: (ns[ko].index, ns[wt].to_numpy() - ns[ko].to_numpy())


def _item(name: str, key: Any, col: str, cell: int | None = None) -> Extract:
    """Column `col` of `name[key]`, for results kept in a dict or list."""

    def extract(ns: Namespace) -> tuple[Any, Any]:
        frame = (ns if cell is None else ns["_cells"][cell])[name][key]
        return frame.index, frame[col]

    return extract


def _poolman_scan(ns: Namespace) -> tuple[Any, Any]:
    flux = ns["_cells"][1]["res"].fluxes["ex_g1p"]
    return flux.index, flux


def _yokota(col: str) -> Extract:
    return lambda ns: (ns["res"].variables.index, ns["res"].variables[col])


def _poolman_tc(col: str, kind: str) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        frame = getattr(ns["_cells"][0]["res"], kind)
        return frame.index, frame[col]

    return extract


def _light_dark_light(intensity: int, col: str) -> Extract:
    # The notebook keeps only the last run, so these repeat the others.
    def extract(ns: Namespace) -> tuple[Any, Any]:
        cache = ns.setdefault("_ldl", {})
        if intensity not in cache:
            cache[intensity] = ns["light_dark_light"](
                ns["get_matuszynska2019"](), intensity=intensity
            )
        return cache[intensity].index, cache[intensity][col]

    return extract


def _ebenhoeh_surface(ns: Namespace) -> tuple[Any, Any]:
    values = ns["res_fig3"].to_numpy()
    return np.arange(len(values)), values


def _zhu2009_scan(figure: str, param: str, col: str) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        res = ns[figure][param]
        return np.arange(len(res)), res[col]

    return extract


def _table(name: str, col: str, cell: int | None = None) -> Extract:
    """Column of a scan result by position, for scans without a sorted index."""

    def extract(ns: Namespace) -> tuple[Any, Any]:
        frame = (ns if cell is None else ns["_cells"][cell])[name]
        return np.arange(len(frame)), frame[col]

    return extract


def _npq(name: str) -> Extract:
    return lambda ns: (ns[name]["Fm_time"], ns[name]["NPQ"])


def _saadat_fig4(col: str) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        base = ns["fig4_m"].get_parameter_values()["kf_cyclic_electron_flow"]
        res = ns["fig4_res"]
        return res.index - np.log2(base), res[col]

    return extract


def _saadat_mca(row: str, ppfd: int) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        labels = list(ns["scan_params"].values())
        values = ns["res"].loc[ppfd].loc[row, labels].to_numpy()
        return np.arange(len(values)), values

    return extract


def _fuente_fig4(hi: int, period: float, col: str) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        frame = ns["fig4_res"].loc[f"(50, {hi})"].loc[period]
        return frame.index, frame[col]

    return extract


def _bellasio_transient(name: str, key: str, col: str) -> Extract:
    return _item(name, key, col)


def _lam(figure: str, gt: str, col: str) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        frame = ns[figure].loc[gt]
        return frame.index, frame[col]

    return extract


def _lam_fig5(key: str, n: int | None) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        frame = ns["fig5_res"][key]
        if n is not None:
            frame = frame.loc[n]
        frame = frame[frame.index >= 1]
        return frame.index - 1, frame["tau_Fluo"]

    return extract


def _davis_fig3(key: str, col: str) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        frame = ns["fig3_res"].loc[key]
        return frame.index, frame[col]

    return extract


def _lazar_ojip(ns: Namespace) -> tuple[Any, Any]:
    idx = list(ns["res_fig2"]["OJIP"].values())
    res = ns["res_fig2"]["results"]
    return res.index[idx], res["F"].iloc[idx]


def _lazar_rf(figure: str, which: str) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        values = ns[figure]["rF"][which]
        keys = sorted(values, key=float)
        return [float(k) for k in keys], [values[k] for k in keys]

    return extract


def _lazar_curve(figure: str, key: Any) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        res = ns[figure]["results"]
        frame = res[key] if isinstance(res, dict) else res.loc[key]
        return frame.index, frame["F"]

    return extract


SALVATORI_CELLS = (("fig3", 1, 2), ("fig5", 3, 2), ("fig8", 5, 4))
SCAN_BELLASIO = ("A", "gs", "v_FNR", "RUBP", "PGA", "Ract", "f_rubp")
SAADAT_ROWS = (
    "Plastoquinone_reduced",
    "Ferredoxine_reduced",
    "Plastocyanine_reduced",
    "NADPH",
    "ATP",
    "RUBP",
    "_3PGA",
    "FBP",
    "SBP",
    "PSII",
    "PSI",
    "b6f",
    "mehler",
    "cyclic_electron_flow",
    "rubisco_carboxylase",
    "fbpase",
    "SBPase",
    "mda_reductase_2",
    "dehydroascorbate_reductase",
)
SAADAT_FIG3 = (
    "PSI",
    "PSII",
    "cyclic_electron_flow",
    "mehler",
    "PTOX",
    "ATP_per_tot",
    "NADPH_per_tot",
    "Fd_ox_per_tot",
    "PQ_ox_per_tot",
    "PC_ox_per_tot",
    "H2O2",
)
FUENTE_PERIODS = (10000, 1000, 100, 1, 0.1, 0.001)
LAM_PARTS = ("NPQ_qI", "NPQ_V", "NPQ_A", "NPQ_Z_qE", "NPQ_L", "NPQ_Z_qZ")
DAVIS_FIG3 = (
    "Dpsi",
    "delta_pH_inVolts",
    "pmf",
    "k_b6f",
    "pH_lumen",
    "NPQ",
    "K_lu",
    "QA_red",
    "vPSII_recomb",
    "LEF",
    "singO2",
)
LAZAR_LABELLED = ("F", "y2", "y4", "y6", "y8", "y14", "y15", "y12")


def _lazar_figure(
    figure: str, ids: tuple[str, ...], keys: tuple[Any, ...]
) -> dict[str, Extract]:
    return {
        **{f"F_{i}": _lazar_curve(figure, k) for i, k in zip(ids, keys, strict=True)},
        "rFJ": _lazar_rf(figure, "rFJ"),
        "rFI": _lazar_rf(figure, "rFI"),
    }


def _mat_fig(col: str, pfd: int, name: str = "fig4_res") -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        frame = ns[name].loc[pfd]
        return frame.index, frame[col]

    return extract


def _morales_lfue(which: str) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        frame = ns["LFUE"]
        if which != "whole":
            cycle = ns["LFUEcycle"]
            frame = cycle[cycle["Direction"] == which]
        # Sorted by genotype, amplitude, then period (60 before 120).
        return np.arange(len(frame)), frame["simLFUE"]

    return extract


def _morales_trace(genotype: str, amplitude: int) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        lf = ns["lf"]
        run = lf[(lf["Genotype"] == genotype) & (lf["Amplitude"] == amplitude)]
        return run["simulation_time"], run["simPhoto"] * 1e-6

    return extract


def _li(name: str, gt: str, pfd: int, col: str) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        frame = ns[name].loc[gt].loc[pfd]
        return frame.index, frame[col]

    return extract


def _li_fig5(key: str, *levels: Any, col: str) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        frame = ns["fig5_res"][key]
        for level in levels:
            frame = frame.loc[level]
        return frame.index, frame[col]

    return extract


def _li_scan(name: str) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        frame = ns["fig5_res"]["2min_scan"].loc[name]
        return frame.index, frame["NPQ"]

    return extract


def _li_amplitude(gt: str) -> Extract:
    def extract(ns: Namespace) -> tuple[Any, Any]:
        row = ns["fig5_res"]["Osc Sim_points"].loc[gt]
        return row.index, row.to_numpy()

    return extract


LI_GENOTYPES = ("wt", "c", "v", "k", "cv", "ck", "vk", "vck")
LI_FIG4 = ("Dpsi", "delta_pH_inVolts", "pmf", "K_lu", "Cl_lu", "K_flux", "Cl_flux")
LI_ABUNDANCE = ("0.01", "0.1", "1", "10", "100")

SERIES: dict[str, dict[str, dict[str, Extract]]] = {
    "matuszynska2016": {
        "fig4": {f"Fluo{p}": _mat_fig("Fluo", p) for p in (100, 300, 900)},
        "fig5": {
            **{
                f"{c}_{p}": _li_fig5("time_sim", p, col=c)
                for c in ("pH_lu", "zx", "psbs_pr", "Q")
                for p in (100, 300, 900)
            },
            "scan_pH_lu": lambda ns: (
                ns["fig5_res"]["scan"].index,
                ns["fig5_res"]["scan"]["pH_lu"],
            ),
            "scan_Q": lambda ns: (
                ns["fig5_res"]["scan"].index,
                ns["fig5_res"]["scan"]["Q"],
            ),
        },
        "fig6": {
            "Fluo": _at("fig6_res", "Fluo"),
            "phiPSII": lambda ns: (
                ns["fig6_resextra"]["Fm_time"],
                ns["fig6_resextra"]["QY_PSII"],
            ),
        },
    },
    "morales2018": {
        "fig6": {
            "whole": _morales_lfue("whole"),
            "up": _morales_lfue("up"),
            "down": _morales_lfue("down"),
            "Photo_col_100": _morales_trace("col", 100),
            "Photo_npq4_500": _morales_trace("npq4", 500),
            "Photo_rwt43_200": _morales_trace("rwt43", 200),
            "Photo_rca2_500": _morales_trace("rca2", 500),
        },
    },
    "li2021": {
        "fig3": {
            **{
                f"NPQ_{g}_{p}": _li("fig3_res", g, p, "NPQ")
                for g in LI_GENOTYPES
                for p in (100, 500)
            },
            **{
                f"{c}_wt_{p}": _li("fig3_res", "wt", p, c)
                for c in ("QA", "PhiPSII")
                for p in (100, 500)
            },
        },
        "fig4": {
            f"{c}_{g}_{p}": _li("fig4_res", g, p, c)
            for g in ("wt", "v", "k", "vck")
            for p in (100, 500)
            for c in LI_FIG4
        },
        "fig5a": {
            **{
                f"noreg_{p}": _li_fig5("Genotypes", "k_noreg", p, col="NPQ")
                for p in (100, 500)
            },
            "scan_wt": _li_scan("wt"),
            "scan_kea3": _li_scan("kea3"),
            "scan_noreg": _li_scan("kea3_noreg"),
        },
        "fig5b": {
            "kea3": _li_amplitude("kea3"),
            "vccn1": _li_amplitude("vccn1"),
            "noreg": _li_amplitude("kea3_noreg"),
        },
        "fig5c": {
            f"{c}_conc{p}_{g}_{i}": _li_fig5("Concs", p, g, a, col=c)
            for p in (100, 500)
            for g in ("vccn1", "kea3")
            for i, a in enumerate(LI_ABUNDANCE)
            for c in ("delta_pH_inVolts", "Dpsi")
        },
    },
    "saadat2021": {
        "fig2": {"Fluo": _at("fig2_res", "Fluo"), "NPQ": _npq("fig2_resextra")},
        "fig3": {c: _at("fig3_res", c) for c in SAADAT_FIG3},
        "fig4": {
            c: _saadat_fig4(c)
            for c in (
                "PSI",
                "PSII",
                "cyclic_electron_flow",
                "H2O2",
                "ATP_per_tot",
                "NADPH_per_tot",
                "Fd_ox_per_tot",
            )
        },
        "fig5": {
            "Fd_wt": _item("fig5_res", "wt", "Fd_ox_per_tot"),
            "Fd_ko": _item("fig5_res", "ko", "Fd_ox_per_tot"),
            "rubisco_wt": _item("fig5_res", "wt", "rubisco_carboxylase"),
            "rubisco_ko": _item("fig5_res", "ko", "rubisco_carboxylase"),
        },
        "fig6": {
            f"{r}_{p}": _saadat_mca(r, p) for r in SAADAT_ROWS for p in (100, 1000)
        },
    },
    "fuente2024": {
        "fig2": {
            c: _at("fig2_res", c)
            for c in ("osc_light", "PQ", "H_lumen", "Q_active", "ATP_st", "PSI_ox")
        },
        "fig3": {
            c: _at("fig3_res", c)
            for c in (
                "ATP_st",
                "Q_active",
                "H_lumen",
                "PSI_ox",
                "PQ",
                "O2",
                "NPQ",
                "Fluo",
            )
        },
        "fig4": {
            f"{c}_h{hi}_t{k}": _fuente_fig4(hi, t, c)
            for hi in (950, 150)
            for k, t in enumerate(FUENTE_PERIODS)
            for c in ("PQ", "H_lumen", "NPQ")
        },
    },
    "bellasio2019": {
        "fig3": {
            **{f"pfd_{c}": _table("fig3_res_pfd", c) for c in SCAN_BELLASIO},
            **{f"ca_{c}": _table("fig3_res_ca", c) for c in SCAN_BELLASIO},
        },
        "fig5": {
            f"{c}_{i}": _item("fig5_res", k, c)
            for i, k in (("up", "1500"), ("down", "50"))
            for c in ("A", "v_ATPsynth", "gs", "RUBP", "ATP_st")
        },
        "fig6": {
            f"{c}_{i}": _item("fig6_res", k, c)
            for i, k in (("up", "1500"), ("down", "350"))
            for c in ("A", "v_ATPsynth", "gs", "RUBP", "ATP_st")
        },
        "fig7": {"A": _at("fig7_res", "A"), "PhiPSII": _at("fig7_res", "PhiPSII")},
    },
    "lam2026": {
        "fig2": {
            g: _lam("fig2_res", g, "tau_Fluo")
            for g in ("npq4npq1", "npq4", "npq1", "lut2", "zep2")
        },
        "fig3": {
            g: _lam("fig3_res", g, "tau_Fluo")
            for g in (
                "WT",
                "WT_base",
                "WT_mix",
                "zep2lut2",
                "npq1lut2",
                "npq4lut2",
                "npq4zep2",
            )
        },
        "fig4": {
            f"{g}_{c}": _lam("fig4_res", g, c)
            for g in ("npq4npq1", "npq4", "npq1", "lut2", "zep2", "WT")
            for c in LAM_PARTS
        },
        "fig5": {
            "WT": _lam_fig5("WT", None),
            **{f"{k}{n}": _lam_fig5(k, n) for k in "ABC" for n in range(3)},
            **{f"D{n}": _lam_fig5("D", n) for n in range(2)},
        },
    },
    "davis2017": {
        "fig3": {
            f"{c}_p{k}": _davis_fig3(k, c) for k in ("0", "1", "10") for c in DAVIS_FIG3
        },
        "fig4": {
            f"{c}_{i}": _at(n, c)
            for i, n in (
                ("normSin", "norm_sin"),
                ("fastSin", "fast_sin"),
                ("normSquare", "norm_fluct"),
                ("fastSquare", "fast_fluct"),
            )
            for c in ("Dpsi", "pmf", "LEF", "singO2")
        },
        "fig5": {
            f"{c}_{i}": _at(n, c)
            for i, n in (
                ("zero", "zero"),
                ("norm", "norm"),
                ("fast", "fast"),
                ("veryFast", "very_fast"),
            )
            for c in ("v_VKC", "deficit", "deficit_int")
        },
    },
    "lazar1997": {
        "fig2": {
            **{c: _item("res_fig2", "results", c) for c in LAZAR_LABELLED},
            "steps": _lazar_ojip,
        },
        "fig5": _lazar_figure(
            "res_fig3", ("f0", "f1", "f2", "f3", "f4"), (0, 0.5, 0.77, 0.9, 1)
        ),
        "fig6": _lazar_figure(
            "res_fig6",
            ("a0", "a1", "a2", "a3", "a4"),
            ("0", "0.25", "0.5", "0.75", "1.0"),
        ),
        "fig7": _lazar_figure("res_fig7", ("f0", "f1", "f2", "f3"), (0, 0.1, 0.2, 0.4)),
        "fig8": _lazar_figure(
            "res_fig8",
            tuple(f"d{i}" for i in range(8)),
            tuple(str(i) for i in range(8)),
        ),
    },
    "zaks2012": {
        "fig4": {
            "qE1000": _qe("PAM_1000_WT", "PAM_1000_npq4"),
            "qE100": _qe("PAM_100_WT", "PAM_100_npq4"),
        },
        "fig5": {
            "wt1000_pH": _at("res_1000_WT", "pH_lumen"),
            "npq41000_pH": _at("res_1000_npq4", "pH_lumen"),
        },
        "fig6": {
            "kQ1e10": _at("res_kQ_1e10", "pH_lumen"),
            "kQ1e11": _at("res_kQ_1e11", "pH_lumen"),
        },
    },
    "poolman2000": {
        "timecourse": {
            "BPGA": _poolman_tc("BPGA", "variables"),
            "GAP": _poolman_tc("GAP", "variables"),
            "vRubisco": _poolman_tc("rubisco_carboxylase", "fluxes"),
        },
        "fig3": {"starch": _poolman_scan},
    },
    "yokota1985": {
        "fig6a": {
            c: _yokota(c) for c in ("glycolate", "glyoxylate", "glycine", "serine")
        },
    },
    "matuszynska2019": {
        "fig2": {
            f"{col}{i}": _light_dark_light(i, col)
            for i in (20, 50, 100, 150, 200)
            for col in ("Orthophosphate", "rubisco_carboxylase")
        },
    },
    "hahn1987": {
        "fig2": {
            f"{c}_{t}": _item("res_fig2", str(t), c)
            for t in (240, 4800)
            for c in ("TP", "RuBP", "PGA", "Gl")
        },
        "fig3": {
            f"{c}_{v}": _item("res_fig3", v, c)
            for v in ("0.05", "4.5")
            for c in ("RuBP", "PGA", "Gl", "PAn")
        },
        "fig4": {
            f"{c}_{v}": _item("res_fig4", v, c)
            for v in ("10", "200")
            for c in ("RuBP", "PGA", "Gl", "PAn")
        },
    },
    "ebenhoeh2014": {
        "fig2": {
            "normal": _item("res_fig2", "normal", "Fluo"),
            "anoxia": _item("res_fig2", "anoxia", "Fluo"),
        },
        "fig3": {"pqRed": _ebenhoeh_surface},
    },
    "salvatori2022": {
        fig: {
            f"{col}_{i}": _item(kind, i, col, cell)
            for i in range(n)
            for kind, col in (("concs", "A"), ("fluxes", "NPQ"), ("fluxes", "ETR_out"))
        }
        for fig, cell, n in (("fig3", 1, 2), ("fig5", 3, 2), ("fig8", 5, 4))
    },
    "zhu2005": {
        "fig3": {
            # MxlPy also returns the t=0 it starts from, which the log grid omits.
            "F": lambda ns: (ns["simulation"].index[1:], ns["simulation"]["F"][1:]),
            "QA": lambda ns: (
                ns["simulation"].index[1:],
                ns["simulation"]["QA_reduction_fraction"][1:],
            ),
        },
    },
    "zhu2009": {
        "fig2": {c: _at("res_fig2", c) for c in ("PGA", "DPGA", "GAP", "Ru5P")},
        "fig3": {
            f"{p}_{c}": _zhu2009_scan("res_fig3", p, c)
            for p in ("V1_max", "V3_max", "V4_max", "V13_max")
            for c in ("RuBP", "PGA", "DPGA", "Ru5P")
        },
        "fig4": {
            f"{p}_{c}": _zhu2009_scan("res_fig4", p, c)
            for p in ("V2_max", "V5_max")
            for c in ("RuBP", "PGA", "DPGA", "Ru5P")
        },
    },
}


def _exported_model(model: str) -> types.ModuleType:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "model.py"
        subprocess.run(  # noqa: S603
            [
                "npx",
                "vite-node",
                "scripts/export-validation.ts",
                "--model",
                model,
                str(out),
            ],  # noqa: S607
            cwd=MODELS.parents[2],
            check=True,
            capture_output=True,
        )
        module = types.ModuleType(model)
        exec(out.read_text(), module.__dict__)  # noqa: S102
    return module


def _run_serially() -> None:
    """Keep notebook code in this process: its functions can't be pickled here."""

    @functools.wraps(mxlpy.parallel.parallelise)
    def serial(*args: Any, **kwargs: Any) -> Any:
        kwargs["parallel"] = False
        return original(*args, **kwargs)

    original = mxlpy.parallel.parallelise
    for module in (mxlpy.parallel, mxlpy.scan, mxlpy.mca):
        if hasattr(module, "parallelise"):
            module.parallelise = serial


def _accept_integrator_argument() -> None:
    """Translate the notebooks' `integrator=` to MxlPy's current `runner=`."""

    def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def inner(*args: Any, integrator: Any = None, **kwargs: Any) -> Any:
            if integrator is not None:
                kwargs["runner"] = KineticRunner(integrator=integrator)
            return fn(*args, **kwargs)

        return inner

    for module, name in (
        (mxlpy.scan, "steady_state"),
        (mxlpy.scan, "time_course"),
        (mxlpy.scan, "protocol"),
        (mxlpy.mca, "response_coefficients"),
    ):
        if not hasattr(getattr(module, name), "__wrapped__"):
            setattr(module, name, wrap(getattr(module, name)))


def run_notebook(model: str) -> Namespace:
    """Execute a notebook's code cells in one namespace, without display.

    Notebooks do `from <model> import get_model`, which is MxlPy's export of
    green-sloth's model.ts, with its canonical ids.
    """
    mpl.use("Agg")
    sys.modules[model] = _exported_model(model)
    _accept_integrator_argument()
    _run_serially()
    path = MODELS / model / "validation.ipynb"
    ns: Namespace = {"__name__": "__main__", "display": lambda *_: None, "_cells": []}
    cells = json.loads(path.read_text())["cells"]
    # Results are often overwritten by later cells, so keep each cell's view.
    # Notebooks may write figures and read `assets/`, so run in a scratch dir.
    with tempfile.TemporaryDirectory() as tmp:
        assets = path.parent / "assets"
        if assets.exists():
            (Path(tmp) / "assets").symlink_to(assets)
        cwd = Path.cwd()
        os.chdir(tmp)
        try:
            for cell in cells:
                if cell["cell_type"] == "code":
                    exec("".join(cell["source"]), ns)  # noqa: S102
                    ns["_cells"].append(dict(ns))
        finally:
            os.chdir(cwd)
    return ns


def downsample(x: np.ndarray, y: np.ndarray) -> dict[str, list[float]]:
    """Keep at most MAX_POINTS evenly-indexed points, including both ends."""
    finite = np.isfinite(y)
    x, y = x[finite], y[finite]
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
