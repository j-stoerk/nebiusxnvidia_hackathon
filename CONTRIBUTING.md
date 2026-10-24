# Working together

## Give teammates access

Owner: open [repository access settings](https://github.com/j-stoerk/nebiusxnvidia_hackathon/settings/access), then **Settings > Collaborators > Add people**. Search for each teammate's GitHub username or email, select the correct account, and send the invitation. They must accept it to access this private repository. GitHub Free supports unlimited collaborators on private and public personal repositories. [GitHub invitation instructions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/inviting-collaborators-to-a-personal-repository).

Sharing the URL alone does not grant private-repository access. Collaborators can push changes; keep ownership and access administration with the owner. No invitations have been sent by the data/documentation setup.

## Choose a development environment

For minimal laptop storage, accept the invitation, open **Code > Codespaces > Create codespace on main**, and work in the browser. Use a small machine, monitor included quotas, and stop the Codespace when finished. Commit and push work before deleting a Codespace. External data and uncommitted work are not backed up by GitHub commits. See [storage](docs/storage.md).

For local development:

```powershell
git clone https://github.com/j-stoerk/nebiusxnvidia_hackathon.git
cd nebiusxnvidia_hackathon
python scripts/validate_data.py
```

Use your own GitHub login/SSH setup. Share environment-variable names through `.env.example`; exchange actual API credentials through an agreed private channel or issue individual keys. An API token belongs in environment variables or Codespaces secrets, never in Git, an issue, or a pull request.

## Use one branch per change

```powershell
git switch main
git pull --ff-only
git switch -c feature/charging-optimizer
# Make the change, then validate it.
python scripts/validate_data.py
git add path/to/changed-file
git commit -m "Add charging optimizer"
git push -u origin feature/charging-optimizer
```

Open a pull request into `main`, describe the behavior and validation, and ask a teammate to review. Resolve conflicts on the feature branch. Agree on shared CSV/API schemas before parallel implementation. Prefer small PRs and avoid simultaneous rewrites of the same file. Optional branch protection depends on your GitHub plan; the PR convention works without it.

Suggested work areas: agent/tool integration; scheduling/baseline/evaluation; React/dashboard; API/simulation/deployment. This is a suggested division, not an assumption about team size. Use Issues with an owner and clear acceptance criteria. Agree on one Devpost team representative separately; GitHub access does not register someone for the hackathon.

## Before submission

Check the [submission checklist](docs/hackathon-rules.md), finish the runnable app instructions, and coordinate the public repository release with the owner. Keep the demo available throughout judging and preserve a tag/commit identifying the submitted version.
