# mxl-e2e

End-to-end tests of the codegen pipeline between [MxlPy](https://github.com/Computational-Biology-Aachen/MxlPy) and [mxlweb-core](https://github.com/Computational-Biology-Aachen/mxlweb-core), run against every model in [mxl-models](https://github.com/Computational-Biology-Aachen/mxl-models) and [green-sloth](https://github.com/Computational-Biology-Aachen/green-sloth).

## The pipeline

**Phase 1, round trip** (`tests/test_roundtrip.py`), for every model in `e2e/models.py`:

1. mxl-models model → `model.ts` (`mxlpy.meta.generate_model_code_mxlweb`)
2. `model.ts` → `model-gen.py` (mxlweb-core `buildMxlpy()`, `scripts/export-mxlpy.ts`)
3. compare `model-gen.py` against the original: same ids per kind, parameter values and initial conditions, `get_args` (readouts included) and right-hand side at the initial state plus seeded perturbations, and display names.

Both exporters map names through the same canonical identifier rules (mxl-schemas `v1/identifiers.json`), so the generated model's ids are `canonical_identifier_map(original.ids)`: `"CO2 (dissolved)"` becomes `CO2_dissolved`, with the original name kept as `display_name`.

**Phase 2, green-sloth** (`tests/test_greensloth.py`): for every model in both collections, green-sloth's `model.ts` is generated from mxl-models (`uv run python -m e2e.regenerate_greensloth [slug ...]`), so the two are the same model. mxl-models is the single source, including the display names, sliders and units green-sloth shows. The test checks that the committed `model.ts` is still exactly what the codegen produces, comparing mxlweb-core's `buildMxlJson` of both files: values, expressions, stoichiometry, units, display/LaTeX names and sliders.

`maps/<slug>.json` list the ids green-sloth's hand-written models used where the generated id differs (old id → generated id); only ebenhoeh2014, hahn1987, matuszynska2019 and saadat2021 have one. Regeneration uses them to move green-sloth's own id references (`meta.ts`) to the generated ids; every other id is the same on both sides.

**Known differences** live in `xfails.toml` (phase → model → check → reason) and become strict xfails: a difference that disappears turns the suite red until its entry is removed. Fix differences in the codegen and regenerate, never by hand-editing models.

## Running

The repo expects the [0-admin](https://github.com/Computational-Biology-Aachen) meta-repo layout and tests the sibling working trees directly (`../../pkg-py/MxlPy`, `../../pkg-py/mxl-models`, `../../pkg-js/mxlweb-core`, `../../pages/green-sloth`), uncommitted changes included:

```bash
npm ci --prefix ../../pkg-js/mxlweb-core   # mxlweb-core's own deps
npm ci
uv sync
uv run pytest
```

Generated files land in `build/` (`build/roundtrip/<model>/{model.ts,model-gen.py}`, `build/greensloth/<slug>/{committed,generated}/…`).

## CI

`.github/workflows/e2e.yml` runs nightly, on its own pushes and PRs, and as a reusable workflow that MxlPy, mxl-models, mxlweb-core and green-sloth call on their PRs and pushes to main: the calling repo is checked out at the PR's commit, every other repo at main. green-sloth only runs phase 2. The check is advisory, not a required status check.
