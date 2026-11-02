# Team workflow

The team tracks work in GitHub Issues and GitHub Projects. Resolve the target repository explicitly before creating issues or changing assignments.

The shared skill library is in `.agents/skills/`. For the main flow use `grill-with-docs`, `to-spec`, `to-tickets`, `implement`, `code-review`, and `retro` when requested. The repository's `to-tickets` includes the distribution step in `.agents/workflow/distribution.md`.

Maintain the project-specific tracker and domain settings in `docs/agents/`; use `/setup-matt-pocock-skills` on first setup. The team roster is `.agents/team.json`; the example file is not a real roster. For team roles, owners, handoff and closing of parent issues, follow `.agents/workflow/distribution.md`. Before naming a domain concept in an issue, PR, test or document, take its term from `GLOSSARY.md`.

One ticket has one human owner; an owner may use any authorized coding harness. Each concurrent implementation uses a separate branch and checkout or worktree. Respect blocking dependencies and keep a slice's shared contract in its slice issue. A PR body names each issue it implements with `Closes #N`. Review changes and run relevant tests before merging.
