# Dynamic Salesforce-Style Training Mock Pack

Reusable HTML + Python builder for org-aware training videos.

The goal: take a real Salesforce record snapshot, field labels, and picklist metadata, then interpolate it into a safe synthetic CRM UI that looks familiar enough for training without screen-recording a live org.

## What this demo shows

Scenario: **a new field was added near the top of the Account Details panel**.

The generated clip includes:

1. Intro card explaining the release story.
2. Mock login sequence.
3. Record detail page with Salesforce/SLDS-inspired structure.
4. Highlighted new field in the right panel.
5. Picklist edit/save visualization.
6. Closing slide with testing notes.

The HTML sets:

```js
window.__VIDEO_DURATION_SECONDS = 42;
```

So your Colab MP4 pipeline can read that value and capture at the correct length.

## Folder structure

```text
sf_dynamic_training_mock_pack/
├── README.md
├── requirements.txt
├── config/
│   └── field_added_demo.json
├── samples/
│   └── account_opportunity_mock_data.json
├── scripts/
│   └── build_mock_video_html.py
├── templates/
│   └── dynamic_salesforce_mock_template.html
└── outputs/
    └── field_added_demo_sample.html
```

## Run offline sample

```bash
cd sf_dynamic_training_mock_pack
python3 -m pip install -r requirements.txt
python3 scripts/build_mock_video_html.py \
  --sample samples/account_opportunity_mock_data.json \
  --output outputs/field_added_demo_sample.html
```

Open:

```bash
open outputs/field_added_demo_sample.html
```

## Run against a Salesforce org using CLI auth

```bash
sf org login web --alias my-sandbox
cd sf_dynamic_training_mock_pack
python3 -m pip install -r requirements.txt
python3 scripts/build_mock_video_html.py \
  --config config/field_added_demo.json \
  --target-org my-sandbox \
  --output outputs/field_added_demo_from_org.html
```

## Run against a Salesforce org using environment variables

```bash
export SF_INSTANCE_URL="https://your-domain.my.salesforce.com"
export SF_ACCESS_TOKEN="00D..."
cd sf_dynamic_training_mock_pack
python3 scripts/build_mock_video_html.py \
  --config config/field_added_demo.json \
  --output outputs/field_added_demo_from_org.html
```

## Configure the training story

Edit `config/field_added_demo.json`:

```json
{
  "record": {
    "object_api_name": "Opportunity",
    "record_id": "006000000000000AAA",
    "lookup_field": "AccountId"
  },
  "side_panel": {
    "object_api_name": "Account",
    "title": "Account Details",
    "fields": [
      "Account.Customer_Health_Score__c",
      "Account.Name",
      "Account.Type",
      "Account.Industry"
    ],
    "highlight_field": "Account.Customer_Health_Score__c"
  }
}
```

For your first real test, change only these values:

- `org_alias`
- `record.record_id`
- `side_panel.fields[0]`
- `side_panel.highlight_field`

## Notes

- This is intentionally a synthetic UI. It uses a generic cloud mark and mock domain/data patterns.
- The builder snapshots only the values required by the configured fields.
- The output HTML is standalone and safe to drop into `html_inputs` for the MP4 capture notebook.
- For exact Lightning page analysis later, add a metadata collector that reads FlexiPage/Layout metadata and converts regions into the same JSON format.
