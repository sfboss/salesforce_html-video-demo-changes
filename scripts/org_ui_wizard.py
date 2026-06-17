#!/usr/bin/env python3
"""Interactive wizard for org-aware Salesforce mock demo configs.

The wizard intentionally writes the same compact JSON manifests consumed by
build_mock_video_html.py. It can refresh a lightweight UI cache from the
Salesforce CLI, but it also works as a config authoring tool when metadata is
not available locally.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALIAS = "claytonboss+seoboss@gmail.com"
CACHE_DIR = ROOT / "outputs" / "org_ui_cache"

try:
    from InquirerPy import inquirer
except ImportError:  # pragma: no cover - exercised in minimal envs
    inquirer = None


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "default"


def run_json(cmd: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return json.loads(proc.stdout)


def ask_text(message: str, default: str = "") -> str:
    if inquirer:
        return inquirer.text(message=message, default=default).execute()
    prompt = f"{message}" + (f" [{default}]" if default else "") + ": "
    value = input(prompt).strip()
    return value or default


def ask_select(message: str, choices: List[str], default: Optional[str] = None) -> str:
    if inquirer:
        return inquirer.select(message=message, choices=choices, default=default or choices[0]).execute()
    print(message)
    for idx, choice in enumerate(choices, 1):
        print(f"  {idx}. {choice}")
    raw = input(f"Choose 1-{len(choices)} [{choices.index(default) + 1 if default in choices else 1}]: ").strip()
    if raw.isdigit() and 1 <= int(raw) <= len(choices):
        return choices[int(raw) - 1]
    return default or choices[0]


def ask_confirm(message: str, default: bool = True) -> bool:
    if inquirer:
        return bool(inquirer.confirm(message=message, default=default).execute())
    raw = input(f"{message} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    return default if not raw else raw.startswith("y")


def cache_path(alias: str) -> Path:
    return CACHE_DIR / f"{slug(alias)}.json"


def refresh_cache(alias: str, api_version: str, objects: List[str]) -> Dict[str, Any]:
    org = run_json(["sf", "org", "display", "--target-org", alias, "--json"]).get("result", {})
    object_summaries = {}
    for obj in objects:
        desc = run_json(["sf", "sobject", "describe", "--sobject", obj, "--target-org", alias, "--json"]).get("result", {})
        object_summaries[obj] = {
            "label": desc.get("label", obj),
            "labelPlural": desc.get("labelPlural", obj),
            "fields": [
                {
                    "name": f.get("name"),
                    "label": f.get("label"),
                    "type": f.get("type"),
                    "updateable": f.get("updateable"),
                    "picklistValues": [p.get("value") for p in f.get("picklistValues", []) if p.get("active", True)][:50],
                }
                for f in desc.get("fields", [])
            ],
        }
    cache = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "alias": alias,
        "apiVersion": api_version,
        "org": {"username": org.get("username"), "instanceUrl": org.get("instanceUrl")},
        "objects": object_summaries,
        "notes": "Compact cache for demo authoring; generated from Salesforce CLI describe calls.",
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path(alias).write_text(json.dumps(cache, indent=2), encoding="utf-8")
    return cache


def load_cache(alias: str) -> Dict[str, Any]:
    path = cache_path(alias)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"objects": {}}


def object_choices(cache: Dict[str, Any]) -> List[str]:
    values = sorted(cache.get("objects", {}).keys())
    return values or ["Opportunity", "Account", "Case", "Contact"]


def field_choices(cache: Dict[str, Any], obj: str, updateable_only: bool = False) -> List[str]:
    fields = cache.get("objects", {}).get(obj, {}).get("fields", [])
    names = [f["name"] for f in fields if f.get("name") and (not updateable_only or f.get("updateable"))]
    return names or ["Name", "StageName", "Amount", "CloseDate", "NextStep", "Description"]


def build_config(args: argparse.Namespace) -> Dict[str, Any]:
    alias = args.target_org or ask_text("Salesforce CLI alias", DEFAULT_ALIAS)
    api_version = args.api_version
    cache = load_cache(alias)

    if args.refresh_cache or ask_confirm("Refresh compact org UI cache before choosing fields?", False):
        seed = ask_text("Objects to describe (comma-separated)", "Opportunity,Account,Case,Contact")
        cache = refresh_cache(alias, api_version, [x.strip() for x in seed.split(",") if x.strip()])
        print(f"Wrote cache: {cache_path(alias)}")

    scenario = ask_select(
        "Scenario type",
        ["field_added_layout", "update_record_object_action", "create_record_object_action", "screen_flow_action"],
        "update_record_object_action",
    )
    story_title = ask_text("User story / intro title", "As a sales manager, I can act on a record without leaving the page.")
    audience = ask_text("Audience", "Sales users")
    login_user = ask_text("Run-as / visible login user", alias)
    obj = ask_select("Target object", object_choices(cache), "Opportunity" if "Opportunity" in object_choices(cache) else None)
    record_id = ask_text("Record Id to snapshot", "006000000000000AAA")
    header_defaults = [f"{obj}.Name"]

    base = {
        "api_version": api_version,
        "org_alias": alias,
        "demo": {"id": slug(story_title).lower(), "type": scenario},
        "record": {"object_api_name": obj, "record_id": record_id},
        "release": {
            "title": story_title,
            "subtitle": "Generated from a user-scoped org UI cache plus a safe record snapshot.",
            "objectLabel": obj,
            "audience": audience,
            "loginUser": login_user,
            "closeTitle": "Personalized release training from metadata, not live screen recordings.",
            "closeSubtitle": "The scenario config stays small while the org UI cache supplies realistic labels, fields, and choices."
        },
        "header_fields": header_defaults,
        "testing": ["Rendered with the selected user context", "Fields and labels come from org metadata when cache is refreshed"],
    }

    if scenario == "field_added_layout":
        field = ask_select("Field to highlight", field_choices(cache, obj), None)
        base.update({
            "main_fields": [f"{obj}.{x}" for x in field_choices(cache, obj)[:8]],
            "side_panel": {"object_api_name": obj, "title": f"{obj} Details", "fields": [f"{obj}.{field}"], "highlight_field": f"{obj}.{field}"},
            "demo_story": {"new_field_label": field, "placement": "Top of Details panel", "save_value": ask_text("Demo save value", "Updated")},
        })
    else:
        action_label = ask_text("Action / button label", "Mark At Risk" if scenario == "update_record_object_action" else "Start Guided Update")
        first_field = ask_select("Primary field shown in modal", field_choices(cache, obj, updateable_only=True), None)
        base["record_fields"] = [f"{obj}.{x}" for x in field_choices(cache, obj)[:8]]
        base["release"].update({"actionLabel": action_label, "behavior": scenario.replace("_", " ")})
        base["action"] = {
            "type": scenario,
            "api_name": slug(action_label),
            "label": action_label,
            "button_location": "record_highlights_panel",
            "summary": ask_text("One-sentence action summary", "The guided action captures the key change and returns users to the record."),
            "fields": [{"field": f"{obj}.{first_field}", "after": ask_text(f"After/demo value for {first_field}", "Updated by guided action")}],
        }
    return base


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create org-aware demo scenario configs with InquirerPy.")
    parser.add_argument("--target-org", default=None)
    parser.add_argument("--api-version", default="v61.0")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "config" / "wizard_demo.json")
    args = parser.parse_args(argv)
    cfg = build_config(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"Wrote config: {args.output}")
    print("Next: python3 scripts/build_mock_video_html.py --config " + str(args.output) + " --target-org " + cfg["org_alias"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
