# -*- coding: utf-8 -*-
"""换皮工具：从任意投放 H5 提取内联素材 → 换图 → 灌回，关卡不动。

用法：
  python tools/skin_swap.py extract <H5路径> [--out-dir skin/项目名]
  python tools/skin_swap.py replace <skin目录> <原H5路径> [--out 新H5路径]

extract 阶段：
  扫描 H5 里全部 data:image/...;base64,... 和 data:video/...;base64,...
  → SHA256 去重 → 写素材文件到 skin 目录 → 生成 manifest.json（记录原始 data URI、
  在原文中的字节位置列表、MIME 类型）。

replace 阶段：
  读 manifest.json → 把新素材转 base64 / 构造新 data URI → 按字节位置精确替换
  → 输出新 H5 单文件。后续对新 H5 跑一遍 QA 检查（复用 agents.py 的检查逻辑）。

设计要点：
  - 按 base64 内容 SHA256 去重，不是按 data URI 字符串去重——同一张图可能在 CSS 和 JS
    常量里各出现一次，内容完全一样但周边引号/分号不同。
  - 替换按字节位置做 ordinal replace（Python 字符串切片拼接），不像正则遇到特殊字符翻车。
  - manifest 只记录唯一素材；替换时对同一 SHA256 的全部 occurrence 统一替换。
"""
import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import sys

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
# 抓 data URI 的正则：image/xxx 和 video/xxx 都要
_RE_DATA_URI = re.compile(
    r"""(data:(?:image|video)/[a-z0-9+-]+;base64,([A-Za-z0-9+/]+={0,2}))""",
    re.IGNORECASE,
)

# 从 data URI 的 MIME 里推断扩展名
_MIME_EXT = {
    "image/png": "png",  "image/jpeg": "jpg",  "image/jpg": "jpg",
    "image/webp": "webp","image/gif": "gif",   "image/svg+xml": "svg",
    "video/mp4": "mp4",  "video/webm": "webm",
}

# QA 检查项（复用 agents.py 的 _qa_check 逻辑，这里内联一份精简版）
_QA_CHECKS_REQUIRED = [
    ("非空", lambda h: len(h) > 500),
    ("单文件结构", lambda h: all(t in h for t in ("<!DOCTYPE html", "</html>", "<style>", "<script>"))),
    ("CTA 按钮与埋点", lambda h: "track('click_cta')" in h),
    ("渠道三轨跳转", lambda h: "ExitApi" in h and "mraid" in h and "__openStore" in h),
    ("胜利路径可达", lambda h: "App.end('success')" in h or 'App.end("success")' in h),
    ("JS 大括号配平", lambda h: h.count("{") == h.count("}")),
    ("包体 <= 1.8MB", lambda h: len(h.encode("utf-8")) / 1024 <= 1800),
]


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------
def cmd_extract(src: str, out_dir: str):
    if not os.path.exists(src):
        sys.exit("源 H5 不存在: %s" % src)
    with open(src, "r", encoding="utf-8") as f:
        text = f.read()

    # 扫描所有 data URI
    dedup: dict[str, dict] = {}   # sha256 -> { mime, b64, payload, positions }
    # 手动迭代 match：方便记录字节级别的 match span
    pos = 0
    while True:
        m = _RE_DATA_URI.search(text, pos)
        if not m:
            break
        full = m.group(1)          # "data:image/png;base64,iVBOR..."
        b64 = m.group(2)
        mime = re.match(r"data:(image|video/\w+)", full)  # 原样取 MIME
        mime = mime.group(0).replace("data:", "") if mime else "image/png"

        h = hashlib.sha256(b64.encode("ascii")).hexdigest()[:16]
        if h not in dedup:
            payload = base64.b64decode(b64)
            dedup[h] = {
                "mime": mime,
                "b64": b64,
                "original_uri": full,
                "payload": payload,
                "positions": [],
            }
        dedup[h]["positions"].append([m.start(), m.end()])
        pos = m.end()

    if not dedup:
        sys.exit("未找到任何 data URI 素材，这个 H5 可能没有内联资源。")

    os.makedirs(out_dir, exist_ok=True)

    manifest = {
        "source": os.path.abspath(src),
        "total_unique": len(dedup),
        "assets": {},
    }

    for idx, (sha, info) in enumerate(dedup.items(), start=1):
        ext = _MIME_EXT.get(info["mime"], "png")
        fname = "asset_%03d.%s" % (idx, ext)
        fpath = os.path.join(out_dir, fname)
        with open(fpath, "wb") as f:
            f.write(info["payload"])
        sz_kb = len(info["payload"]) / 1024
        print("[%02d/%d] %s  %6.1f KB  (%d 处引用)" % (
            idx, len(dedup), fname, sz_kb, len(info["positions"])))
        manifest["assets"][sha] = {
            "file": fname,
            "mime": info["mime"],
            "original_uri": info["original_uri"],
            "sha256": sha,
            "occurrences": info["positions"],
        }

    mpath = os.path.join(out_dir, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("\n[OK] 提取完成：%d 个唯一素材 -> %s" % (len(dedup), out_dir))
    print("  素材列表: %s" % mpath)
    print("  下一步：替换素材文件（保持同名），然后跑 replace 灌回。")


# ---------------------------------------------------------------------------
# replace
# ---------------------------------------------------------------------------
def cmd_replace(skin_dir: str, src_html: str, out_html: str):
    mpath = os.path.join(skin_dir, "manifest.json")
    if not os.path.exists(mpath):
        sys.exit("manifest.json 不存在：%s（先跑 extract）" % mpath)
    if not os.path.exists(src_html):
        sys.exit("原 H5 不存在: %s" % src_html)

    with open(mpath, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(src_html, "r", encoding="utf-8") as f:
        text = f.read()

    # 从后往前替换（按 occurrence 的 start 位置倒序），避免前面替换后偏移量变化
    replacements = []  # (start, end, new_sha, old_sha)
    for sha, info in manifest["assets"].items():
        fpath = os.path.join(skin_dir, info["file"])
        if not os.path.exists(fpath):
            sys.exit("素材文件缺失: %s（请勿删除 manifest 中记载的文件）" % info["file"])
        with open(fpath, "rb") as f:
            new_payload = f.read()
        new_b64 = base64.b64encode(new_payload).decode("ascii")
        new_uri = "data:%s;base64,%s" % (info["mime"], new_b64)

        # 验证替换长度大体合理（新 base64 长度与原 base64 不同很正常，
        # 因为原图压缩参数不同——data URI 语法是正确的，位置跨度按原 occurrence
        # 的字节范围切掉后插入新 URI，不依赖长度相等）
        old_b64_len = len(info["original_uri"])
        new_uri_len = len(new_uri)
        if new_uri_len > old_b64_len * 3:
            print("!! WARNING: %s 替换后 data URI 膨胀过大 (%d → %d chars)，图片尺寸可能超标" % (
                info["file"], old_b64_len, new_uri_len))

        for occ in info["occurrences"]:
            replacements.append((occ[0], occ[1], new_uri, sha))

    # 按位置倒序替换
    replacements.sort(key=lambda x: x[0], reverse=True)
    for start, end, new_uri, sha in replacements:
        # 验证原位置的字符串（debug 断言）
        orig_slice = text[start:end]
        if orig_slice != manifest["assets"][sha]["original_uri"]:
            print("!! WARNING: 位置 [%d:%d] 原内容已变化，跳过替换" % (start, end))
            continue
        text = text[:start] + new_uri + text[end:]

    os.makedirs(os.path.dirname(os.path.abspath(out_html)), exist_ok=True)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(text)

    # QA
    print("\n--- QA 检查 ---")
    all_ok = True
    for name, fn in _QA_CHECKS_REQUIRED:
        ok = fn(text)
        detail = ""
        if name == "非空":
            detail = "%d chars" % len(text)
        elif name == "包体 <= 1.8MB":
            detail = "%.1f KB" % (len(text.encode("utf-8")) / 1024)
        status = "[OK]" if ok else "[FAIL]"
        if not ok:
            all_ok = False
        print("  %s %s  %s" % (status, name, detail))

    print("\n[OK] 灌回完成: %s (%.1f KB)" % (out_html, len(text.encode("utf-8")) / 1024))
    if not all_ok:
        print("[WARN] 部分 QA 检查未通过，见上方 [FAIL] 标记。")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="换皮工具：H5 素材提取 → 换图 → 灌回")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ext = sub.add_parser("extract", help="从 H5 提取全部内联素材")
    p_ext.add_argument("src", help="H5 文件路径")
    p_ext.add_argument("--out-dir", "-o", default="", help="输出目录（默认 skin/<H5文件名>）")

    p_rep = sub.add_parser("replace", help="将新素材灌回 H5")
    p_rep.add_argument("skin_dir", help="素材目录（含 manifest.json）")
    p_rep.add_argument("src", help="原 H5 文件路径")
    p_rep.add_argument("--out", "-o", default="", help="输出路径（默认覆盖原文件加 _skinned 后缀）")

    args = ap.parse_args()

    if args.cmd == "extract":
        out_dir = args.out_dir or os.path.join("skin", os.path.splitext(os.path.basename(args.src))[0])
        cmd_extract(args.src, out_dir)

    elif args.cmd == "replace":
        out = args.out or args.src.replace(".html", "_skinned.html")
        cmd_replace(args.skin_dir, args.src, out)


if __name__ == "__main__":
    main()
