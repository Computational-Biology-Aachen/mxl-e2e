"""Step 3 of the pipeline: is the generated model the same model?

Every check returns a list of human-readable differences (empty when the two
models agree), with names given in the generated model's (canonical) ids.
`name_map` maps every id of the reference model to its id in the other model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from mxlpy.units import unit_to_json

if TYPE_CHECKING:
    import pandas as pd
    from mxlpy import Model

KINDS = ("parameters", "variables", "derived", "reactions", "readouts")
RTOL = 1e-10
ATOL = 1e-12


def ids_by_kind(model: Model) -> dict[str, set[str]]:
    """Ids per kind, with surrogate outputs counted the way the mxlweb export flattens them.

    An output with stoichiometry becomes a reaction, any other output a derived value.
    """
    derived = set(model.get_raw_derived())
    reactions = set(model.get_raw_reactions())
    for surrogate in model.get_raw_surrogates().values():
        stoichiometries = getattr(surrogate, "stoichiometries", {}) or {}
        for out in surrogate.outputs:
            (reactions if out in stoichiometries else derived).add(out)
    return {
        "parameters": set(model.get_raw_parameters()),
        "variables": set(model.get_raw_variables()),
        "derived": derived,
        "reactions": reactions,
        "readouts": set(model.get_raw_readouts()),
    }


def _set_diff(kind: str, expected: set[str], actual: set[str]) -> list[str]:
    diffs = []
    if missing := sorted(expected - actual):
        diffs.append(f"{kind}: missing {missing}")
    if extra := sorted(actual - expected):
        diffs.append(f"{kind}: unexpected {extra}")
    return diffs


def structure(ref: Model, other: Model, name_map: dict[str, str]) -> list[str]:
    """Same ids per kind, and the same stoichiometric coefficients where numeric."""
    ref_ids = ids_by_kind(ref)
    other_ids = ids_by_kind(other)
    diffs = []
    for kind in KINDS:
        expected = {name_map[i] for i in ref_ids[kind]}
        diffs.extend(_set_diff(kind, expected, other_ids[kind]))

    other_rxns = other.get_raw_reactions()
    for name, rxn in ref.get_raw_reactions().items():
        if (other_rxn := other_rxns.get(name_map[name])) is None:
            continue
        expected = {name_map[k] for k in rxn.stoichiometry}
        diffs.extend(
            _set_diff(
                f"stoichiometry of {name_map[name]}",
                expected,
                set(other_rxn.stoichiometry),
            )
        )
    return diffs


def _values(
    kind: str, ref: dict[str, Any], other: dict[str, Any], name_map: dict[str, str]
) -> list[str]:
    mapped = {name_map[k]: v for k, v in ref.items()}
    diffs = _set_diff(kind, set(mapped), set(other))
    for k in sorted(set(mapped) & set(other)):
        a, b = float(mapped[k]), float(other[k])
        if not np.isclose(b, a, rtol=RTOL, atol=ATOL, equal_nan=True):
            diffs.append(f"{kind} {k}: {a!r} != {b!r}")
    return diffs


def values(ref: Model, other: Model, name_map: dict[str, str]) -> list[str]:
    """Same parameter values and initial conditions."""
    return _values(
        "parameter",
        ref.get_parameter_values(),
        other.get_parameter_values(),
        name_map,
    ) + _values(
        "initial condition",
        ref.get_initial_conditions(),
        other.get_initial_conditions(),
        name_map,
    )


def sample_states(
    model: Model, n: int = 5, seed: int = 42
) -> list[tuple[float, dict[str, float]]]:
    """The initial state plus `n` seeded log-normal perturbations, at t=0 and t=1.5."""
    rng = np.random.default_rng(seed)
    y0 = model.get_initial_conditions()
    names = list(y0)
    base = np.array([y0[k] for k in names], dtype=float)
    states = [base]
    for _ in range(n):
        noise = rng.lognormal(0.0, 0.3, size=base.shape)
        states.append(base * noise + 1e-3 * rng.random(base.shape))
    return [(t, dict(zip(names, s, strict=True))) for s in states for t in (0.0, 1.5)]


def _series_diff(
    label: str, ref: pd.Series, other: pd.Series, atol: float = ATOL
) -> list[str]:
    diffs = _set_diff(label, set(ref.index), set(other.index))
    common = ref.index.intersection(other.index)
    a = ref[common].to_numpy(dtype=float)
    b = other[common].to_numpy(dtype=float)
    bad = ~np.isclose(b, a, rtol=RTOL, atol=atol, equal_nan=True)
    diffs.extend(
        f"{label} {k}: {x!r} != {y!r}"
        for k, x, y in zip(common[bad], a[bad], b[bad], strict=True)
    )
    return diffs


def args(ref: Model, other: Model, name_map: dict[str, str]) -> list[str]:
    """Same `get_args` (readouts included) and right-hand side at sampled states."""
    diffs = []
    other_y0 = other.get_initial_conditions()
    for i, (t, state) in enumerate(sample_states(ref)):
        # Variables the other model lacks are reported by `structure`; any it
        # has on its own keep their initial value.
        mapped = other_y0 | {
            name_map[k]: v for k, v in state.items() if name_map[k] in other_y0
        }
        label = f"state #{i // 2}, t={t}"
        ref_args = ref.get_args(state, t, include_readouts=True).rename(name_map)
        other_args = other.get_args(mapped, t, include_readouts=True)
        diffs.extend(_series_diff(f"args ({label})", ref_args, other_args))
        ref_rhs = ref.get_right_hand_side(state, t).rename(name_map)
        other_rhs = other.get_right_hand_side(mapped, t)
        # dx/dt sums fluxes that may cancel almost exactly (near steady state),
        # so its rounding error scales with the fluxes, not with dx/dt itself.
        magnitudes = np.abs(ref_args.to_numpy(dtype=float))
        scale = np.max(magnitudes[np.isfinite(magnitudes)], initial=1.0)
        diffs.extend(
            _series_diff(f"rhs ({label})", ref_rhs, other_rhs, atol=RTOL * scale)
        )
        if diffs:
            break
    return diffs


def _entities(model: Model) -> dict[str, Any]:
    return {
        **model.get_raw_parameters(),
        **model.get_raw_variables(),
        **model.get_raw_derived(),
        **model.get_raw_reactions(),
        **model.get_raw_readouts(),
    }


def display_names(ref: Model, other: Model, name_map: dict[str, str]) -> list[str]:
    """A renamed id survives as the generated entity's display name."""
    other_entities = _entities(other)
    diffs = []
    for name, el in _entities(ref).items():
        if (other_el := other_entities.get(name_map[name])) is None:
            continue
        expected = el.display_name
        if expected is None and name_map[name] != name:
            expected = name
        if other_el.display_name != expected:
            diffs.append(
                f"{name_map[name]}: display_name {other_el.display_name!r} != {expected!r}"
            )
    return diffs


def units(ref: Model, other: Model, name_map: dict[str, str]) -> list[str]:
    """Same unit on every entity, compared in the representation shared with mxlweb."""
    other_entities = _entities(other)
    diffs = []
    for name, el in _entities(ref).items():
        if (other_el := other_entities.get(name_map[name])) is None:
            continue
        expected, actual = unit_to_json(el.unit), unit_to_json(other_el.unit)
        if actual != expected:
            diffs.append(f"{name_map[name]}: unit {actual!r} != {expected!r}")
    return diffs
