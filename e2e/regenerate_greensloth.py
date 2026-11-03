"""Regenerate green-sloth's model.ts files from mxl-models.

    uv run python -m e2e.regenerate_greensloth [slug ...]

Writes `src/lib/models/<slug>/model.ts` (and, for a model with data, its
`model.data.json`) in the sibling green-sloth checkout, moves the id references in its `meta.ts` over to the generated ids, formats
the files with green-sloth's own prettier and refreshes `model.mxl.json`
(`npm run generate:mxl`, then prettier). Review the green-sloth diff before
committing.
"""

from __future__ import annotations

import argparse
import subprocess

from e2e import greensloth


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("slugs", nargs="*", default=list(greensloth.SLUGS))
    args = parser.parse_args()

    files = []
    for slug in args.slugs:
        model_ts = greensloth.GREENSLOTH_MODELS / slug / "model.ts"
        code, data = greensloth.generate(slug)
        model_ts.write_text(code)
        data_file = model_ts.with_name(greensloth.DATA_FILE)
        if data is not None:
            data_file.write_text(data)
            files.append(data_file)
        else:
            data_file.unlink(missing_ok=True)
        renamed = greensloth.migrate_ids(slug)
        files += [model_ts, model_ts.with_name("meta.ts")]
        print(f"{slug}: model.ts regenerated, meta.ts ids renamed: {renamed}")  # noqa: T201

    cwd = greensloth.GREENSLOTH
    subprocess.run(  # noqa: S603
        ["npx", "prettier", "--write", *map(str, files)],  # noqa: S607
        cwd=cwd,
        check=True,
    )
    subprocess.run(["npm", "run", "generate:mxl"], cwd=cwd, check=True)  # noqa: S607
    # generate:mxl writes numbers as JSON.stringify does (6.022e+23); format them
    # the way green-sloth's prettier (and sync.sh) leaves them, so they don't flap.
    subprocess.run(
        ["npx", "prettier", "--write", "src/lib/models/*/model.mxl.json"],  # noqa: S607
        cwd=cwd,
        check=True,
    )


if __name__ == "__main__":
    main()
