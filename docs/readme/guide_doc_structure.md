# Document Structure Guide

`.doc_structure.yaml` is a project-level configuration file that declares where documents live and what types they are. forge uses it to resolve document paths.

## Feature

forge can optionally manage documents per **Feature** — a grouped unit of related specifications for development. Features are not required; forge works without them.

| Development Pattern     | How Features are used                                                        |
| ----------------------- | ---------------------------------------------------------------------------- |
| Incremental development | Separate new capabilities from the existing main spec as individual Features |
| Agile development       | Develop and deliver per Feature in each iteration                            |
| Small projects          | Treat the entire project as a single Feature                                 |

When using Features, each one shares a common directory structure:

```
specs/
  {feature}/
    requirements/   # Requirements documents
    design/         # Design documents
    plan/           # Implementation plan (temporary; excluded from the search index)
    adr/            # ADRs (Architecture Decision Records)
```

## .doc_structure.yaml

### Purpose

A file that declares where documents live and what types they are. The following tools share it:

- **forge** — Resolve review targets, detect Feature directories, locate document output paths, and resolve the search-index target paths (passed to the selected document-search backend, doc-advisor or doc-db)

Place it at the project root (same level as `.git/`).

### Schema Overview

Organized into two categories: `rules` and `specs`.

```yaml
# .doc_structure.yaml
# doc_structure_version: 3.0

rules:
  root_dirs: # Directories to scan (glob supported)
    - docs/rules/
  doc_types_map: # Directory → doc_type mapping
    docs/rules/: rule
  patterns:
    target_glob: "**/*.md"
    exclude: [] # Directory names to exclude

specs:
  root_dirs:
    - "docs/specs/*/adr/"
    - "docs/specs/*/design/"
    - "docs/specs/*/plan/"
    - "docs/specs/*/requirement/"
  doc_types_map:
    "docs/specs/*/adr/": adr
    "docs/specs/*/design/": design
    "docs/specs/*/plan/": plan
    "docs/specs/*/requirement/": requirement
  patterns:
    target_glob: "**/*.md"
    exclude: [
      plan,
    ] # Plans are temporary documents, so keep them out of the search index
```

| Field                  | Description                                                                                                        |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `root_dirs`            | Document directories. Supports `*` (one level) / `**` (any depth) glob patterns                                    |
| `doc_types_map`        | Path → doc_type mapping. Recommended doc_types: `rule`, `requirement`, `design`, `plan`, `adr`, `api`, `reference` |
| `patterns.target_glob` | File search pattern (default: `**/*.md`)                                                                           |
| `patterns.exclude`     | Directory names to exclude (matches at any depth in the path)                                                      |

forge resolves where requirements, designs, plans, and ADRs go from `doc_types_map`, so `requirement` / `design` / `plan` / `adr` must each be declared exactly once, even before their directories exist. `exclude` only limits what the search index collects; it does not affect path resolution, so `plan` can be declared and excluded at the same time.

### Configuration Examples

#### Simple (No Features)

```yaml
specs:
  root_dirs:
    - docs/specs/adr/
    - docs/specs/design/
    - docs/specs/plan/
    - docs/specs/requirement/
  doc_types_map:
    docs/specs/adr/: adr
    docs/specs/design/: design
    docs/specs/plan/: plan
    docs/specs/requirement/: requirement
  patterns:
    target_glob: "**/*.md"
    exclude: [plan]
```

#### Feature-Based

```yaml
specs:
  root_dirs:
    - "docs/specs/*/adr/"
    - "docs/specs/*/design/"
    - "docs/specs/*/plan/"
    - "docs/specs/*/requirement/"
  doc_types_map:
    "docs/specs/*/adr/": adr
    "docs/specs/*/design/": design
    "docs/specs/*/plan/": plan
    "docs/specs/*/requirement/": requirement
  patterns:
    target_glob: "**/*.md"
    exclude: [plan]
```

No `.doc_structure.yaml` changes needed when adding a Feature. Just create the `docs/specs/payment/design/` directory and it is detected automatically.

#### Nested Features (Sub-Features)

```yaml
specs:
  root_dirs:
    - "docs/specs/**/adr/"
    - "docs/specs/**/design/"
    - "docs/specs/**/plan/"
    - "docs/specs/**/requirements/"
  doc_types_map:
    "docs/specs/**/adr/": adr
    "docs/specs/**/design/": design
    "docs/specs/**/plan/": plan
    "docs/specs/**/requirements/": requirement
  patterns:
    target_glob: "**/*.md"
    exclude: [plan]
```

Both `docs/specs/forge/design/` and `docs/specs/forge/review-PR/design/` are detected automatically.

## /forge:setup-doc-structure

```
/forge:setup-doc-structure
```

No arguments.

### What it does

- Scans the project and interactively generates or updates `.doc_structure.yaml`
- Auto-detects existing Feature directories and configures them as glob patterns
- Proposes a recommended structure (specs / rules / reference) and creates missing directories with `.gitkeep`
- Always declares `requirement` / `design` / `plan` / `adr`, which forge uses to locate documents, even when their directories do not exist yet. Plans may be discarded after implementation, so `plan` is excluded from the search index with `patterns.exclude`
- Before writing, shows the full `.doc_structure.yaml` and the reason for each entry's classification, and asks for approval. When you change a classification, it lists the values you can choose from
- If `.doc_structure.yaml` already exists, it switches to review mode and points out entries that break the declaration and exclusion rules above, with a proposed fix

### When to run

- First time using forge in a project
- After major changes to the directory structure
- After manually adding a Feature
- When you want to review an existing `.doc_structure.yaml`

## Schema Reference

For the full format specification, see [doc_structure_format.md](../../plugins/forge/docs/doc_structure_format.md).
