# GitHub Baseline: CI/CD + Security Hardening

> TL;DR: this repo now includes CI (`.github/workflows/ci.yml`), security baseline + optional CodeQL (`.github/workflows/security.yml`), deploy gates with environments (`.github/workflows/deploy.yml`), and Dependabot (`.github/dependabot.yml`). You still need to enforce branch and security settings in GitHub UI.

## Problem / Context

Without mandatory checks and security controls in GitHub, `main` can receive unreviewed changes, tests can be skipped, and vulnerable dependencies/secrets can slip into history.

This baseline aligns SISEM with the expected flow: PR mandatory to `main`, domain-first governance, and guardrails compatible with SDD + Engram (Jira is no longer used).

## Solution / Implementation

### 1) Workflows included in the repo

- `CI` workflow (`.github/workflows/ci.yml`) runs on `pull_request` and `push` to `main`:
  - Job `frontend`: Bun install, lint, tests in non-watch mode (`bun run test:run`).
  - Job `backend`: Python setup, dependencies install, Django tests.
  - Job `docker-compose-validate`: `docker compose config`.
- `Security` workflow (`.github/workflows/security.yml`) runs on `pull_request`, `push` to `main`, and weekly schedule:
  - Job `security-baseline` (always-on, does not depend on GitHub Advanced Security).
  - Job `codeql-javascript-typescript` (optional, only if repository variable `ENABLE_CODEQL=true`).
  - Job `codeql-python` (optional, only if repository variable `ENABLE_CODEQL=true`).
- `Deploy` workflow (`.github/workflows/deploy.yml`):
  - `deploy-staging`: automatic on push to `main` and manual via dispatch target `Staging`.
  - `deploy-production`: manual only via dispatch target `Production`.
  - Both jobs require environment-level secrets/vars and run through GitHub Environment protection rules.
- Dependabot config (`.github/dependabot.yml`) for:
  - npm in `/frontend`
  - pip in `/backend`
  - GitHub Actions in `/`

### 2) Ruleset / Branch protection recommended for `main`

Use either a repository ruleset (preferred) or classic branch protection rule, with the same effective policy:

- Require a pull request before merging: ON
- Require approvals: ON (minimum `1`)
- Dismiss stale approvals when new commits are pushed: ON
- Require review from Code Owners: ON
- Require status checks to pass: ON
- Require branches to be up to date before merging: ON
- Require conversation resolution before merging: ON
- Require signed commits: ON (recommended)
- Require linear history: ON (recommended when squash/rebase only)
- Allow force pushes: OFF
- Allow deletions of `main`: OFF
- Lock branch: OFF (keep normal PR flow)
- Do not bypass for admins unless there is a strict operational reason

### 3) Required status checks (exact names)

After the first run of each workflow, set these checks as required:

- `CI / frontend`
- `CI / backend`
- `CI / docker-compose-validate`
- `Security / security-baseline`

Add CodeQL checks as required only after enabling Code scanning and setting `ENABLE_CODEQL=true`:

- `Security / codeql-javascript-typescript`
- `Security / codeql-python`

### 4) Merge strategy settings

Repository Settings -> General -> Pull Requests:

- Allow squash merging: ON (recommended default)
- Allow merge commits: OFF (recommended)
- Allow rebase merging: ON (optional, if your team wants clean linear commits)
- Automatically delete head branches: ON
- Always suggest updating pull request branches: ON

If you enable both squash and rebase, define team convention in `docs/guides/pr-merge-governance.md` to avoid inconsistent history.

### 5) Security features to enable in GitHub UI

Settings -> Security & analysis:

- Dependency graph: ON
- Dependabot alerts: ON
- Dependabot security updates: ON
- Code scanning (CodeQL): ON (required before enabling `ENABLE_CODEQL=true`)
- Secret scanning: ON
- Push protection for secret scanning: ON
- Private vulnerability reporting: ON (if repository visibility and plan support it)

### 6) Environments and deployment protections

Create two environments in Settings -> Environments:

- `staging`
  - Required reviewers: optional (recommended `1` if shared staging)
  - Deployment branches: selected branches (`main` or release branch model)
  - Environment secrets: only non-production secrets
- `production`
  - Required reviewers: ON (at least `1`, ideally `2`)
  - Wait timer: optional (for controlled releases)
  - Deployment branches: selected branches/tags only
  - Restrict environment secrets to production only

Use environment-scoped secrets/variables instead of repository-wide secrets whenever possible.

If your GitHub plan does not support required reviewers or wait timer for environments, keep branch policy protection enabled (`main` only) and enforce approval at PR level.

### 7) Environment config required by `deploy.yml`

The deploy workflow expects these values in each environment.

Environment secrets (required):

- `SSH_HOST`
- `SSH_USER`
- `SSH_PRIVATE_KEY`

Environment variables (required):

- `DEPLOY_PATH` (absolute path in remote host where the repository is cloned)
- `SSH_PORT` (usually `22`)

Optional repository variable:

- `ENABLE_CODEQL` (`true` to run CodeQL jobs, unset/false to skip)
- `ENABLE_STAGING_DEPLOY` (`true` to enable deploy-staging job)
- `ENABLE_PRODUCTION_DEPLOY` (`true` to enable deploy-production job)

The workflow will fail fast with a clear error list if any required secret/variable is missing.

## Examples

### Checklist for initial hardening rollout

1. Push these baseline files to the repository.
2. Open a PR and verify these 4 checks run and pass (`frontend`, `backend`, `docker-compose-validate`, `security-baseline`).
3. Configure ruleset for `main` and mark those 4 checks as required.
4. Enable Code scanning in GitHub UI, set repository variable `ENABLE_CODEQL=true`, and then add the 2 CodeQL checks as required.
5. Enable security features under Security & analysis.
6. Create `staging` and `production` environments with reviewer protections.
7. Add required environment secrets/vars for `Staging` and `Production`.
8. Merge PR using squash (recommended).

### Fast verification after setup

- Create a test PR from a feature branch.
- Confirm merge is blocked until required checks pass and approval is present.
- Confirm direct push to `main` is blocked.

## References

- `.github/workflows/ci.yml`
- `.github/workflows/security.yml`
- `.github/workflows/deploy.yml`
- `.github/dependabot.yml`
- `docs/guides/pr-merge-governance.md`
