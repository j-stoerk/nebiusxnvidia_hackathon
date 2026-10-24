# Optional GitHub Actions workflows

These templates are inactive in this folder. Data preparation and validation already work locally and in Codespaces using Python, with no Actions setup.

To enable automation, the repository owner can use GitHub's web editor to create `.github/workflows/validate-data.yml` and `.github/workflows/fetch-reference-data.yml` with the corresponding template contents. Alternatively, use an authenticated Git credential authorized to write workflows. The CLI login used during setup had repository access but no `workflow` scope; the initial workflow push was rejected, so it was replaced with these inactive templates.

`validate-data.yml` checks committed data and deterministic regeneration on push/PR. `fetch-reference-data.yml` is manually triggered, downloads small public NLR/NASA slices on a cloud runner, and keeps a seven-day artifact including provenance and the NLR notice. It does not commit files, fetch private ACN data, or publish OPSD observations. GitHub Actions minutes/artifact storage remain subject to the account's quotas. No workflow has been enabled or run by this setup.
