---
version: "0.1"
tier: C
title: Rename project from life-cli to life
owner: benthepsychologist
goal: Remove '-cli' suffix from project name across all references
labels: []
project_slug: life
spec_version: 1.0.0
created: 2025-12-11T21:13:21.806208+00:00
updated: 2025-12-11T21:13:21.806208+00:00
orchestrator_contract: "standard"
repo:
  working_branch: "feat/rename-to-life-no-cli"
---

# Rename project from life-cli to life

## Objective

> Rename the project from `life-cli` to `life`, removing the `-cli` suffix from the package name, repository name, and all references throughout the codebase.

## Acceptance Criteria

- [ ] `pyproject.toml` updated with new package name and URLs
- [ ] All code references updated (version string, error messages, docstrings)
- [ ] All documentation updated (README, CONTRIBUTING, ARCHITECTURE, QUICK_REFERENCE)
- [ ] All spec/AIP files updated with new project_slug and URLs
- [ ] CI green (lint + unit)
- [ ] GitHub repository renamed from `life-cli` to `life` *(do last - breaks local session)*
- [ ] Git remote updated to point to new repository *(do last - after repo rename)*

## Context

### Background

The project is currently named `life-cli` but the `-cli` suffix is redundant since:
1. The command is already just `life` (not `life-cli`)
2. The project is clearly a CLI tool without needing it in the name
3. Shorter name is cleaner for package installation (`pip install life` vs `pip install life-cli`)

### Scope

**Source files:**
- `pyproject.toml` - package name and GitHub URLs
- `src/life/cli.py:118` - version output string (`life-cli version` → `life version`)
- `src/life_jobs/__init__.py:2` - module docstring
- `src/life_jobs/generate.py:41` - pip install error message

**Tests:**
- `tests/test_generate.py:37` - expected error message assertion

**Documentation:**
- `README.md` - clone URLs, install instructions, title, ~20 references
- `CONTRIBUTING.md` - clone URLs, directory structure, spec reference
- `docs/ARCHITECTURE.md` - architecture description
- `docs/QUICK_REFERENCE.md` - paths, working directory, repo references

**Examples:**
- `examples/life.yml` - comment

**Spec files (12 files):**
- `.specwright/specs/emails-and-batch-send.md` - project_slug, references
- `.specwright/specs/email-templates-directory.md` - project_slug
- `.specwright/specs/regular-assessment-schedule.md` - project_slug
- `.specwright/specs/cockpit-scripts-to-verbs.md` - project_slug, multiple references
- `.specwright/specs/llm-processing-ho.md` - project_slug, multiple references
- `.specwright/specs/life-gen-commands-spec.md` - project_slug
- `.specwright/specs/config-management-spec.md` - reference
- `.specwright/specs/job-runner-spec.md` - title, goal, multiple references
- `.specwright/specs/projection-writeback.md` - project_slug, file paths
- `.specwright/specs/life-jobs-verbs-refactor.md` - project_slug, goal, references
- `.specwright/specs/life-cli-initial-spec.md` - references (keep filename for history)

**AIP files (8 files):**
- `.specwright/aips/life-jobs-verbs-refactor.yaml` - aip_id, project_slug, repo URL
- `.specwright/aips/cockpit-scripts-to-verbs.yaml` - aip_id, constraints
- `.specwright/aips/life-cli-initial-spec.yaml` - constraints, repo URL
- `.specwright/aips/life-gen-commands-spec.yaml` - aip_id, project_slug, repo URL
- `.specwright/aips/job-runner-spec.yaml` - background, goal, repo URL
- `.specwright/aips/llm-processing-ho.yaml` - aip_id, project_slug, repo URL
- `.specwright/aips/projection-writeback.yaml` - aip_id, project_slug, repo URL
- `.specwright/aips/email-templates-directory.yaml` - aip_id, project_slug, repo URL

**Other:**
- `.specwright/aips/001-life-today-command.md` - multiple references

## Plan

> **Note:** Update all internal references first, then rename repo/remote last. The repo rename will break the local git session until the remote is updated.

### Step 1: Update Core Package Files

Update `pyproject.toml`:
- `name = "life-cli"` → `name = "life"` *(already done)*
- Update all GitHub URLs *(already done)*

Update source files:
- `src/life/cli.py:118`: `life-cli version` → `life version`
- `src/life_jobs/__init__.py:2`: docstring `life-cli` → `life`
- `src/life_jobs/generate.py:41`: `life-cli[llm]` → `life[llm]`

### Step 2: Update Tests

Update `tests/test_generate.py:37` to expect `life[llm]` in error message.

### Step 3: Update Documentation

Replace all `life-cli` references with `life` in:
- `README.md` (~20 occurrences)
- `CONTRIBUTING.md` (4 occurrences)
- `docs/ARCHITECTURE.md` (2 occurrences)
- `docs/QUICK_REFERENCE.md` (8 occurrences)
- `examples/life.yml` (1 occurrence)

### Step 4: Update Spec/AIP Files

Update `project_slug: life-cli` → `project_slug: life` and all `life-cli` references in:
- 12 spec files in `.specwright/specs/`
- 8 AIP files in `.specwright/aips/`

For AIP files, also update:
- `aip_id` prefixes (e.g., `AIP-life-cli-*` → `AIP-life-*`)
- `repo.url` values (`life-cli.git` → `life.git`)

### Step 5: Run CI Checks

```bash
ruff check .
pytest -q
```

### Step 6: Rename GitHub Repository *(do last)*

Rename the GitHub repository from `benthepsychologist/life-cli` to `benthepsychologist/life` via GitHub settings.

**Warning:** This will break the local git remote until Step 7 is completed.

### Step 7: Update Git Remote *(do immediately after Step 6)*

```bash
git remote set-url origin git@github.com:benthepsychologist/life.git
```

## Models & Tools

**Tools:** bash, git, gh

## Repository

**Branch:** `feat/rename-to-life-no-cli`

**Merge Strategy:** squash
