# Asset Sources

This showcase includes a small public demo asset pack for generated playables.

## Included Public Assets

Source:

- Kenney Puzzle Pack 2: https://kenney.nl/assets/puzzle-pack-2
- Kenney UI Pack: https://kenney.nl/assets/ui-pack

License:

- Creative Commons CC0
- The included license files are kept under `public_assets/kenney/`.
- Attribution is not required by the license, but the README credits Kenney
  because it is useful and transparent for a portfolio project.

## How The Generator Uses Them

`src/demo_asset_pack.py` loads a curated subset of PNG files and converts them to
data URIs at render time. The generated playable remains a single-file H5, but
the repo keeps the original public PNG files visible for review and replacement.

Default keys:

- `merge_item_lv0` to `merge_item_lv4`
- `demo_coin`
- `ui_button_primary`
- `ui_button_secondary`
- `ui_checkmark`

Templates should call `App.assets.get(key)` first and keep a lightweight canvas
fallback only for local development.

## Extending The Pack

1. Put public or owned PNG/WebP files under `public_assets/<source>/`.
2. Add a license or attribution note beside the files.
3. Register keys in `src/demo_asset_pack.py`.
4. Use those keys in a template through `App.assets.get(...)`.
5. Run `python tests/self_test.py` and regenerate screenshots.
