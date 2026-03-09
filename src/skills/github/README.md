# CATBot GitHub Skill Module

This package provides the GitHub skill used by the CATBot skills framework.

## Module Layout

- `skill.py`: skill + tool definitions used by `GitHubProjectManager`.
- `service.py`: orchestration layer for git operations, versioning, and GitHub API calls.
- `git_service.py`: local git command wrapper.
- `github_api.py`: minimal GitHub REST API client.
- `version_manager.py`: semantic version handling via `VERSION`.
- `config.py`, `models.py`, `errors.py`: config and typed models/errors.
- `cli.py`: CLI entrypoint.

## CLI Usage

Run with:

```powershell
python -m src.skills.github.cli --workspace . status
python -m src.skills.github.cli --workspace . commit --message "chore: update" --bump patch --push
```

## Environment

See `.env.example` in this folder for expected variables.

Recommended branch/PR-safe defaults:

- `GITHUB_OWNER=andyjm2k`
- `GITHUB_REPO=CATBot`
- `GITHUB_TARGET_REPOSITORY=andyjm2k/CATBot`
- `GITHUB_ENFORCE_BRANCH_PR_FLOW=true`
- `GITHUB_PROTECTED_BRANCHES=main,master`
- `GITHUB_ENFORCE_SENSITIVE_PATH_GUARD=true`

With `GITHUB_ENFORCE_BRANCH_PR_FLOW=true`, the service blocks commits/pushes/PR-heads on protected branches.
With `GITHUB_ENFORCE_SENSITIVE_PATH_GUARD=true`, the service blocks commit/push/PR creation when sensitive path patterns are present (for example `.env`, key/cert files, and secret-like config files, including `config/*.json`).

## Packaging

The skill manifest at `src/skills/manifests/github_project_manager.skill.json` includes:

- `module: "src.skills.github.skill:create_skill"`
- `package_sources: ["src.skills.github"]`

This ensures `.catbotskill` export/import includes the full module, not a single file.
