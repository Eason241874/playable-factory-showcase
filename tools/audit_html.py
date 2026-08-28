# -*- coding: utf-8 -*-
"""独立的单文件 H5 交付审计器。

它不执行页面脚本，只检查结构、跳转兜底、外链和包体，适合放进 CI。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List


def audit(path: str, *, max_mb: float = 5.0) -> Dict[str, object]:
    file_path = Path(path)
    html = file_path.read_text(encoding="utf-8", errors="replace")
    size_mb = file_path.stat().st_size / (1024 * 1024)
    external = sorted(set(re.findall(r"(?:src|href)\s*=\s*['\"]https?://[^'\"]+", html, re.I)))

    checks = [
        ("doctype", html.lstrip().lower().startswith("<!doctype html>"), "BLOCKER"),
        ("single_file_shell", all(x in html for x in ("<style>", "<script>", "</html>")), "BLOCKER"),
        ("start_flow", 'id="btn-start"' in html and "App.emit('start')" in html, "BLOCKER"),
        ("settle_flow", 'id="end-layer"' in html and "App.end(" in html, "BLOCKER"),
        ("cta_fallback", all(x in html for x in ("ExitApi", "mraid", "window.__openStore")), "BLOCKER"),
        ("no_template_placeholders", "{{" not in html, "BLOCKER"),
        ("no_external_requests", not external, "BLOCKER"),
        ("size_limit", size_mb <= max_mb, "INFO"),
    ]
    result: List[Dict[str, object]] = []
    blockers: List[str] = []
    for name, ok, severity in checks:
        row = {"name": name, "ok": bool(ok), "severity": severity}
        if name == "size_limit":
            row["detail"] = f"{size_mb:.2f} MB <= {max_mb:.2f} MB"
        elif name == "no_external_requests" and external:
            row["detail"] = external[:5]
        result.append(row)
        if not ok and severity == "BLOCKER":
            blockers.append(name)
    return {
        "path": str(file_path),
        "size_mb": round(size_mb, 3),
        "passed": not blockers,
        "blockers": blockers,
        "checks": result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="审计单文件试玩广告 H5")
    parser.add_argument("html")
    parser.add_argument("--max-mb", type=float, default=5.0)
    args = parser.parse_args()
    report = audit(args.html, max_mb=args.max_mb)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
