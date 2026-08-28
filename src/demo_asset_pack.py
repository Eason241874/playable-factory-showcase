# -*- coding: utf-8 -*-
"""Public demo asset pack loader.

The committed demo pack uses a small subset of Kenney CC0 assets so generated
showcase playables have real game art by default while remaining lightweight.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Dict


ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = ROOT / "public_assets" / "kenney"

ASSET_FILES = {
    "merge_item_lv0": "puzzle/merge_lv0.png",
    "merge_item_lv1": "puzzle/merge_lv1.png",
    "merge_item_lv2": "puzzle/merge_lv2.png",
    "merge_item_lv3": "puzzle/merge_lv3.png",
    "merge_item_lv4": "puzzle/merge_lv4.png",
    "demo_coin": "puzzle/coin.png",
    "ui_button_primary": "ui/button_primary.png",
    "ui_button_secondary": "ui/button_secondary.png",
    "ui_checkmark": "ui/checkmark.png",
}


def load_demo_assets() -> Dict[str, str]:
    assets: Dict[str, str] = {}
    for key, relative in ASSET_FILES.items():
        path = PACK_ROOT / relative
        if not path.exists():
            continue
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        payload = base64.b64encode(path.read_bytes()).decode("ascii")
        assets[key] = f"data:{mime};base64,{payload}"
    return assets
