# Team workflow

The team tracks work in GitHub Issues and GitHub Projects. Resolve the target repository explicitly before creating issues or changing assignments.

The shared skill library is in `.agents/skills/`. For the main flow use `grill-with-docs`, `to-spec`, `to-tickets`, `implement`, `code-review`, and `retro` when requested. The repository's `to-tickets` includes the distribution step in `.agents/workflow/distribution.md`.

Maintain the project-specific tracker and domain settings in `docs/agents/`; use `/setup-matt-pocock-skills` on first setup. The team roster is `.agents/team.json`: its members, their team roles, and the `roles` catalog; the example file is not a real roster. Domain terms are in `GLOSSARY.md`.

One ticket has one human owner and needs at most one team role; an owner may use any authorized coding harness. Each concurrent implementation uses a separate branch and checkout or worktree. Respect blocking dependencies and keep a slice's shared contract in its slice issue. To hand off a ticket, remove its owner and distribution assigns it again. Review changes and run relevant tests before merging.
