"""Seed `maps/<slug>.json` (green-sloth id -> mxl-models id) for review.

A one-off helper: it guesses, a human reviews and commits the result. Run
with `--stage` (or after an earlier staged run) so the mxlpy exports of
green-sloth's committed models exist in `build/greensloth/<slug>/committed/`:

    uv run python -m e2e.seed_map --stage [--force] [slug ...]

Matching, in order, until nothing new matches:
1. the green-sloth id is the canonical identifier of the mxl-models id;
2. the green-sloth texName / displayName is the mxl-models id (or has the same
   canonical identifier);
3. the same canonical identifier ignoring case, if unique on both sides;
4. a parameter value / initial condition that is unique on both sides among the
   unmatched ones;
5. a derived value / reaction / readout whose arguments (and stoichiometry)
   map exactly onto those of exactly one unmatched mxl-models entity.
"""

from __future__ import annotations

import argparse
import warnings
from typing import TYPE_CHECKING, Any

from mxlpy.meta import canonical_identifier, canonical_identifier_map

from e2e import greensloth, pipeline
from e2e.models import MODELS

if TYPE_CHECKING:
    from mxlpy import Model


def _entities(model: Model) -> dict[str, Any]:
    return {
        **model.get_raw_parameters(),
        **model.get_raw_variables(),
        **model.get_raw_derived(),
        **model.get_raw_reactions(),
        **model.get_raw_readouts(),
    }


def _signature(el: Any, mapping: dict[str, str]) -> tuple | None:
    """Arguments (and stoichiometry) of `el` in mxl-models ids, if all are mapped."""
    names = list(getattr(el, "args", []))
    names += list(getattr(el, "stoichiometry", {}) or {})
    if not names or any(n not in mapping for n in names):
        return None
    args = frozenset(mapping[n] for n in getattr(el, "args", []))
    stoich = frozenset(mapping[n] for n in getattr(el, "stoichiometry", {}) or {})
    return (type(el).__name__, args, stoich)


def _unique_pairs(left: dict[str, Any], right: dict[str, Any]) -> dict[str, str]:
    """left key -> right key for every value that occurs exactly once on each side."""

    def index(d: dict[str, Any]) -> dict[Any, list[str]]:
        out: dict[Any, list[str]] = {}
        for k, v in d.items():
            if v is not None:
                out.setdefault(v, []).append(k)
        return out

    li, ri = index(left), index(right)
    return {
        li[v][0]: ri[v][0]
        for v in li.keys() & ri.keys()
        if len(li[v]) == 1 and len(ri[v]) == 1
    }


def seed(slug: str) -> greensloth.NameMap:
    model = greensloth.SLUGS[slug]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mxl = MODELS[model]()
        canonical = canonical_identifier_map(mxl.ids)
    gs = pipeline.load_generated(greensloth.stage(slug) / "model-gen.py")
    gs_entities, mxl_entities = _entities(gs), _entities(mxl)
    gs_ids, mxl_ids = set(gs.ids), set(mxl.ids)

    mapping: dict[str, str] = {}

    def claim(pairs: dict[str, str]) -> bool:
        before = len(mapping)
        taken = set(mapping.values())
        for g, m in pairs.items():
            if g not in mapping and m not in taken:
                mapping[g] = m
                taken.add(m)
        return len(mapping) > before

    claim({v: k for k, v in canonical.items() if v in gs_ids})
    by_name = {}
    for g, el in gs_entities.items():
        for name in (el.tex_name, el.display_name):
            if name is None:
                continue
            for m in mxl_ids:
                if name == m or canonical_identifier(name) == canonical[m]:
                    by_name.setdefault(g, m)
    claim(by_name)

    progress = True
    while progress:
        free_gs = {g for g in gs_ids if g not in mapping}
        free_mxl = mxl_ids - set(mapping.values())
        gs_pars = gs.get_parameter_values()
        mxl_pars = mxl.get_parameter_values()
        gs_y0 = gs.get_initial_conditions()
        mxl_y0 = mxl.get_initial_conditions()
        progress = claim(
            _unique_pairs(
                {g: g.lower() for g in free_gs},
                {m: canonical[m].lower() for m in free_mxl},
            )
        )
        progress |= claim(
            _unique_pairs(
                {g: gs_pars[g] for g in free_gs if g in gs_pars},
                {m: mxl_pars[m] for m in free_mxl if m in mxl_pars},
            )
        )
        progress |= claim(
            _unique_pairs(
                {g: gs_y0[g] for g in free_gs if g in gs_y0},
                {m: mxl_y0[m] for m in free_mxl if m in mxl_y0},
            )
        )
        identity = {m: m for m in mxl_ids}
        progress |= claim(
            _unique_pairs(
                {
                    g: _signature(gs_entities[g], mapping)
                    for g in free_gs
                    if g in gs_entities
                },
                {
                    m: _signature(mxl_entities[m], identity)
                    for m in free_mxl
                    if m in mxl_entities
                },
            )
        )

    return greensloth.NameMap(
        slug=slug,
        model=model,
        to_mxlmodels=mapping,
        only_greensloth=sorted(gs_ids - set(mapping)),
        only_mxlmodels=sorted(mxl_ids - set(mapping.values())),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("slugs", nargs="*", default=list(greensloth.SLUGS))
    parser.add_argument("--stage", action="store_true", help="stage and export first")
    parser.add_argument("--force", action="store_true", help="overwrite existing maps")
    args = parser.parse_args()
    if args.stage:
        pipeline.export_py([greensloth.stage(s) for s in args.slugs])
    for slug in args.slugs:
        if (greensloth.MAPS / f"{slug}.json").exists() and not args.force:
            print(f"{slug}: map exists, skipped (--force to overwrite)")  # noqa: T201
            continue
        nm = seed(slug)
        nm.dump()
        print(  # noqa: T201
            f"{slug}: {len(nm.to_mxlmodels)} matched, "
            f"{len(nm.only_greensloth)} only in green-sloth, "
            f"{len(nm.only_mxlmodels)} only in mxl-models"
        )


if __name__ == "__main__":
    main()
