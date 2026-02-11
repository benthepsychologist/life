---
id: e010-03-life-email
title: "Life Email — JobDef Wrappers via Lorchestra → Egret"
tier: B
owner: benthepsychologist
goal: "Expose lorchestra email.send / email.send_templated / email.batch_send as Life JobDefs (Life is a job runner; no email subcommands)"
branch: feat/egret-integration
repo:
  name: life
  url: workspace/life
status: refined
created: 2026-02-09T00:00:00Z
updated: 2026-02-11T00:00:00Z
---

# e010-03-life-email: Life Email — JobDef Wrappers via Lorchestra → Egret

**Epic:** e010-egret
**Repo:** life
**Branch:** `feat/egret-integration`
**Tier:** B

## Objective

Life has already been migrated to a **generic YAML job runner** (like lorchestra/specwright): `life run <job_id> key=value ...` compiles a JobDef YAML to a JobInstance and executes its steps.

This spec updates Life’s **email** surface to be purely **JobDef wrappers** around the existing lorchestra email jobs, which dispatch through egret.

There are **no** `life email ...` subcommands and **no** local provider calls in Life.

## Problem

1. **Spec drift / wrong assumptions**: The previous spec assumes a verb-based CLI (`life email send|batch`) and local processors (`life_jobs/email.py`) which do not exist in the current Life architecture.
2. **Contract mismatch risk**: lorchestra already defines the canonical payload shapes for `email.send`, `email.send_templated`, and `email.batch_send`; Life must pass payloads that match those contracts exactly.
3. **Batch footgun**: lorchestra `email.batch_send` (as implemented) expects **pre-expanded** `items=[{to, template_vars, idempotency_key?}]` — there is no workman expansion step.
4. **Dry-run confusion**: Life `--dry-run` is a Life-runner mode; it compiles and shows what would run, but does not validate templates, render, or submit to egret.

## Current Capabilities (Actual)

- Life compiles JobDef YAML → JobInstance (steps). Steps can reference prior outputs via `@run.*`.
- Life JobDefs may contain additional dicts beyond `steps`; these are available at compile time via `@self.*`.
- Life supports a `lorchestra.run` step op to execute a lorchestra job by `job_id` with a `payload`.
- Lorchestra already provides these JobDefs and they are the source of truth:
  - `email.send`
  - `email.send_templated`
  - `email.batch_send`

Rendering is handled upstream by lorchestra (`callable: render`). Egret only receives finalized `subject/body/is_html`.

## Proposed build_delta

```yaml
target: "projects/life/life.build.yaml"
summary: "Add Life email JobDefs that call lorchestra email.* jobs"

adds:
  layout:
    - "src/life/jobs/definitions/email.send.yaml"
    - "src/life/jobs/definitions/email.send_templated.yaml"
    - "src/life/jobs/definitions/email.batch_send.yaml"
  kernel_surfaces:
    - "life run email.send -> lorchestra.run(job_id=email.send)"
    - "life run email.send_templated -> lorchestra.run(job_id=email.send_templated)"
    - "life run email.batch_send -> lorchestra.run(job_id=email.batch_send)"
```

## Acceptance Criteria

- [ ] Life exposes email sends as JobDefs invoked via `life run` (no email subcommands):
  - [ ] `life run email.send ...`
  - [ ] `life run email.send_templated ...`
  - [ ] `life run email.batch_send ...`
- [ ] Each Life JobDef dispatches via a `lorchestra.run` step with `job_id` set to the same lorchestra job id.
- [ ] Payloads match lorchestra contracts exactly (see below).
- [ ] Batch send uses `items=[{to, template_vars, idempotency_key?}]` (pre-expanded); no `recipients_file`/workman expansion.
- [ ] Template rendering is done by lorchestra (`callable: render`). Egret never sees templates.
- [ ] Dry-run behavior is documented correctly for Life (compile-only preview; no render/send).


## Life JobDef Payload Contracts

These are the payload shapes Life must accept and pass through unchanged to lorchestra.

### `email.send`

Payload:
- `to` (string)
- `subject` (string)
- `body` (string)
- `is_html` (bool, optional)
- `provider` (string)
- `account` (string)
- `idempotency_key` (string, optional)

### `email.send_templated`

Payload:
- `to` (string)
- `template_path` (string; absolute path)
- `template_vars` (dict)
- `provider` (string)
- `account` (string)
- `idempotency_key` (string, optional)

### `email.batch_send`

Payload:
- `template_path` (string; absolute path)
- `items` (list) where each item is:
  - `to` (string)
  - `template_vars` (dict)
  - `idempotency_key` (string, optional)
- `provider` (string)
- `account` (string)

## Idempotency (Correct + Safe)

- Egret requires `idempotency_key` on write ops for WAL idempotency.
- Life does not invent its own canonicalization rules; it either passes explicit keys or relies on lorchestra’s egret plan builder defaults.
- **Footgun**: lorchestra’s derived key format may change; callers who need stable semantics across template/body changes should pass explicit `idempotency_key` values.

## Dry Run (Correct Semantics)

Life `--dry-run` is a Life-runner preview mode:
- compiles JobDef → JobInstance
- prints/returns what would run
- does NOT execute lorchestra steps
- therefore does NOT render templates and does NOT submit to egret

## Verification

- `python3 -m life jobs | grep '^email\.'`
- `python3 -m life run email.send to=a@x.com subject=Hi body=Hello provider=gmail account=personal-gmail --dry-run`
- `python3 -m life run email.send_templated to=a@x.com template_path=/abs/path/template.md template_vars='{"name":"A"}' provider=gmail account=personal-gmail --dry-run`
- `python3 -m life run email.batch_send template_path=/abs/path/template.md items='[{"to":"a@x.com","template_vars":{"name":"A"}}]' provider=gmail account=personal-gmail --dry-run`