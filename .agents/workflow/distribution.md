# Distribute and hand off GitHub issues

The roster in `.agents/team.json` is the shared source of truth for human owners and check-ins. Never infer a person's presence from GitHub login, commits, or an agent session. `working` requires a timezone-aware `until` timestamp; after that instant the person is away. `away` is immediate. Missing presence is unknown: never assign new work to that member, and do not infer that their existing work should move.

## Publish with `/to-tickets`

1. Check the configured repository, roster, authenticated `gh`, and `docs/agents/issue-tracker.md`. If no roster exists, ask for real participants; never invent identities. Configure one or more human participants, capacities, skills, and check-ins. Do not distribute for a non-GitHub tracker.
2. Publish the approved GitHub issues in dependency order. Apply `ready-for-agent` and put exactly one single-line HTML comment in each issue body, with its real blocker issue numbers (not PR numbers):

   `<!-- agent-distribution: {"skills":["backend"],"estimate":1,"blocked_by":[12]} -->`

   `skills` is the required skill list (`[]` means no restriction); `estimate` is a positive effort weight (1 if unknown). `blocked_by` is `[]` if no blockers. The metadata must agree with the native blocking edges. Add it during creation; the reconciler skips issues without valid unambiguous metadata. If a dependency is cross-repository, leave it for manual handling.
3. After creation, save a UTF-8 JSON batch manifest with actual numbers and the same `skills`, `estimate`, and `blocked_by` values, e.g. `.scratch/<feature>/assignment-manifest.json`; see `.agents/workflow/tickets.example.json`.
4. Run `python .agents/workflow/distribute.py --team .agents/team.json --tickets <manifest> --apply` from the repo root. Without `--apply` it previews. Report assignments and any waiting, changed, failed, or skipped tasks. The script verifies target users and issue state and rechecks immediately before a write. Do not claim an agent was started or a PR was created.

## Automatic handoff

`.github/workflows/availability-reconcile.yml` runs on a roster push to the default branch, manually, and approximately every 10 minutes. GitHub may delay or disable scheduled workflows. It fetches **open issues in the configured repository** labeled `ready-for-agent`; it skips pull requests, issues with missing/ambiguous metadata and cross-repo blockers. It checks native blocking links as well as metadata. The workflow runs only with the repository's `GITHUB_TOKEN`, with `contents: read` and `issues: write`. A copied template needs `.agents/team.json` committed to the default branch and GitHub Actions enabled; the supplied example is not an active roster.

Only participants with an unexpired `working` check-in and all required skills are eligible. The script balances estimated load in the selected batch by relative capacity. Blocked issues may have an owner for planning, but their implementation waits for all blockers. It keeps an available owner's assignment. If the single known owner's state is `away` or their check-in expired, it transfers the assignment to an eligible available person. If no one qualifies, the current owner is preserved and the report says `waiting_for_available`; unassigned work remains unassigned. Unknown owners, missing presence, and multiple assignees are left untouched. Closed issues are ignored.

Reassigning an issue does not move a branch, stop an agent, transfer uncommitted work, merge a PR, or perform a handoff conversation. The new owner must check the issue and linked PR before starting. The script does not automatically start or message another person or agent. Keep only issues the team consents to hand off under `ready-for-agent`; remove that label for work which must stay with its owner.

## Check in / leave

Use **Actions → Set availability → Run workflow** on the default branch: `working` checks in the initiating account for 8 hours and requires an empty `login`; `away` marks the initiating account away when `login` is empty, or the specified GitHub login when provided. Alternatively run `gh workflow run availability.yml -f status=working`, `gh workflow run availability.yml -f status=away`, or `gh workflow run availability.yml -f status=away -f login=LOGIN`. The affected login must match one roster member; any participant with permission to dispatch the workflow can mark another member away. Verify **Set availability** and the subsequent **Reconcile issue owners** run; dispatching a workflow does not wait for its result. Re-running an old run repeats its original actor and inputs.

For short shell commands, load `.agents/workflow/aliases.ps1` (PowerShell dot-sourcing) or source `.agents/workflow/aliases.sh` (Bash) once per shell; `on`, `off`, and `off LOGIN` dispatch the same workflow. The repository is resolved from the current directory.

The availability workflow needs `contents: write` and `actions: write`; the default branch must allow its `GITHUB_TOKEN` to push. It retries concurrent push conflicts and explicitly dispatches reconciliation because token-generated pushes do not trigger the push workflow. If the dispatch fails after saving, run reconciliation manually. As a fallback, use `python .agents/workflow/availability.py --team .agents/team.json --login LOGIN --hours 8` or `--away`, then publish the roster via the repository's normal process. `--hours` accepts a duration up to 24 hours; the stored timestamp is UTC.

Expiration is handled by the scheduled run, not instantaneously. A fresh shift requires a fresh check-in. To preview or run locally, use `python .agents/workflow/reconcile.py --team .agents/team.json` or add `--apply`. Review workflow logs for skipped or waiting tasks. No issue is altered if the roster is missing, the target repository does not match GitHub Actions, or required permissions are unavailable.

## Concurrency and scope

GitHub Actions serializes this workflow, but a local run and a scheduled run are not mutually locked. Avoid running two dispatchers on the same issues. GitHub issue updates are not an atomic compare-and-swap: the script re-reads immediately before writing and verifies after, but simultaneous outside edits can race or a partial write can occur. Inspect any `failed`, `skipped_changed`, or `conflict_after_write` result before retrying. Distribution considers only the issues in the selected batch (or labeled queue), not all work elsewhere.
