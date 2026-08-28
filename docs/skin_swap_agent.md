# Skin Swap Agent

This module is a small agent pipeline for playable-ad reskinning. It extracts
embedded assets from a single-file HTML playable, classifies the assets, turns a
user request into a replacement plan, and embeds the selected files back into a
new single-file HTML.

## Pipeline

```text
source.html
   |
   v
ExtractAgent
   - scans data:*/*;base64 URIs
   - deduplicates by SHA-256 payload
   - stores exact source offsets for safe re-embedding
   |
   v
ClassificationAgent
   - classifies image, audio, video, font, UI, scene, gameplay
   - uses MIME type, dimensions, and local code context
   |
   v
ReplacementPlannerAgent
   - reads the user's JSON request
   - resolves targets by id, role, category, MIME, size, or hash prefix
   - can also detect edited files in the extracted bundle
   |
   v
EmbeddingAgent
   - validates the source HTML has not drifted
   - replaces occurrences from back to front
   - writes a new single-file HTML and a skin report
   - runs the static delivery audit
```

## Commands

```powershell
python tools/skin_swap.py extract path\to\playable.html --out-dir skin\demo
python tools/skin_swap.py plan skin\demo --request examples\skin_request.json
python tools/skin_swap.py embed skin\demo path\to\playable.html --out outputs\demo_skinned.html
```

For a quick end-to-end demo:

```powershell
python tools/skin_swap.py run path\to\playable.html --out-dir skin\demo --request examples\skin_request.json --out outputs\demo_skinned.html
```

## User Request Format

```json
{
  "replace": [
    {
      "match": { "role": "background" },
      "with": "replacements/new_scene.webp",
      "limit": 1,
      "reason": "make the first scene match the new theme"
    },
    {
      "match": { "category": "ui" },
      "with": "replacements/new_cta.png",
      "limit": 1,
      "reason": "replace the main CTA visual"
    }
  ],
  "replace_edited_files": true
}
```

Targets can be matched with `id`, `file`, `sha256`, `category`, `role`, `mime`,
`min_bytes`, and `max_bytes`.

If `replace_edited_files` is true, the planner also checks whether files in the
extracted bundle were manually edited. Any file whose SHA-256 changed is added
to the replacement plan automatically.

## Why This Matters

Playable reskinning is risky because embedded files often appear multiple times:
inside CSS, JavaScript constants, preloads, and asset maps. This pipeline keeps
the original source offsets and verifies the original HTML hash before embedding
new assets, so replacements do not silently drift into the wrong location.

The output remains a single self-contained HTML and is audited with
`tools/audit_html.py` after embedding.
