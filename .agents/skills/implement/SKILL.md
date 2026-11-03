---
name: implement
description: "Implement a piece of work based on a spec or set of tickets, or take your next assigned ticket."
disable-model-invocation: true
---

Implement the work described by the user in the spec or tickets.

If the user passes no work and the repository has `.agents/team.json`, take the user's next startable ticket: an open `ready-for-agent` issue assigned to the authenticated `gh` user (`--assignee @me`) whose blockers are all closed, lowest issue number first. Use the tracker doc's list and blocker operations. State its number and title before starting. When no ticket qualifies, list the user's assigned open tickets with their open blockers and stop.

If the user passes a ticket reference, fetch it from the issue tracker and state its title before starting. If the reference is ambiguous, ask. In a repository with `.agents/team.json`, also check that the ticket is assigned to the authenticated `gh` user and that its blockers are all closed; when either check fails, say which one and ask whether to continue.

Call the Skill tool with "tdd" where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, call the Skill tool with "code-review" to review the work.

Commit your work to the current branch.
