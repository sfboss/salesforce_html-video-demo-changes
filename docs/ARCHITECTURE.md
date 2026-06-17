# Dynamic Training Mock Architecture

## Core pattern

```text
User story + scenario choice
→ selected run-as user / Salesforce CLI alias
→ compact org UI cache (apps, tabs, object describes, layout hints)
→ small scenario JSON
→ safe record snapshot JSON
→ catalog-selected reusable template
→ standalone HTML animation
→ MP4 capture pipeline
```

## Paradigm: story-first, org-aware, renderer-light

The app should not try to recreate all of Salesforce. It should collect just enough user-scoped metadata to paint a believable Lightning canvas for the selected scenario:

1. **Story intake** — capture the user story, audience, change summary, and testing notes first. These become the intro and closing slides.
2. **Run-as context** — choose the Salesforce CLI alias and visible login user. The current local default is `claytonboss+seoboss@gmail.com`.
3. **Metadata cache** — refresh a compact cache before authoring, or reuse the latest cache for fast iteration. The cache is finite: org identity, selected apps/tabs, object describe summaries, updateable fields, picklist values, and layout hints.
4. **Scenario contract** — write a small config that references object, record, fields, action/flow labels, and desired after values.
5. **Renderer family** — use one of a few universal canvases: record page with side panel, record page with action modal, list view, or related-list moment.

This keeps dynamic org data out of templates and keeps templates from becoming one-off videos.

## Reusable layers

```text
catalog/action_types.json          # supported scenario types and renderer contract
catalog/scene_primitives.json      # reusable UI animation blocks
catalog/scenario_templates.json    # wizard/front-end intake model and cache contract
config/*.json                      # one compact manifest per release/demo
samples/*.json                     # offline snapshots for fast iteration
templates/*.html                   # renderer only; no org-specific hardcoding
scripts/org_ui_wizard.py           # InquirerPy authoring workflow + cache refresh
scripts/build_mock_video_html.py   # config/sample to standalone HTML
web/ui-planner.html                # static front-end equivalent for shaping JSON
```

## Current implemented demo types

```text
field_added_layout
update_record_object_action
create_record_object_action        # generic action-modal renderer
screen_flow_action                 # generic action-modal renderer
```

## Recommended first-step workflow

```bash
python3 scripts/org_ui_wizard.py \
  --target-org claytonboss+seoboss@gmail.com \
  --refresh-cache \
  --output config/wizard_demo.json

python3 scripts/build_mock_video_html.py \
  --config config/wizard_demo.json \
  --target-org claytonboss+seoboss@gmail.com \
  --output outputs/wizard_demo.html
```

Use `--refresh-cache` when you want up-to-date metadata. Skip it when you are iterating on story language or field choices and the cache is fresh enough.

## Cache-first versus live-query

- **Cache-first authoring** is preferred for the app experience because picklists, fields, and labels are available immediately while the user answers questions.
- **Live record snapshot at build time** is still useful because the generated HTML should show current-looking values for the chosen record.
- **Cache TTL** should start at 24 hours and can be shortened for active release windows.

## Next catalog additions

```text
url_action
global_action
quick_action_with_validation_error
related_list_button
list_view_mass_action

```
