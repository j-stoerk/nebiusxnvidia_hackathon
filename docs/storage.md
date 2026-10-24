# Storage on a laptop with limited free space

Use the existing [GitHub repository](https://github.com/j-stoerk/nebiusxnvidia_hackathon) for authored source/docs and small generated fixtures. Keep historical observations in ignored `data/external/` and reproduce selected slices when needed. The setup checked roughly 14.5 GiB free on C:, so it avoids model weights, dependency installation, full data archives on disk, and a duplicate checkout.

## What goes where

| Material | Storage |
| --- | --- |
| Source, Markdown, schemas, scripts, MIT license | GitHub, ordinary Git |
| Small synthetic demo datasets and acquisition report | GitHub, ordinary Git |
| Small NLR/NASA demo slices and required notices | GitHub, `data/reference/` |
| OPSD observations and additional source slices | Ignored local folder or a Codespace; URLs, transforms and hashes in acquisition report |
| ACN data and private uploads | Authorized environment only; no raw personal records in Git |
| Full archives, model weights, build output, dependencies | Fetch in cloud only if needed; ignore in Git |
| Future large authorized artifacts | Object storage or Releases after checking rights; lifecycle/retention required |
| Fine-tuning/LoRA corpora and checkpoints | Separate cloud storage, versioned manifests in Git; see forecasting.md |

Pushing a file does not remove it from the working tree or Git history. LFS also has local storage/cache and quotas, so enabling it would not solve laptop space by itself. GitHub warns above 50 MiB and blocks ordinary Git files above 100 MiB; browser uploads have a 25 MiB limit. [GitHub file limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).

## Move development into the browser

Open **Code > Codespaces > Create codespace on main** after committing/pushing work. Run the data commands there. Use separate Codespaces secrets for tokens. No Codespace was created by this setup.

Codespaces uses remote disk. Personal accounts have included quotas, then compute/storage billing; check your account before creating large environments. Stopping halts compute but retained disk still counts; push work and preserve any nonreproducible files before deleting the Codespace. [Billing](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces), [lifecycle](https://docs.github.com/en/codespaces/getting-started/understanding-the-codespace-lifecycle).

An optional **Fetch reference data** Action template is in `workflow-templates/`. Once enabled, it fetches public NLR/NASA slices, validates them, and retains a seven-day artifact including the required NLR notice. It does not download credential-gated ACN data or redistribute OPSD observations. The current GitHub CLI login cannot write active workflows because it lacks the `workflow` scope, so templates are inactive. The owner can copy them into `.github/workflows/` using GitHub's web editor when desired. No scheduled download or paid storage provisioning is configured.

## Reclaim reproducible local data

The external folder is optional and ignored. After checking `data/acquisition-report.json` and confirming you can regenerate it, delete **only** `data/external/` using your file manager to reclaim its small footprint. Keep the scripts and demo fixtures. Avoid deleting the local project until every authored change is pushed and accessible remotely. Full archives are never written by the preparation script; it temporarily holds the NLR ZIP in RAM and streams OPSD.
