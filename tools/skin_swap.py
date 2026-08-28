# -*- coding: utf-8 -*-
"""Playable H5 skin-swap agent pipeline.

The pipeline turns a self-contained playable HTML into an editable asset bundle,
lets a user declare which assets to replace, then embeds the selected assets back
into a new single-file HTML.

Examples:
  python tools/skin_swap.py extract demo.html --out-dir skin/demo
  python tools/skin_swap.py plan skin/demo --request examples/skin_request.json --out skin/demo/plan.json
  python tools/skin_swap.py embed skin/demo demo.html --plan skin/demo/plan.json --out outputs/demo_skinned.html
  python tools/skin_swap.py run demo.html --out-dir skin/demo --request examples/skin_request.json --out outputs/demo_skinned.html
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


RE_DATA_URI = re.compile(
    r"""(data:([a-z0-9.+-]+/[a-z0-9.+-]+)(?:;[a-z0-9=.+-]+)*;base64,([A-Za-z0-9+/]+={0,2}))""",
    re.IGNORECASE,
)

MIME_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/svg+xml": "svg",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/ogg": "ogg",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "font/woff": "woff",
    "font/woff2": "woff2",
    "application/font-woff": "woff",
    "application/octet-stream": "bin",
}

ROLE_KEYWORDS = [
    ("logo", ["logo", "brand", "icon"]),
    ("cta_button", ["cta", "store", "download", "play_now", "btn_play", "button"]),
    ("background", ["bg", "backdrop", "scene", "sky", "map", "stage", "background"]),
    ("character", ["hero", "role", "player", "girl", "boy", "avatar", "char", "zombie"]),
    ("prop", ["prop", "item", "coin", "gem", "weapon", "screw", "pin", "rope", "balloon"]),
    ("endcard", ["end", "win", "fail", "settle", "result", "banner"]),
    ("sfx", ["sound", "audio", "music", "sfx", "mp3", "wav"]),
    ("video", ["video", "mp4", "webm", "movie"]),
    ("font", ["font", "woff"]),
]

CATEGORY_BY_ROLE = {
    "logo": "brand",
    "cta_button": "ui",
    "background": "scene",
    "character": "character",
    "prop": "gameplay",
    "endcard": "ui",
    "sfx": "audio",
    "video": "video",
    "font": "font",
}


def _sha256_bytes(data: bytes, length: Optional[int] = None) -> str:
    digest = hashlib.sha256(data).hexdigest()
    return digest if length is None else digest[:length]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _mime_to_ext(mime: str) -> str:
    guessed = mimetypes.guess_extension(mime)
    if guessed:
        return guessed.lstrip(".").replace("jpeg", "jpg")
    return MIME_EXT.get(mime.lower(), "bin")


def _safe_name(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("._")
    return clean or "asset"


def _context_tokens(context: str) -> List[str]:
    quoted = re.findall(r"['\"]([a-zA-Z0-9_.\-/]{2,80})['\"]", context)
    identifiers = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,60}", context)
    return [x.lower() for x in quoted + identifiers]


def _dimensions(payload: bytes, mime: str) -> Dict[str, int]:
    if mime == "image/png" and payload.startswith(b"\x89PNG\r\n\x1a\n") and len(payload) >= 24:
        return {"width": int.from_bytes(payload[16:20], "big"), "height": int.from_bytes(payload[20:24], "big")}
    if mime == "image/gif" and payload[:6] in (b"GIF87a", b"GIF89a") and len(payload) >= 10:
        return {"width": int.from_bytes(payload[6:8], "little"), "height": int.from_bytes(payload[8:10], "little")}
    if mime in {"image/jpeg", "image/jpg"}:
        idx = 2
        while idx + 9 < len(payload):
            if payload[idx] != 0xFF:
                idx += 1
                continue
            marker = payload[idx + 1]
            idx += 2
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                return {"height": int.from_bytes(payload[idx + 3:idx + 5], "big"), "width": int.from_bytes(payload[idx + 5:idx + 7], "big")}
            if marker in {0xD8, 0xD9}:
                continue
            if idx + 2 > len(payload):
                break
            idx += int.from_bytes(payload[idx:idx + 2], "big")
    if mime == "image/webp" and payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        chunk = payload[12:16]
        if chunk == b"VP8X" and len(payload) >= 30:
            width = 1 + int.from_bytes(payload[24:27], "little")
            height = 1 + int.from_bytes(payload[27:30], "little")
            return {"width": width, "height": height}
    return {}


@dataclass
class AssetRecord:
    asset_id: str
    sha256: str
    mime: str
    file: str
    byte_size: int
    original_uri: str
    occurrences: List[Tuple[int, int]]
    context: str = ""
    category: str = "unknown"
    role: str = "unknown"
    confidence: float = 0.0
    dimensions: Dict[str, int] = field(default_factory=dict)
    hints: List[str] = field(default_factory=list)

    def to_manifest(self) -> Dict[str, Any]:
        return {
            "id": self.asset_id,
            "sha256": self.sha256,
            "file": self.file,
            "mime": self.mime,
            "bytes": self.byte_size,
            "occurrences": [list(x) for x in self.occurrences],
            "category": self.category,
            "role": self.role,
            "confidence": self.confidence,
            "dimensions": self.dimensions,
            "hints": self.hints,
            "original_uri": self.original_uri,
        }

    @classmethod
    def from_manifest(cls, row: Dict[str, Any]) -> "AssetRecord":
        return cls(
            asset_id=row["id"],
            sha256=row["sha256"],
            mime=row["mime"],
            file=row["file"],
            byte_size=int(row["bytes"]),
            original_uri=row["original_uri"],
            occurrences=[(int(a), int(b)) for a, b in row["occurrences"]],
            category=row.get("category", "unknown"),
            role=row.get("role", "unknown"),
            confidence=float(row.get("confidence", 0.0)),
            dimensions=row.get("dimensions", {}),
            hints=row.get("hints", []),
        )


class ExtractAgent:
    """Extracts unique base64 assets and keeps source positions for lossless re-embedding."""

    def run(self, html_path: Path, out_dir: Path) -> Dict[str, Any]:
        html = _read_text(html_path)
        out_dir.mkdir(parents=True, exist_ok=True)

        by_sha: Dict[str, AssetRecord] = {}
        payloads: Dict[str, bytes] = {}
        for match in RE_DATA_URI.finditer(html):
            original_uri, mime, b64 = match.group(1), match.group(2).lower(), match.group(3)
            try:
                payload = base64.b64decode(b64, validate=True)
            except ValueError:
                continue
            sha = _sha256_bytes(payload)
            start, end = match.start(1), match.end(1)
            if sha in by_sha:
                by_sha[sha].occurrences.append((start, end))
                continue
            asset_index = len(by_sha) + 1
            ext = MIME_EXT.get(mime, _mime_to_ext(mime))
            asset_id = f"asset_{asset_index:03d}"
            context_start = max(0, start - 260)
            context_end = min(len(html), end + 260)
            by_sha[sha] = AssetRecord(
                asset_id=asset_id,
                sha256=sha,
                mime=mime,
                file=f"{asset_id}.{ext}",
                byte_size=len(payload),
                original_uri=original_uri,
                occurrences=[(start, end)],
                context=html[context_start:context_end],
                dimensions=_dimensions(payload, mime),
            )
            payloads[sha] = payload

        if not by_sha:
            raise SystemExit(f"No embedded base64 assets found in {html_path}")

        records = ClassificationAgent().run(list(by_sha.values()))

        for record in records:
            target = out_dir / record.file
            target.write_bytes(payloads[record.sha256])

        manifest = {
            "version": 2,
            "pipeline": "skin-swap-agent",
            "source": str(html_path.resolve()),
            "source_sha256": _sha256_text(html),
            "total_assets": len(records),
            "total_occurrences": sum(len(x.occurrences) for x in records),
            "assets": [x.to_manifest() for x in records],
            "categories": _category_summary(records),
            "agent_trace": [
                {"agent": "ExtractAgent", "status": "passed", "unique_assets": len(records)},
                {"agent": "ClassificationAgent", "status": "passed", "categories": _category_summary(records)},
            ],
        }
        _write_json(out_dir / "manifest.json", manifest)
        _write_json(out_dir / "asset_catalog.json", _catalog(records))
        return manifest


class ClassificationAgent:
    """Classifies extracted assets from MIME type, size, dimensions, and local code context."""

    def run(self, records: Sequence[AssetRecord]) -> List[AssetRecord]:
        for record in records:
            tokens = _context_tokens(record.context)
            role, hits = self._role(record, tokens)
            record.role = role
            record.category = CATEGORY_BY_ROLE.get(role, self._category_from_mime(record.mime))
            record.hints = hits[:8]
            record.confidence = self._confidence(record, hits)
        return list(records)

    def _role(self, record: AssetRecord, tokens: Sequence[str]) -> Tuple[str, List[str]]:
        if record.mime.startswith("audio/"):
            return "sfx", ["mime:audio"]
        if record.mime.startswith("video/"):
            return "video", ["mime:video"]
        if "font" in record.mime or record.mime.endswith("woff") or record.mime.endswith("woff2"):
            return "font", ["mime:font"]

        context = record.context.lower()
        if "background-image" in context or ".scene" in context:
            return "background", ["background-image"]

        joined = " ".join(tokens)
        scored: List[Tuple[int, str, List[str]]] = []
        for role, keywords in ROLE_KEYWORDS:
            hits = [kw for kw in keywords if kw in joined]
            if hits:
                scored.append((len(hits), role, hits))
        if scored:
            scored.sort(key=lambda row: row[0], reverse=True)
            return scored[0][1], scored[0][2]

        dims = record.dimensions
        if dims:
            width, height = dims.get("width", 0), dims.get("height", 0)
            if width >= 480 or height >= 480:
                return "background", ["large-image"]
            if width <= 180 and height <= 180:
                return "prop", ["small-image"]
        return "prop" if record.mime.startswith("image/") else "unknown", []

    def _category_from_mime(self, mime: str) -> str:
        if mime.startswith("image/"):
            return "gameplay"
        if mime.startswith("audio/"):
            return "audio"
        if mime.startswith("video/"):
            return "video"
        return "unknown"

    def _confidence(self, record: AssetRecord, hits: Sequence[str]) -> float:
        if hits and hits[0].startswith("mime:"):
            return 0.95
        if hits:
            return min(0.9, 0.55 + len(hits) * 0.12)
        if record.dimensions:
            return 0.45
        return 0.25


class ReplacementPlannerAgent:
    """Turns a user replacement request into a deterministic embedding plan."""

    def run(self, manifest: Dict[str, Any], request: Dict[str, Any], skin_dir: Path) -> Dict[str, Any]:
        records = [AssetRecord.from_manifest(row) for row in manifest["assets"]]
        requested = request.get("replace", [])
        if not isinstance(requested, list):
            raise SystemExit("request JSON must contain a list field named 'replace'")

        replacements: List[Dict[str, Any]] = []
        warnings: List[str] = []
        used_ids: set[str] = set()
        for idx, item in enumerate(requested, start=1):
            match = item.get("match", {})
            source = item.get("with") or item.get("file")
            if not source:
                warnings.append(f"replace[{idx}] ignored: missing 'with' file")
                continue
            source_path = (skin_dir / source).resolve() if not Path(source).is_absolute() else Path(source)
            if not source_path.exists():
                warnings.append(f"replace[{idx}] ignored: replacement file not found: {source}")
                continue
            matched = [record for record in records if _matches(record, match)]
            if item.get("limit"):
                matched = matched[: int(item["limit"])]
            if not matched:
                warnings.append(f"replace[{idx}] matched no assets: {match}")
                continue
            for record in matched:
                if record.asset_id in used_ids and not item.get("allow_duplicate"):
                    continue
                replacements.append(
                    {
                        "id": record.asset_id,
                        "old_file": record.file,
                        "new_file": str(source_path),
                        "mime": item.get("mime") or record.mime,
                        "reason": item.get("reason", "user_request"),
                        "occurrences": len(record.occurrences),
                    }
                )
                used_ids.add(record.asset_id)

        if request.get("replace_edited_files", True):
            replacements.extend(_edited_file_replacements(records, skin_dir, used_ids))

        return {
            "version": 1,
            "source": manifest.get("source"),
            "source_sha256": manifest.get("source_sha256"),
            "replace_count": len(replacements),
            "replacements": replacements,
            "warnings": warnings,
            "agent_trace": manifest.get("agent_trace", [])
            + [{"agent": "ReplacementPlannerAgent", "status": "passed", "replace_count": len(replacements)}],
        }


class EmbeddingAgent:
    """Embeds planned replacement files back into the original HTML."""

    def run(self, manifest: Dict[str, Any], plan: Dict[str, Any], src_html: Path, out_html: Path) -> Dict[str, Any]:
        html = _read_text(src_html)
        expected_sha = manifest.get("source_sha256")
        if expected_sha and _sha256_text(html) != expected_sha:
            raise SystemExit("Source HTML changed since extraction; run extract again to avoid offset drift.")

        rows = {row["id"]: AssetRecord.from_manifest(row) for row in manifest["assets"]}
        replacements: List[Tuple[int, int, str, str]] = []
        embedded: List[Dict[str, Any]] = []
        for item in plan.get("replacements", []):
            record = rows.get(item["id"])
            if not record:
                continue
            replacement_path = Path(item["new_file"])
            payload = replacement_path.read_bytes()
            mime = item.get("mime") or record.mime
            new_uri = "data:%s;base64,%s" % (mime, base64.b64encode(payload).decode("ascii"))
            for start, end in record.occurrences:
                replacements.append((start, end, new_uri, record.asset_id))
            embedded.append(
                {
                    "id": record.asset_id,
                    "old_file": record.file,
                    "new_file": str(replacement_path),
                    "bytes": len(payload),
                    "occurrences": len(record.occurrences),
                }
            )

        replacements.sort(key=lambda row: row[0], reverse=True)
        skipped: List[str] = []
        for start, end, new_uri, asset_id in replacements:
            record = rows[asset_id]
            if html[start:end] != record.original_uri:
                skipped.append(asset_id)
                continue
            html = html[:start] + new_uri + html[end:]

        out_html.parent.mkdir(parents=True, exist_ok=True)
        out_html.write_text(html, encoding="utf-8")

        audit_report = _audit_html(out_html)
        report = {
            "output": str(out_html),
            "embedded": embedded,
            "skipped": sorted(set(skipped)),
            "size_kb": round(out_html.stat().st_size / 1024, 2),
            "audit": audit_report,
            "agent_trace": plan.get("agent_trace", [])
            + [{"agent": "EmbeddingAgent", "status": "passed", "embedded_assets": len(embedded)}],
        }
        _write_json(out_html.with_suffix(".skin_report.json"), report)
        return report


def _matches(record: AssetRecord, match: Dict[str, Any]) -> bool:
    if not match:
        return False
    for key, expected in match.items():
        if key in {"id", "asset_id"} and record.asset_id != expected:
            return False
        if key == "sha256" and not record.sha256.startswith(str(expected)):
            return False
        if key == "file" and record.file != expected:
            return False
        if key == "category" and record.category != expected:
            return False
        if key == "role" and record.role != expected:
            return False
        if key == "mime" and record.mime != expected:
            return False
        if key == "min_bytes" and record.byte_size < int(expected):
            return False
        if key == "max_bytes" and record.byte_size > int(expected):
            return False
    return True


def _edited_file_replacements(records: Sequence[AssetRecord], skin_dir: Path, used_ids: set[str]) -> List[Dict[str, Any]]:
    replacements: List[Dict[str, Any]] = []
    for record in records:
        if record.asset_id in used_ids:
            continue
        file_path = skin_dir / record.file
        if not file_path.exists():
            continue
        payload = file_path.read_bytes()
        if _sha256_bytes(payload) == record.sha256:
            continue
        replacements.append(
            {
                "id": record.asset_id,
                "old_file": record.file,
                "new_file": str(file_path.resolve()),
                "mime": record.mime,
                "reason": "edited_extracted_file",
                "occurrences": len(record.occurrences),
            }
        )
        used_ids.add(record.asset_id)
    return replacements


def _category_summary(records: Iterable[AssetRecord]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for record in records:
        summary[record.category] = summary.get(record.category, 0) + 1
    return dict(sorted(summary.items()))


def _catalog(records: Sequence[AssetRecord]) -> Dict[str, Any]:
    return {
        "assets": [
            {
                "id": record.asset_id,
                "file": record.file,
                "category": record.category,
                "role": record.role,
                "mime": record.mime,
                "bytes": record.byte_size,
                "dimensions": record.dimensions,
                "occurrences": len(record.occurrences),
                "confidence": record.confidence,
                "hints": record.hints,
            }
            for record in records
        ]
    }


def _audit_html(path: Path) -> Dict[str, Any]:
    try:
        from tools.audit_html import audit

        return audit(str(path))
    except Exception as exc:  # pragma: no cover - defensive CLI fallback
        return {"passed": False, "blockers": ["audit_error"], "error": str(exc)}


def _load_manifest(skin_dir: Path) -> Dict[str, Any]:
    manifest_path = skin_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"manifest.json not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _load_request(path: Optional[Path]) -> Dict[str, Any]:
    if not path:
        return {"replace": [], "replace_edited_files": True}
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_plan_files(plan: Dict[str, Any], skin_dir: Path) -> None:
    replacement_dir = skin_dir / "replacements"
    replacement_dir.mkdir(exist_ok=True)
    for item in plan.get("replacements", []):
        source = Path(item["new_file"])
        if not source.exists() or source.parent == replacement_dir:
            continue
        target = replacement_dir / _safe_name(source.name)
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
            item["new_file"] = str(target.resolve())


def cmd_extract(args: argparse.Namespace) -> None:
    manifest = ExtractAgent().run(Path(args.src), Path(args.out_dir))
    print(f"[OK] ExtractAgent: {manifest['total_assets']} assets, {manifest['total_occurrences']} occurrences")
    print(f"[OK] ClassificationAgent: {manifest['categories']}")
    print(f"[OK] manifest: {Path(args.out_dir) / 'manifest.json'}")
    print(f"[OK] catalog:  {Path(args.out_dir) / 'asset_catalog.json'}")


def cmd_plan(args: argparse.Namespace) -> None:
    skin_dir = Path(args.skin_dir)
    manifest = _load_manifest(skin_dir)
    request = _load_request(Path(args.request) if args.request else None)
    plan = ReplacementPlannerAgent().run(manifest, request, skin_dir)
    if args.copy_files:
        _copy_plan_files(plan, skin_dir)
    out = Path(args.out or skin_dir / "replacement_plan.json")
    _write_json(out, plan)
    print(f"[OK] ReplacementPlannerAgent: {plan['replace_count']} replacements")
    if plan["warnings"]:
        print("[WARN] " + " | ".join(plan["warnings"]))
    print(f"[OK] plan: {out}")


def cmd_embed(args: argparse.Namespace) -> None:
    skin_dir = Path(args.skin_dir)
    manifest = _load_manifest(skin_dir)
    plan_path = Path(args.plan or skin_dir / "replacement_plan.json")
    if not plan_path.exists():
        raise SystemExit(f"replacement plan not found: {plan_path}")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    report = EmbeddingAgent().run(manifest, plan, Path(args.src), Path(args.out))
    print(f"[OK] EmbeddingAgent: {len(report['embedded'])} assets embedded")
    print(f"[OK] output: {report['output']} ({report['size_kb']} KB)")
    print(f"[OK] audit passed: {report['audit'].get('passed')}")


def cmd_run(args: argparse.Namespace) -> None:
    skin_dir = Path(args.out_dir)
    manifest = ExtractAgent().run(Path(args.src), skin_dir)
    request = _load_request(Path(args.request) if args.request else None)
    plan = ReplacementPlannerAgent().run(manifest, request, skin_dir)
    plan_path = skin_dir / "replacement_plan.json"
    _write_json(plan_path, plan)
    report = EmbeddingAgent().run(manifest, plan, Path(args.src), Path(args.out))
    print(f"[OK] SkinSwapPipeline: {manifest['total_assets']} classified, {plan['replace_count']} planned")
    print(f"[OK] output: {report['output']} ({report['size_kb']} KB)")
    print(f"[OK] audit passed: {report['audit'].get('passed')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Playable H5 skin-swap agent pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)

    extract = sub.add_parser("extract", help="extract and classify embedded assets")
    extract.add_argument("src", help="source single-file HTML")
    extract.add_argument("--out-dir", "-o", required=True, help="asset bundle output directory")
    extract.set_defaults(func=cmd_extract)

    plan = sub.add_parser("plan", help="turn a user request into a replacement plan")
    plan.add_argument("skin_dir", help="directory containing manifest.json")
    plan.add_argument("--request", "-r", default="", help="JSON request describing replacements")
    plan.add_argument("--out", "-o", default="", help="replacement plan path")
    plan.add_argument("--copy-files", action="store_true", help="copy replacement files into skin_dir/replacements")
    plan.set_defaults(func=cmd_plan)

    embed = sub.add_parser("embed", help="embed planned replacements back into HTML")
    embed.add_argument("skin_dir", help="directory containing manifest.json")
    embed.add_argument("src", help="original source HTML used for extraction")
    embed.add_argument("--plan", "-p", default="", help="replacement plan JSON")
    embed.add_argument("--out", "-o", required=True, help="output HTML")
    embed.set_defaults(func=cmd_embed)

    run = sub.add_parser("run", help="extract, classify, plan, and embed in one command")
    run.add_argument("src", help="source single-file HTML")
    run.add_argument("--out-dir", "-d", required=True, help="asset bundle output directory")
    run.add_argument("--request", "-r", default="", help="JSON request describing replacements")
    run.add_argument("--out", "-o", required=True, help="output HTML")
    run.set_defaults(func=cmd_run)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
