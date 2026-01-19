# Step: step-001

## Objective
Add request schema for pm.work_item.move:
- `schemas/org1.workman/pm.work_item.move/jsonschema/1-0-0/schema.json`
Schema:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "work_item_id": { "type": "string" },
    "project_id": { "type": "string" }
  },
  "required": ["work_item_id", "project_id"],
  "additionalProperties": false
}
```

## Scope Constraints

### Allowed Paths
- `/home/developer/.local/schema-transform-registry/schemas/org1.workman/**`

### Forbidden Paths
- `.git/**`
- `*.lock`
- `.env*`
- `secrets/**`

## Verification Commands

Your changes will be verified by running:


## Output Requirements

Your final output MUST be valid JSON matching the provided schema.
`patch_diff` MUST be a unified diff against the current baseline.
