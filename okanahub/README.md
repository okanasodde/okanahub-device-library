# Manufacturer metadata pipeline

This directory generates the **manufacturer metadata library** —
`manufacturers/<slug>_manufacturer.yaml` records describing each vendor (website,
support/CVE portals, support phone, onboarding `lookup` aliases, and pointers to the
vendor's asset directories).

## Data flow

```text
okanahub/manufacturer_data.yaml   (hand-authored source of truth)
            │
            ▼
okanahub/dev_script.py            (validate against schema/manufacturer.json + write)
            │
            ▼
manufacturers/<slug>_manufacturer.yaml   (generated — do not hand-edit)
```

`manufacturer_data.yaml` is keyed by the **exact** `device-types/<dir>` folder name
(e.g. `Aruba Networks`, `Check Point`). The generator is data-driven and idempotent: every
run rebuilds *all* records from the data file.

## Add or update a manufacturer

1. Edit `okanahub/manufacturer_data.yaml`:
   - **update** — change fields under an existing key;
   - **add** — add a new top-level key (the exact manufacturer name) with its fields.
2. Regenerate and validate:

   ```bash
   python okanahub/dev_script.py
   python -m yamllint -c .yamllint.yaml --strict manufacturers/
   ```

   `dev_script.py` prints `Generated <valid>/<total> ...`, how many `device-types/` dirs
   are still without authored data, and a `FAILED <name>: <reason>` line for any entry
   that fails schema validation (that entry is skipped, not written).

The script only **validates and writes** — it does not research field content. Vendor
descriptions, URLs, and phone numbers were gathered separately (web research); the script
does not fetch anything.

## Field reference

Authored in `manufacturer_data.yaml` (all optional except `name`, which is the YAML key):

| Field | Limit | Notes |
| --- | --- | --- |
| `description` | ≤255 | One concise factual sentence. |
| `lookup` | tokens ≤255 | Alias tokens for vendor-string matching (see below). |
| `url` | ≤200 | Official primary website. |
| `support_url` | ≤200 | Customer / TAC support portal. |
| `cve_portal` | ≤200 | Vendor's own security-advisory / PSIRT page. |
| `support_email` | ≤254 | Support email. |
| `support_phone` | ≤255 | US / global-primary support line, e.g. `+1-800-553-2447`. |
| `default_account` | ≤255 | Default support account / contract number. |
| `support_credentials` | UUID | Secrets-group reference for portal/TAC auth. |
| `logo_light` / `logo_dark` | ≤200 | Logo image paths/URLs. |

Computed automatically by the generator (`_compute_paths` in `dev_script.py`) — **do not
author these**: `device_types_path`, `elevation_images_path`, `platforms_path`,
`module_types_path`, `module_images_path`, `rack_types_path`. Each is a repo-relative path
(e.g. `device-types/Cisco`) when that asset directory exists, or `null` when it does not.

Schema: `schema/manufacturer.json`. Model: the `Manufacturer` pydantic class in
`dev_script.py`.

## `lookup` aliases

Derived from [Netmiko](https://github.com/ktbyers/netmiko) driver names so discovered
vendor strings resolve to the right manufacturer:

- For each driver, split on underscores into tokens **and** add a no-underscore variant of
  the full driver — e.g. `aruba_aoscx` → `aruba`, `aoscx`, `arubaaoscx`.
- If the vendor has no Netmiko driver, derive tokens from the name (split multiword, drop
  punctuation) — e.g. `Allied Telesis` → `allied`, `telesis`, `alliedtelesis`.
- All tokens lowercase, deduplicated, never empty.

## Caveats

1. **Edit the data file, not the generated files.** Everything in `manufacturers/*.yaml`
   is overwritten on the next run.
2. **A `device-types/<Vendor>/` folder alone does not create a record.** Generation is
   driven by `manufacturer_data.yaml` keys; add the entry (the script reports unauthored
   dirs until you do).
3. **The generator only writes, never deletes.** Removing or renaming an entry leaves the
   old `manufacturers/<old-slug>_manufacturer.yaml` behind — delete it manually.

## Dependencies

`PyYAML`, `jsonschema`, and `pydantic` (all in the dev environment; see `requirements.txt`).
`okanahub/llm_factory/` is an unrelated experimental helper and is **not** used by this
pipeline.
