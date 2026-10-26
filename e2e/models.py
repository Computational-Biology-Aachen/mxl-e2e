"""The mxl-models models the round-trip pipeline covers.

An explicit list: a model is only covered once it is added here. Left out for
now: the steady-state models (bernacchi2013, fvcb1980 and nedbal2021 take
arguments, gu2023/johnson2021 return plain dicts), pfennig2024 (`add_data`,
which no exporter emits) and fuente2024 (its initial conditions come from a
numerical root-solve, which has no MathML representation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import mxlmodels

if TYPE_CHECKING:
    from collections.abc import Callable

    from mxlpy import Model

MODELS: dict[str, Callable[[], Model]] = {
    "bellasio2019": mxlmodels.get_bellasio_2019,
    "davis2017": mxlmodels.get_davis2017,
    "dynamic_enterobactin": mxlmodels.get_dynamic_enterobactin,
    "ebeling2026": mxlmodels.get_ebeling_2026,
    "ebenhoeh2014": mxlmodels.get_ebenhoeh2014,
    "elowitz2000_repressilator": mxlmodels.get_elowitz2000_repressilator,
    "hahn1987": mxlmodels.get_hahn1987,
    "lam2026": mxlmodels.get_lam2026,
    "lazar1997": mxlmodels.get_lazar1997,
    "li2021": mxlmodels.get_li_2021,
    "lotka_volterra_v1": mxlmodels.get_lotka_volterra_v1,
    "lotka_volterra_v2": mxlmodels.get_lotka_volterra_v2,
    "matuszynska2016_npq": mxlmodels.get_matuszynska2016_npq,
    "matuszynska2016_phd": mxlmodels.get_matuszynska2016_phd,
    "matuszynska2019": mxlmodels.get_matuszynska2019,
    "morales2018": mxlmodels.get_morales2018,
    "nguyen2026_tomato": mxlmodels.get_nguyen2026_tomato,
    "poolman2000": mxlmodels.get_poolman2000,
    "population_dynamics": mxlmodels.get_population_dynamics,
    "prigogine1968_brusselator": mxlmodels.get_prigogine1968_brusselator,
    "saadat2021": mxlmodels.get_saadat2021,
    "salvatori2022": mxlmodels.get_salvatori2022,
    "selkov1968_oscillator": mxlmodels.get_selkov1968_glycolysis_oscillator,
    "sir": mxlmodels.get_sir,
    "sird": mxlmodels.get_sird,
    "tripartite_dynamics": mxlmodels.get_tripartite_dynamics,
    "yokota1985": mxlmodels.get_yokota1985,
    "zaks2012": mxlmodels.get_zaks2012,
    "zhu2005": mxlmodels.get_zhu_2005,
    "zhu2009": mxlmodels.get_zhu_2009,
}
