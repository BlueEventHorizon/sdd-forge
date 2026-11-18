# Installing and Switching forge Backends

forge has two independent, swappable backend axes.

| Axis                    | Candidates                                | Used by                                                                            |
| ----------------------- | ----------------------------------------- | ---------------------------------------------------------------------------------- |
| Document-search backend | doc-link (default first) / doc-db         | `/forge:query-db-rules` / `query-db-specs` / `update-db-rules` / `update-db-specs` |
| Review executor         | agent-review (the only current candidate) | `/forge:review`                                                                    |

Both are switched via the project settings file `.claude/.forge.yaml` (relative to the project root). The file is optional; without it, the defaults apply.

## Installing a Document-Search Backend

The document-search backends are not part of forge; install the one you use separately. Neither is gated on a version: availability is judged by whether the required features can be used.

| Backend  | What it is                                                                                                                                                                                                                                                                      | How to install                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| doc-link | An external plugin ([BlueEventHorizon/doc-link](https://github.com/BlueEventHorizon/doc-link)). Gives each document a stable ID (DLID), builds an index from them, and searches by meaning. Requires [uv](https://docs.astral.sh/uv/) (uv provides Python and the dependencies) | The commands below                                                                                        |
| doc-db   | A locally running document-search server                                                                                                                                                                                                                                        | Install the `doc-db` command on your PATH. forge starts it automatically when the ordered list selects it |

```
/plugin marketplace add BlueEventHorizon/doc-link
/plugin install doc-link@doc-link
```

### What Happens to Your Documents with doc-link

- **Updating the index (`/forge:update-db-rules` / `update-db-specs`) writes DLIDs into the target documents.** They go into `doc_link_id` in the frontmatter and at the end of every heading line, because a document without DLIDs is left out of the index. No confirmation is shown before writing. The first update writes to every target document
- The index and its managed state live in `.doc-link/` at the project root. **Track `.doc-link/` and the documents that carry DLIDs in git, and commit them together with the document changes**
- Searching (`/forge:query-db-rules` / `query-db-specs`) checks, before it searches, whether the index matches the documents on disk. When the index is out of date, it asks whether to rebuild first or to search with the existing index

## Settings File Syntax

```yaml
# .claude/.forge.yaml
doc_backend:
  prefer: doc-db # doc-db | doc-link

review:
  backend: agent-review # agent-review is the only current candidate
```

### `doc_backend.prefer` (document search)

- Puts the specified backend first in the ordered list (e.g. `doc-db` yields `["doc-db", "doc-link"]`). The default without this setting is doc-link first
- If the first backend is unavailable, forge notifies you of the reason and uses the other one
- The only accepted key is `prefer`. Unknown keys or values outside the two allowed ones raise an explicit error (forge never silently falls back to the default — this prevents a setting you believe is active from being quietly ignored)

### `review.backend` (review executor)

- Runs **only** the specified backend (treated as an explicit choice). If it is unavailable, forge does not pick an alternative; it fails without sending a request (fail closed)
- Without this setting, the candidates are probed in order and the first available one is used (**agent-review is the only current candidate**; the resolution machinery is unchanged even with a single candidate)
- The only accepted key is `backend`

## Forcing a Backend by Argument (overrides the setting)

| Skill                                        | Argument                     | Behavior                                            |
| -------------------------------------------- | ---------------------------- | --------------------------------------------------- |
| `/forge:update-db-rules` / `update-db-specs` | `--backend doc-db\|doc-link` | Uses only that backend; fails closed if unavailable |
| `/forge:review`                              | `--backend <name>`           | Same as above                                       |
| `/forge:query-db-rules` / `query-db-specs`   | (no such flag)               | Always decided by the ordered list                  |

Precedence: **argument > `.claude/.forge.yaml` > default order**.

## Notes

- `.claude/.forge.yaml` is parsed as a restricted YAML subset. Anchors/aliases (`&` / `*`), multi-line strings (`|` / `>`), and flow style (`[...]` / `{...}`) are not supported; if present, the whole file is treated as unparsable and raises an explicit error
- For the rationale behind the review-executor candidate order and each backend's prerequisites, see [guide_review.md](forge/guide_review.md)
