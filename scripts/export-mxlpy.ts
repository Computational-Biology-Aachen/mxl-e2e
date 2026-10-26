/**
 * Step 2 of the pipeline: load every `<dir>/model.ts` given on the command
 * line and write its mxlweb-core mxlpy export to `<dir>/model-gen.py`. A
 * model that fails to load or export gets `<dir>/export-error.txt` instead,
 * so one broken model doesn't hide the results of all others.
 */
import { rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

type Exportable = { buildMxlpy(): string };

for (const dir of process.argv.slice(2)) {
  const errorFile = resolve(dir, "export-error.txt");
  rmSync(errorFile, { force: true });
  try {
    const mod = (await import(pathToFileURL(resolve(dir, "model.ts")).href)) as {
      initModel(): Exportable;
    };
    writeFileSync(resolve(dir, "model-gen.py"), mod.initModel().buildMxlpy());
  } catch (err) {
    writeFileSync(errorFile, err instanceof Error ? (err.stack ?? err.message) : String(err));
  }
}
