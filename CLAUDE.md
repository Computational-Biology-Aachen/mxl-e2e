# CLAUDE.md

Cross-repo end-to-end tests: mxl-models -> model.ts (MxlPy) -> model-gen.py (mxlweb-core) -> compare, and green-sloth's model.ts == the codegen of mxl-models. See README.md for the pipeline.

- Lives at `misc/mxl-e2e` in the 0-admin meta-repo and uses path dependencies on the sibling repos (`pyproject.toml` `[tool.uv.sources]`, `package.json` `file:`), so it always tests the local working trees. mxlweb-core is imported from source (`tsx --conditions=svelte`), no build needed, but `pkg-js/mxlweb-core` needs its own `npm ci`.
- Commands: `uv run pytest`, `uv run ruff format`, `uv run ruff check --fix`.
- `e2e/models.py` is an explicit list; a model is only covered once added there.
- `xfails.toml` records accepted differences as strict xfails. Don't add entries to hide codegen bugs; fix the codegen (MxlPy `meta/_via_sym_repr.py`, mxlweb-core `buildMxlpy`) instead. Never hand-edit mxl-models or green-sloth models to make this suite pass.
- green-sloth's overlapping models are generated from mxl-models (`uv run python -m e2e.regenerate_greensloth`); mxl-models is the single source, so add missing information (display names, sliders, units, docstrings) there, never in green-sloth's model.ts.
- `maps/<slug>.json` (green-sloth's old hand-written id -> generated id) only list ids that changed, for the four models whose ids changed on first generation; regeneration uses them to migrate `meta.ts` references. New models need no map.
- Canonical identifier rules: mxl-schemas `v1/identifiers.json`, implemented in `mxlpy.meta.identifiers` and mxlweb-core `src/identifiers.ts`.
