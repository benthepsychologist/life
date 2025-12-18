# Scripts Directory

**Scripts are temporary glue code.**

This directory contains quarantined bash scripts managed by `life script`. Scripts placed here are:

1. **Subject to TTL enforcement** - They will warn, require confirmation, and eventually block as they age
2. **Not first-class capabilities** - They don't appear in `life list` or job catalogs
3. **Expected to be promoted** - Each script must specify a `promotion_target` in its metadata

## When to Use Scripts

Scripts are appropriate for:
- One-time data migrations
- Temporary orchestration during development
- Quick validation workflows that will become proper jobs

Scripts are **not** appropriate for:
- Long-running production workflows
- Anything that should be documented or tested
- Code that will be reused

## Script Structure

Each script requires two files:
```
scripts/
├── my-script.sh           # The bash script
└── my-script.meta.yaml    # Required metadata
```

### Metadata Schema

```yaml
name: my-script              # Must match filename (lowercase, hyphens only)
description: "What this does" # Required - no mystery scripts
owner: "@github-handle"       # Who owns this script
created_at: 2025-12-17        # When it was created
ttl_days: 30                  # How long before warnings start
promotion_target: job/target  # Where this goes when promoted
calls:                        # Optional: what jobs this invokes
  - job/step-one
  - job/step-two
```

## TTL Enforcement

| Age | Behavior |
|-----|----------|
| < 1×TTL | Normal execution |
| 1×TTL – 2×TTL | Warning shown |
| 2×TTL – 3×TTL | Confirmation required (`--yes` bypasses) |
| > 3×TTL | **HARD BLOCK** (only `--force` bypasses) |

## CLI Usage

```bash
# List available scripts
life script list

# Show script info
life script info my-script

# Run a script
life script run my-script

# Run with arguments (use -- to separate)
life script run my-script -- --source prod --dry-run

# Bypass TTL confirmation (2x-3x TTL)
life script run my-script --yes

# Bypass TTL hard block (>3x TTL) - audited
life script run my-script --force
```

## Promotion

When a script is ready to become permanent:

1. Write a proper spec
2. Implement the job using `life run`
3. Delete the script files

There is no automatic promotion. Promotion means writing real code.
