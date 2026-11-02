# Distribute GitHub tickets

The roster in `.agents/team.json` is the shared source of truth for team members and their team roles. A team role is one key of its `roles` catalog, whose value describes what the role covers. Never invent members or roles, and never assign an agent as an owner. Team roles are unrelated to the triage roles of `/triage`, which are label states. Name slices, tickets, verification tickets, contracts and owners with the terms of `GLOSSARY.md`; why slices are split into role tickets is recorded in `docs/adr/0001-role-tickets-within-slices.md`.

## Ticket metadata

A ticket that should get an owner carries the `ready-for-agent` label and exactly one single-line HTML comment in its body:

`<!-- agent-distribution: {"role":"backend","estimate":2} -->`

- `role` is one key of the catalog, or `null` when any member may take the ticket.
- `estimate` is a positive relative effort weight (1 if unknown).
- A verification ticket also lists the other tickets of its slice and has `role: null`: `{"role":null,"estimate":1,"parts":[11,12]}`.

Blockers live only in GitHub's native blocking links. Distribution ignores them: a blocked ticket gets an owner for planning, and its owner starts after the blockers close. Issues without valid metadata, with an unknown role, and pull requests are skipped and listed under `skipped` in the report.

## Publish with `/to-tickets`

1. Check the configured repository, the roster, authenticated `gh`, and `docs/agents/issue-tracker.md`. If no roster exists, ask for the real participants and their roles; never invent identities. Do not distribute for a non-GitHub tracker.
2. Publish the approved slices in dependency order, blockers first:
   - A slice with one ticket is published as that ticket.
   - A slice with several tickets is first published as a slice issue holding its behaviour, contract and acceptance criteria, with no `ready-for-agent` label and no metadata. Every ticket of the slice is its sub-issue and points to it for the contract.
   - If the source was an existing issue, each slice issue (or single-ticket slice) is that issue's sub-issue.
   - Publish the role tickets of a slice before its verification ticket, so that `parts` and the blocking links use real numbers.
3. Publishing with the label starts **Distribute tickets** in GitHub Actions. Then run the read-only preview `python .agents/workflow/distribute.py --team .agents/team.json` and report each ticket's owner: an assigned ticket shows its actual owner, an unassigned one the planned owner. Report `no_member_with_role` and skipped tickets. Do not run `--apply` locally while the workflow is enabled, and do not claim that an agent was started or a PR was created.

## How distribution works

`.github/workflows/distribute.yml` runs the distributor with `--apply`; its triggers are listed in the workflow. Each run reads every open `ready-for-agent` issue of the configured repository in issue-number order:

- A ticket with an owner is never changed; its estimate counts toward the owner's load.
- An unassigned ticket goes to the member with the lowest load ÷ `capacity` among members who have its role, or among all members for `role: null`. Ties go to the alphabetically first login.
- A verification ticket goes to the least-loaded roster member who owns one of its parts, including owners planned earlier in the same run and owners of closed parts. Without such a member it is distributed like any other ticket.
- When no member has the role, the ticket stays unassigned and is reported as `no_member_with_role`.

Before each write the script re-reads the issue and skips it unless it is still open and unassigned; after the write it verifies the result. A login that cannot be assigned in the repository fails only its own tickets. Inspect any `failed`, `skipped_changed` or `conflict_after_write` result before rerunning. A copied template needs `.agents/team.json` committed to the default branch and GitHub Actions enabled. No issue is altered if the roster is missing or invalid, or if its repository does not match the Actions repository.

## Closing parents

A ticket's PR says `Closes #<ticket>`. `.github/workflows/close-parents.yml` runs whenever an issue closes: if every sub-issue of its parent is closed, it closes the parent, then repeats for that parent's parent. So the last closed ticket of a slice closes the slice issue, and the last closed slice closes the spec. It never closes a parent in another repository or a `wayfinder:map` issue. A PR that implements an issue directly, without sub-issues, says `Closes #<issue>` itself.

## Handoff

To hand off a ticket, remove its owner in GitHub and the workflow distributes it again. Remove a departing member from `.agents/team.json` first, otherwise they can get the ticket back. To pick the new owner yourself, add them before removing the old one. A handoff does not move a branch, stop an agent or transfer uncommitted work; the new owner checks the issue and any linked PR before starting. Remove `ready-for-agent` from work that must not be distributed.

## Concurrency

GitHub Actions serializes the workflow, but a local `--apply` run is not locked against it. GitHub issue updates are not an atomic compare-and-swap: the script re-reads before writing and verifies after, but simultaneous outside edits can still race.
