#!/usr/bin/env python3
"""
Build standalone CRM-style training mock videos from either:
- a local sample/snapshot JSON, or
- a Salesforce org snapshot via Salesforce CLI auth / access token.

Demo types currently supported:
- field_added_layout
- update_record_object_action
- create_record_object_action
- screen_flow_action

Examples:
  python scripts/build_mock_video_html.py --sample samples/action_update_record_mock_data.json --output outputs/action_update_record_demo_sample.html
  python scripts/build_mock_video_html.py --config config/action_update_record_demo.json --target-org my-sandbox --output outputs/action_update_record_from_org.html
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parents[1]
FIELD_ADDED_TEMPLATE = ROOT / "templates" / "dynamic_salesforce_mock_template.html"
ACTION_TEMPLATE = ROOT / "templates" / "action_update_record_template.html"
ACTION_MODAL_DEMO_TYPES = {"update_record_object_action", "create_record_object_action", "screen_flow_action"}
DEFAULT_OUTPUT = ROOT / "outputs" / "generated_demo.html"


@dataclass
class SalesforceAuth:
    instance_url: str
    access_token: str
    api_version: str = "v61.0"


def run_json(cmd: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Command did not return JSON: {' '.join(cmd)}\n{proc.stdout[:500]}") from exc


def get_auth(target_org: Optional[str], api_version: str) -> SalesforceAuth:
    env_url = os.getenv("SF_INSTANCE_URL")
    env_token = os.getenv("SF_ACCESS_TOKEN")
    if env_url and env_token:
        return SalesforceAuth(env_url.rstrip("/"), env_token, api_version)

    alias = target_org or os.getenv("SF_TARGET_ORG")
    commands: List[List[str]] = []
    if alias:
        commands.append(["sf", "org", "display", "--target-org", alias, "--json"])
        commands.append(["sfdx", "force:org:display", "-u", alias, "--json"])
    else:
        commands.append(["sf", "org", "display", "--json"])
        commands.append(["sfdx", "force:org:display", "--json"])

    last_error: Optional[Exception] = None
    for cmd in commands:
        try:
            payload = run_json(cmd)
            result = payload.get("result", payload)
            instance_url = result.get("instanceUrl") or result.get("instance_url")
            access_token = result.get("accessToken") or result.get("access_token")
            if instance_url and access_token:
                return SalesforceAuth(instance_url.rstrip("/"), access_token, api_version)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(
        "Could not get Salesforce auth. Run `sf org login web`, pass --target-org, "
        "or set SF_INSTANCE_URL and SF_ACCESS_TOKEN.\n"
        f"Last error: {last_error}"
    )


class SalesforceClient:
    def __init__(self, auth: SalesforceAuth):
        self.auth = auth
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {auth.access_token}"})

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if path.startswith("http"):
            url = path
        else:
            url = f"{self.auth.instance_url}/services/data/{self.auth.api_version}/{path.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"GET failed {resp.status_code}: {url}\n{resp.text[:1000]}")
        return resp.json()

    def query_one(self, soql: str) -> Dict[str, Any]:
        payload = self.get("query", {"q": soql})
        records = payload.get("records", [])
        if not records:
            raise RuntimeError(f"No rows returned for SOQL: {soql}")
        return records[0]

    def describe(self, object_api_name: str) -> Dict[str, Any]:
        return self.get(f"sobjects/{object_api_name}/describe")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def demo_type(config: Dict[str, Any]) -> str:
    return (
        config.get("demo", {}).get("type")
        or config.get("demo_type")
        or config.get("type")
        or ("field_added_layout" if "side_panel" in config else "update_record_object_action")
    )


def choose_template(config: Optional[Dict[str, Any]], explicit_template: Optional[Path], sample_path: Optional[Path]) -> Path:
    if explicit_template:
        return explicit_template
    if config:
        return ACTION_TEMPLATE if demo_type(config) in ACTION_MODAL_DEMO_TYPES else FIELD_ADDED_TEMPLATE
    if sample_path and "action" in sample_path.name:
        return ACTION_TEMPLATE
    return FIELD_ADDED_TEMPLATE


def normalize_field_ref(ref: str) -> Tuple[str, str]:
    parts = ref.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Field ref must be Object.Field: {ref}")
    return parts[0], parts[1]


def soql_field(field_path: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*", field_path):
        raise ValueError(f"Unsafe field path: {field_path}")
    return field_path


def literal_id(record_id: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9]{15,18}", record_id):
        raise ValueError(f"Record Id does not look like a Salesforce Id: {record_id}")
    return record_id


def flatten_value(record: Dict[str, Any], field_path: str) -> Any:
    cur: Any = record
    for part in field_path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def describe_map(describe: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {f["name"]: f for f in describe.get("fields", [])}


def friendly_from_api(name: str) -> str:
    return re.sub(r"__c$", "", name).replace("_", " ").replace("Id", " ID").strip()


def field_label(field_path: str, describes: Dict[str, Dict[str, Any]]) -> str:
    base = field_path.split(".")[-1]
    for fmap in describes.values():
        if base in fmap:
            return fmap[base].get("label") or friendly_from_api(base)
    return friendly_from_api(base)


def format_value(value: Any, field_meta: Optional[Dict[str, Any]] = None) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "☑" if value else "☐"
    if isinstance(value, dict):
        parts = [value.get(k) for k in ["street", "city", "state", "postalCode", "country"]]
        return "\n".join([str(p) for p in parts if p])
    if field_meta:
        typ = field_meta.get("type")
        if typ == "currency" and isinstance(value, (int, float)):
            return f"${value:,.2f}"
        if typ == "percent" and isinstance(value, (int, float)):
            return f"{value:g}%"
    return str(value)


def picklist_values(field_meta: Optional[Dict[str, Any]]) -> List[str]:
    if not field_meta:
        return []
    return [p["value"] for p in field_meta.get("picklistValues", []) if p.get("active", True)]


def build_field_rows(
    refs: Iterable[str],
    records_by_object: Dict[str, Dict[str, Any]],
    describes_by_object: Dict[str, Dict[str, Any]],
    highlight_ref: Optional[str] = None,
) -> List[Dict[str, Any]]:
    rows = []
    for ref in refs:
        object_api, field_path = normalize_field_ref(ref)
        record = records_by_object.get(object_api, {})
        fmap = describes_by_object.get(object_api, {})
        meta = fmap.get(field_path.split(".")[-1])
        value = flatten_value(record, field_path)
        row = {
            "label": field_label(field_path, describes_by_object),
            "apiName": field_path.split(".")[-1],
            "value": format_value(value, meta),
        }
        vals = picklist_values(meta)
        if vals:
            row["picklistValues"] = vals
        if highlight_ref and ref == highlight_ref:
            row["isNew"] = True
        rows.append(row)
    return rows


def collect_records_for_field_added(sf: SalesforceClient, config: Dict[str, Any]) -> Dict[str, Any]:
    record_cfg = config["record"]
    main_obj = record_cfg["object_api_name"]
    main_id = literal_id(record_cfg["record_id"])
    side_obj = config["side_panel"]["object_api_name"]
    lookup_field = record_cfg.get("lookup_field")

    main_refs = config.get("main_fields", [])
    header_refs = config.get("header_fields", [])
    side_refs = config.get("side_panel", {}).get("fields", [])
    all_main_paths = {normalize_field_ref(r)[1] for r in main_refs + header_refs if normalize_field_ref(r)[0] == main_obj}
    if lookup_field:
        all_main_paths.add(lookup_field)
    all_main_paths.add("Name")
    main_soql = f"SELECT {', '.join(sorted(soql_field(f) for f in all_main_paths))} FROM {main_obj} WHERE Id = '{main_id}' LIMIT 1"
    main_record = sf.query_one(main_soql)

    if side_obj == main_obj:
        side_record = main_record
    else:
        side_id = main_record.get(lookup_field) if lookup_field else None
        if not side_id:
            raise RuntimeError(f"Could not find lookup field {lookup_field} on {main_obj} record {main_id}")
        side_paths = {normalize_field_ref(r)[1] for r in side_refs if normalize_field_ref(r)[0] == side_obj}
        side_paths.add("Name")
        side_soql = f"SELECT {', '.join(sorted(soql_field(f) for f in side_paths))} FROM {side_obj} WHERE Id = '{literal_id(side_id)}' LIMIT 1"
        side_record = sf.query_one(side_soql)

    return {main_obj: main_record, side_obj: side_record}


def build_field_added_data(config: Dict[str, Any], records_by_object: Dict[str, Any], sf: SalesforceClient) -> Dict[str, Any]:
    main_obj = config["record"]["object_api_name"]
    side_obj = config["side_panel"]["object_api_name"]
    describes_raw = {main_obj: sf.describe(main_obj), side_obj: sf.describe(side_obj)}
    describes_by_object = {obj: describe_map(desc) for obj, desc in describes_raw.items()}
    highlight_ref = config["side_panel"].get("highlight_field")

    main_name = records_by_object[main_obj].get("Name") or f"{describes_raw[main_obj].get('label', main_obj)} record"
    side_rows = build_field_rows(config["side_panel"].get("fields", []), records_by_object, describes_by_object, highlight_ref)
    main_rows = build_field_rows(config.get("main_fields", []), records_by_object, describes_by_object)
    header_rows = build_field_rows(config.get("header_fields", []), records_by_object, describes_by_object)

    story = config.get("demo_story", {})
    if story.get("save_value"):
        for row in side_rows:
            if highlight_ref and row.get("apiName") == highlight_ref.split(".")[-1]:
                row["value"] = row.get("value") or story["save_value"]
                if row.get("picklistValues") and story["save_value"] not in row["picklistValues"]:
                    row["picklistValues"].insert(0, story["save_value"])

    return {
        "release": config.get("release", {}),
        "main": {
            "objectApiName": main_obj,
            "label": describes_raw[main_obj].get("label", main_obj),
            "name": main_name,
            "icon": describes_raw[main_obj].get("label", main_obj)[:1].upper(),
            "header": header_rows,
            "fields": main_rows,
        },
        "side": {
            "objectApiName": side_obj,
            "label": describes_raw[side_obj].get("label", side_obj),
            "title": config["side_panel"].get("title") or f"{describes_raw[side_obj].get('label', side_obj)} Details",
            "icon": describes_raw[side_obj].get("label", side_obj)[:1].upper(),
            "fields": side_rows,
        },
        "highlightField": (highlight_ref.split(".")[-1] if highlight_ref else None),
        "testing": config.get("testing", []),
    }


def direct_field_api(field_ref: str, expected_object: str) -> str:
    obj, path = normalize_field_ref(field_ref)
    if obj != expected_object:
        raise ValueError(f"Action update fields must target {expected_object}; got {field_ref}")
    if "." in path:
        raise ValueError(f"Action update fields must be direct fields, not relationships: {field_ref}")
    return path


def collect_record_for_action(sf: SalesforceClient, config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    record_cfg = config["record"]
    obj = record_cfg["object_api_name"]
    record_id = literal_id(record_cfg["record_id"])
    describe = sf.describe(obj)
    fmap = describe_map(describe)

    refs: List[str] = []
    refs.extend(config.get("header_fields", []))
    refs.extend(config.get("record_fields", []))
    for field_cfg in config.get("action", {}).get("fields", []):
        ref = field_cfg.get("field") or field_cfg.get("field_ref")
        if ref:
            api = direct_field_api(ref, obj)
            if api not in fmap:
                raise RuntimeError(f"Configured action field not found on {obj}: {api}")
            refs.append(ref)
    refs.append(f"{obj}.Name")

    paths = sorted({normalize_field_ref(r)[1] for r in refs if normalize_field_ref(r)[0] == obj})
    soql = f"SELECT {', '.join(soql_field(p) for p in paths)} FROM {obj} WHERE Id = '{record_id}' LIMIT 1"
    record = sf.query_one(soql)
    return record, describe


def build_action_update_data(config: Dict[str, Any], record: Dict[str, Any], describe_raw: Dict[str, Any]) -> Dict[str, Any]:
    obj = config["record"]["object_api_name"]
    fmap = describe_map(describe_raw)
    describes = {obj: fmap}
    records = {obj: record}
    label = describe_raw.get("label", obj)
    plural = describe_raw.get("labelPlural") or f"{label}s"
    main_name = record.get("Name") or f"{label} record"

    header_rows = build_field_rows(config.get("header_fields", []), records, describes)
    record_rows = build_field_rows(config.get("record_fields", []), records, describes)

    action_cfg = config.get("action", {})
    action_fields: List[Dict[str, Any]] = []
    after_values: Dict[str, str] = {}
    for field_cfg in action_cfg.get("fields", []):
        ref = field_cfg.get("field") or field_cfg.get("field_ref")
        api = direct_field_api(ref, obj)
        meta = fmap.get(api, {})
        before_raw = flatten_value(record, api)
        after_raw = field_cfg.get("after", field_cfg.get("value_after", ""))
        before = format_value(before_raw, meta)
        after = format_value(after_raw, meta)
        vals = picklist_values(meta)
        if after and vals and after not in vals:
            vals.insert(0, after)
        row = {
            "label": field_cfg.get("label") or meta.get("label") or friendly_from_api(api),
            "apiName": api,
            "before": before,
            "after": after,
        }
        if vals:
            row["picklistValues"] = vals
        action_fields.append(row)
        after_values[api] = after

    # Ensure the details panel contains fields touched by the action, then show after-save state.
    existing = {r.get("apiName") for r in record_rows}
    for af in action_fields:
        if af["apiName"] not in existing:
            record_rows.insert(1, {"label": af["label"], "apiName": af["apiName"], "value": af["before"]})
            existing.add(af["apiName"])
    for row in record_rows:
        if row.get("apiName") in after_values:
            row["value"] = after_values[row["apiName"]]
            row["isActionField"] = True

    release = config.get("release", {})
    release.setdefault("objectLabel", label)
    release.setdefault("actionLabel", action_cfg.get("label", "Update Record"))
    release.setdefault("behavior", "Update record")

    return {
        "release": release,
        "main": {
            "objectApiName": obj,
            "label": label,
            "pluralLabel": plural,
            "name": main_name,
            "icon": label[:1].upper(),
            "header": header_rows,
            "fields": record_rows,
        },
        "action": {
            "type": demo_type(config),
            "apiName": action_cfg.get("api_name") or action_cfg.get("apiName") or "Update_Record_Action",
            "label": action_cfg.get("label", "Update Record"),
            "buttonLocation": action_cfg.get("button_location", "record_highlights_panel"),
            "summary": action_cfg.get("summary", "This object-specific action updates configured fields and saves the record."),
            "fields": action_fields,
        },
        "testing": config.get("testing", []),
    }


BAD_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean_text(value: str) -> str:
    value = str(value).encode("utf-8", "replace").decode("utf-8", "replace")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return BAD_CONTROL_CHARS.sub(" ", value)


def clean_json_payload(value: Any) -> Any:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        return [clean_json_payload(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json_payload(v) for v in value]
    if isinstance(value, dict):
        return {clean_text(k): clean_json_payload(v) for k, v in value.items()}
    return value


def json_for_script_tag(data: Dict[str, Any]) -> str:
    json_text = json.dumps(clean_json_payload(data), ensure_ascii=False, separators=(",", ":"))
    return (
        json_text
        .replace("&", "\\u0026")
        .replace("<", "\\u003C")
        .replace(">", "\\u003E")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_html(template_path: Path, data: Dict[str, Any], output_path: Path) -> None:
    html = template_path.read_text(encoding="utf-8")
    html = html.replace("__SF_MOCK_DATA_JSON__", json_for_script_tag(data))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate standalone dynamic CRM mock training HTML.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--template", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-org", default=None)
    parser.add_argument("--api-version", default=None)
    parser.add_argument("--snapshot-out", type=Path, default=ROOT / "outputs" / "last_snapshot.json")
    parser.add_argument("--sample", type=Path, help="Use local mock_data JSON instead of connecting to Salesforce.")
    args = parser.parse_args(argv)

    if args.sample:
        data = load_json(args.sample)
        template = choose_template(None, args.template, args.sample)
        render_html(template, data, args.output)
        print(f"Wrote sample HTML: {args.output}")
        print("VIDEO_DURATION_SECONDS=48" if template == ACTION_TEMPLATE else "VIDEO_DURATION_SECONDS=45")
        return 0

    config_path = args.config or (ROOT / "config" / "field_added_demo.json")
    config = load_json(config_path)
    template = choose_template(config, args.template, None)
    api_version = args.api_version or config.get("api_version", "v61.0")
    auth = get_auth(args.target_org or config.get("org_alias"), api_version)
    sf = SalesforceClient(auth)

    typ = demo_type(config)
    if typ in ACTION_MODAL_DEMO_TYPES:
        record, desc = collect_record_for_action(sf, config)
        data = build_action_update_data(config, record, desc)
    elif typ == "field_added_layout":
        records = collect_records_for_field_added(sf, config)
        data = build_field_added_data(config, records, sf)
    else:
        raise RuntimeError(f"Unsupported demo type: {typ}")

    save_json(args.snapshot_out, data)
    render_html(template, data, args.output)
    print(f"Wrote HTML: {args.output}")
    print(f"Wrote snapshot: {args.snapshot_out}")
    print("VIDEO_DURATION_SECONDS=48" if template == ACTION_TEMPLATE else "VIDEO_DURATION_SECONDS=45")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")
        raise SystemExit(1)
