---
name: to-tickets
description: Break a plan, spec, or the current conversation into a set of tracer-bullet tickets, each declaring its blocking edges, published to the configured tracker (edges as text in one file per ticket locally, or native blocking links on a real tracker).
disable-model-invocation: true
---

# To Tickets

Break a plan, spec, or conversation into a set of **tickets**: tracer-bullet vertical slices, each declaring the tickets that **block** it.

The issue tracker and triage label vocabulary should have been provided to you. If not, tell the user to run `/setup-matt-pocock-skills`.

## Process

### 1. Gather context

Work from whatever is already in the conversation context. If the user passes a reference (a spec path, an issue number or URL) as an argument, fetch it and read its full body and comments.

### 2. Explore the codebase (optional)

If you have not already explored the codebase, do so to understand the current state of the code. Ticket titles and descriptions should use the project's domain glossary vocabulary, and respect ADRs in the area you're touching.

Look for opportunities to prefactor the code to make the implementation easier. "Make the change easy, then make the easy change."

### 3. Draft vertical slices

Break the work into **tracer bullet** slices, then split each slice into tickets by team role.

<vertical-slice-rules>

- Each slice cuts a narrow but COMPLETE path through every layer (schema, API, UI, tests): vertical, NOT a horizontal slice of one layer
- A completed slice is demoable or verifiable on its own
- Each ticket is sized to fit in a single fresh context window
- Any prefactoring should be done first

</vertical-slice-rules>

Then split each slice into **tickets** by the team roles in the `roles` catalog of `.agents/team.json` (see `docs/adr/0001-role-tickets-within-slices.md`):

- A ticket needs one team role, or none when any member may take it; never more than one. A slice that needs one role (or none) stays a single ticket.
- A slice with several tickets gets a **contract**: how its tickets fit together (API, data shapes), precise enough for them to proceed in parallel. Add a blocking edge between tickets of one slice only when one truly cannot start without the other.
- A slice with several tickets also gets a **verification ticket** with no role, blocked by all its other tickets, that connects the parts and checks the slice end to end. Only the slice as a whole has to be demoable.

Give each ticket its **blocking edges**: the other tickets that must complete before it can start. A ticket with no blockers can start immediately.

**Wide refactors are the exception to vertical slicing.** A **wide refactor** is one mechanical change (rename a column, retype a shared symbol) whose **blast radius** fans across the whole codebase, so a single edit breaks thousands of call sites at once and no vertical slice can land green. Don't force it into a tracer bullet; sequence it as **expand–contract**. First expand: add the new form beside the old so nothing breaks. Then migrate the call sites over in batches sized by blast radius (per package, per directory), each batch its own ticket blocked by the expand, keeping CI green batch to batch because the old form still exists. Finally contract: delete the old form once no caller remains, in a ticket blocked by every migrate batch. When even the batches can't stay green alone, keep the sequence but let them share an integration branch that all block a final integrate-and-verify ticket; green is promised only there.

### 4. Quiz the user

Present the proposed breakdown grouped by slice. For each slice show the behaviour it delivers and, when it has several tickets, a short contract. For each ticket show its title, team role (`—` for none), estimate, and blockers:

```
Slice 1: Registration (a visitor can sign up by email)
  Contract: POST /users {email, password} → 201 {id} | 409
  1a. Registration API       role: backend   estimate: 2  blocked by: —
  1b. Registration form      role: frontend  estimate: 1  blocked by: —
  1c. Connect and verify     role: —         estimate: 1  blocked by: 1a, 1b
```

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Are the team roles right, and does each ticket need only one?
- Is each contract enough for its tickets to proceed in parallel?
- Are the blocking edges correct: does each ticket only depend on tickets that genuinely gate it?
- Should any tickets be merged or split further?

Iterate until the user approves the breakdown.

### 5. Publish the tickets to the configured tracker

For the GitHub tracker, follow `.agents/workflow/distribution.md`: it defines the ticket metadata and label, the slice issue for a slice with several tickets, the sub-issue links, and the publishing order. Without valid metadata distribution intentionally skips the issue.

Publish the approved tickets. **How** depends on the tracker `/setup-matt-pocock-skills` configured; the tickets are the same either way, only the shape of the blocking edges changes:

- **Local files** → write one file per ticket under `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01` in dependency order (blockers first). Each file's "Blocked by" lists the numbers/titles it depends on. Use the per-ticket file template below: one ticket per file, never a single combined file.
- **A real issue tracker (GitHub, Linear, …)** → publish one issue per ticket in dependency order (blockers first) so each ticket's blocking edges can reference real identifiers. Use the platform's native blocking relationship where it has one; otherwise set each ticket's "Blocked by" to the blocking issues. Make each ticket of a multi-ticket slice a sub-issue of its slice issue, and, if the source was an existing issue, make each slice issue or single-ticket slice a sub-issue of the source (tracker doc's operation). Apply the `ready-for-agent` triage label unless instructed otherwise; the tickets are agent-grabbable by construction.

Work the **frontier**: any ticket whose blockers are all done. For a purely linear chain that means top to bottom.

Do NOT close or modify any parent issue.

<local-ticket-template>

# <NN>: <Ticket title>

**What to build:** the end-to-end behaviour this ticket makes work, from the user's perspective, not a layer-by-layer implementation list.

**Blocked by:** the numbers/titles of the tickets that gate this one, or "None (can start immediately)".

**Status:** ready-for-agent

- [ ] Acceptance criterion 1
- [ ] Acceptance criterion 2

</local-ticket-template>

<issue-template>

## Parent

A reference to the slice issue, which holds the contract, or to the source issue for a single-ticket slice. Omit this section when there is neither.

## What to build

The end-to-end behaviour this ticket makes work, from the user's perspective, not layer-by-layer implementation.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Blocked by

- A reference to each blocking ticket, or "None (can start immediately)". Omit this section when blockers were set as native edges.

</issue-template>

<slice-issue-template>

## Parent

A reference to the source issue (if the source was an existing issue, otherwise omit this section).

## What it delivers

The end-to-end behaviour of the slice, from the user's perspective.

## Contract

How the tickets of this slice fit together: endpoints, data shapes, events. Every ticket of the slice builds against this section.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2

</slice-issue-template>

In either form, avoid specific file paths or code snippets: they go stale fast. Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it and note briefly that it came from a prototype. Trim to the decision-rich parts, not a working demo, just the important bits.

### 6. Distribute the published GitHub tickets

Immediately after publishing, follow `.agents/workflow/distribution.md` in this repository. That file is the authoritative procedure for team configuration, ticket metadata, how GitHub Actions assigns owners, and reporting. Run its read-only preview for every published batch and report each ticket's owner. Do not distribute draft tickets, invent team members or roles, or assign agents as people. If configuration or GitHub access is missing, leave existing tickets untouched and explain exactly what is needed to resume.
