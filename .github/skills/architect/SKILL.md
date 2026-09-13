---
name: architect
description: 'Run a senior-engineer architecture thinking session before implementation. Use when a developer wants to clarify a feature, align terminology, surface consequential design decisions, produce an implementation blueprint, and wait for explicit confirmation before coding.'
argument-hint: '[feature or change to think through]'
user-invocable: true
---

# Architecture Thinking Session

## Purpose

Help a developer and senior engineer form the same mental model before implementation begins. This is a focused thinking session, not an interrogation or a full specification exercise.

## Operating Rules

- Read the feature description and available context before asking questions.
- Do not ask about facts already answered by documentation or existing code.
- Ask only about decisions that can change the implementation direction.
- Ask one decision question at a time and explain the recommended approach first.
- Update the working understanding immediately when the developer corrects a term or decision.
- Stop when all implementation-changing decisions are resolved.
- Never begin implementation until the developer explicitly confirms the plan.

## Procedure

### 1. Understand What Exists

Before saying anything substantive:

1. Read the requested feature or change.
2. Inspect relevant context files, documentation, existing code, tests, and configuration.
3. Identify what already exists, what must be added, and which constraints are already established.
4. Avoid asking questions that the available context already answers.

If the request does not identify a usable feature or change, ask what outcome the skill should produce before proceeding.

### 2. Align on Language

Identify 3-5 terms from the request that could reasonably be interpreted in more than one way. Define each according to the inspected context and ask the developer to confirm.

Use this shape:

> Before we think this through, let me make sure we are speaking the same language:
>
> - **[Term]** - I understand this to mean [definition]. Is that right?
> - **[Term]** - I am treating this as [definition]. Does that match what you have in mind?

Wait for the developer's response. Correct the working definitions immediately. Do not move to implementation decisions until the terminology is aligned.

If fewer than three terms are genuinely ambiguous, present only the terms that need confirmation rather than inventing ambiguity.

### 3. Resolve Consequential Decisions

Work through decisions in order of downstream impact. For each decision, provide a recommendation and reasoning, then ask one question and wait for the answer.

Use this shape:

> **[Decision that needs to be made]**
>
> My thinking: [recommended approach and why it fits the context].
>
> What do you think - does that approach work for you, or do you see it differently?

Typical decision areas include:

- Scope and user-visible behavior
- Ownership and boundaries between modules or services
- Data shape, state, persistence, and API contracts
- Failure, validation, authorization, and compatibility behavior
- Testing strategy and acceptance signals
- Rollout, migration, or operational constraints

Skip a decision when an earlier answer makes it irrelevant. Treat details that can be decided safely during implementation as assumptions rather than blocking questions.

### 4. Declare Readiness

When every decision that would change the implementation has been resolved, say exactly:

> Blueprint ready.

Do not continue asking questions for completeness once the plan is solid enough to start.

### 5. Produce the Blueprint

Immediately after declaring readiness, present:

```markdown
## Implementation Plan - [Feature Name]

### What we are building
[One clear paragraph describing exactly what will be built]

### Language we agreed on
- [Term]: [agreed definition]
- [Term]: [agreed definition]

### Decisions made
- [Decision]: [what was decided and why]
- [Decision]: [what was decided and why]

### Assumptions
- [Anything assumed but not explicitly confirmed]

### How to build it
1. [Ordered implementation step]
2. [Ordered implementation step]
3. [Validation and completion step]
```

Keep the blueprint clear and implementation-oriented without expanding it into a full specification.

### 6. Gate Implementation

Ask the developer to confirm the plan explicitly. Do not edit files, run implementation commands, or start building before confirmation.

After explicit confirmation, implementation may begin using the repository's established patterns and the agreed decisions. The skill's responsibility ends with the confirmed blueprint unless the developer continues into implementation.

## Completion Criteria

The session is complete when:

- Relevant existing context was inspected.
- Ambiguous project language was confirmed or corrected.
- Every decision with meaningful implementation impact was resolved.
- A concrete, ordered implementation plan was presented.
- The developer was asked for explicit confirmation before implementation.
