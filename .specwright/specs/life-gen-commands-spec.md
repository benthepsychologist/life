---
tier: C
title: life gen commands spec
owner: benthepsychologist
goal: Implement life gen commands spec
labels: []
project_slug: life
spec_version: 1.0.0
created: 2025-11-11T18:57:13.364422+00:00
updated: 2025-11-11T18:57:13.364422+00:00
---

# life gen commands spec

## Objective

> Implement life gen commands spec

## Acceptance Criteria

- [ ] CI green (lint + unit)
- [ ] No protected paths modified
- [ ] 70% test coverage achieved

## Context

### Background

> Describe the current state and why this work is needed now.

### Constraints

- No edits under protected paths (`src/core/**`, `infra/**`)

## Plan

### Step 1: Planning and File Analysis [G0: Plan Approval]

**Prompt:**

Outline minimal file-touch set and quick test plan.
Produce a one-paragraph plan and list of files to touch (<= 5).

**Outputs:**

- `artifacts/plan/plan-01.md`

### Step 2: Prompt Engineering [G0: Plan Approval]

**Prompt:**

Generate basic prompts for implementation (auto-approved for Tier C).
Create simple, direct prompts for the implementation tasks.

**Outputs:**

- `artifacts/prompts/coding-prompts.md`

### Step 3: Implementation [G1: Code Readiness]

**Prompt:**

Implement small change; keep diff small and isolated.

**Commands:**

```bash
ruff check .
pytest -q
```

**Outputs:**

- `artifacts/code/quick-release-note.md`

### Step 4: Testing and Validation [G2: Pre-Release]

**Prompt:**

Run quick validation suite.

**Commands:**

```bash
pytest -q --tb=short
```

**Outputs:**

- `artifacts/test/test-pass-confirmation.md`

### Step 5: Governance [G4: Post-Implementation]

**Prompt:**

Minimal documentation (decision log only).

**Outputs:**

- `artifacts/governance/decision-log.md`

## Models & Tools

**Tools:** bash, pytest, ruff

**Models:** (to be filled by defaults)

## Repository

**Branch:** `feat/life-gen-commands-spec`

**Merge Strategy:** squash