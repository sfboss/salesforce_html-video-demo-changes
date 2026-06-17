#!/usr/bin/env python3
"""Validate demo configs against the local action/demo catalog."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dotted_get(payload: Dict[str, Any], path: str) -> Any:
    cur: Any = payload
    for part in path.split("."):
        if part.endswith("[]"):
            key = part[:-2]
            cur = cur.get(key, []) if isinstance(cur, dict) else []
            return cur
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def main() -> int:
    catalog = load(ROOT / "catalog" / "action_types.json")["actionTypes"]
    registry = load(ROOT / "catalog" / "demo_registry.json")["demos"]
    errors = []
    for demo in registry:
        cfg_path = ROOT / demo["config"]
        if not cfg_path.exists():
            errors.append(f"Missing config: {cfg_path}")
            continue
        cfg = load(cfg_path)
        typ = cfg.get("demo", {}).get("type") or cfg.get("demo_type") or demo.get("type")
        if typ not in catalog:
            errors.append(f"{cfg_path}: unknown demo/action type {typ}")
            continue
        required = catalog[typ].get("requiredConfig", [])
        for req in required:
            # Treat action.fields[].field and action.fields[].after specially.
            if req.startswith("action.fields[]"):
                fields = cfg.get("action", {}).get("fields", [])
                key = req.split(".")[-1]
                if not fields or any(key not in f for f in fields):
                    errors.append(f"{cfg_path}: missing {req}")
            elif dotted_get(cfg, req) in (None, ""):
                errors.append(f"{cfg_path}: missing {req}")
    if errors:
        print("Catalog lint failed:")
        for err in errors:
            print(" -", err)
        return 1
    print(f"Catalog lint passed for {len(registry)} demos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
