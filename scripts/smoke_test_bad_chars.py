#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "bad_chars_torture_test.html"


def main() -> int:
    build = ROOT / "scripts" / "build_mock_video_html.py"
    sample = ROOT / "samples" / "bad_chars_torture_test.json"
    proc = subprocess.run(
        [sys.executable, str(build), "--sample", str(sample), "--output", str(OUT)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        return proc.returncode

    html = OUT.read_text(encoding="utf-8")
    data_match = re.search(r'<script id="sf-mock-data" type="application/json">(.*?)</script>', html, re.S)
    if not data_match:
        raise AssertionError("Missing sf-mock-data JSON script block")
    json.loads(data_match.group(1))

    if html.lower().count("</script>") != 2:
        raise AssertionError("Unexpected script close count; JSON may contain unsafe literal </script>")

    js_blocks = re.findall(r'<script(?![^>]*application/json)[^>]*>(.*?)</script>', html, re.S)
    check_file = ROOT / "outputs" / "_syntax_check.js"
    check_file.write_text("\n".join(js_blocks), encoding="utf-8")
    node = subprocess.run(["node", "--check", str(check_file)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if node.returncode != 0:
        print(node.stdout)
        print(node.stderr, file=sys.stderr)
        return node.returncode
    print(f"PASS: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
