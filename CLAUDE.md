# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A fork of the NetBox community [devicetype-library](https://github.com/netbox-community/devicetype-library):
a data library of YAML definitions for **device types**, **module types**, and **rack types** that are
imported into [NetBox](https://github.com/netbox-community/netbox). It is overwhelmingly data, not code —
the Python is a validation/test harness (`tests/`) and a manufacturer-metadata generator (`okanahub/`).

This fork also adds a **manufacturer metadata library**: `manufacturers/<slug>_manufacturer.yaml`
records (vendor description, lookup aliases, support/CVE URLs, phone) generated from
`okanahub/manufacturer_data.yaml`. See "Manufacturer metadata library" below and `okanahub/README.md`.

## Repository layout

- `device-types/<Manufacturer>/*.yaml` — device type definitions (the bulk of the repo)
- `module-types/<Manufacturer>/*.yaml` — field-replaceable modules (PSUs, line cards, CPUs, GPUs…)
- `rack-types/<Manufacturer>/*.yaml` — rack/enclosure definitions
- `elevation-images/`, `module-images/` — front/rear images, named `<slug>.front.<ext>` / `<slug>.rear.<ext>`
- `manufacturers/<slug>_manufacturer.yaml` — **generated** manufacturer metadata records (fork addition)
- `schema/*.json` — JSON Schemas for validation. `generated_schema.json` is auto-synced from NetBox releases;
  `manufacturer.json` validates the manufacturer records.
- `tests/` — pytest validation suite and the domain model classes
- `okanahub/manufacturer_data.yaml` — hand-authored source of truth for the `manufacturers/` records
- `okanahub/dev_script.py` — generator/validator: reads `manufacturer_data.yaml`, validates against
  `schema/manufacturer.json`, writes `manufacturers/*.yaml` (see `okanahub/README.md`)
- `okanahub/llm_factory/` — unrelated experimental LLM helper; **not** part of the manufacturer pipeline

## Commands

Dev tooling lives in `requirements.txt` (jsonschema, pytest, PyYAML, yamllint, pre-commit, gitpython, psutil).
`pyproject.toml`/`uv.lock` exist but declare no runtime dependencies — install the dev deps with pip/uv:

```bash
pip install -r requirements.txt        # or: uv pip install -r requirements.txt
pre-commit install                     # optional but recommended
```

- Run full validation: `pytest --tb=short -v`
- Run a single test: `pytest tests/definitions_test.py -k <pattern> -v`
- Run all pre-commit hooks: `pre-commit run -a` (trailing-whitespace, yamlfmt, yamllint --strict, markdownlint, pytest)
- Regenerate the slug index (normally CI does this — see below): `python tests/generate-slug-list.py`
- Regenerate manufacturer records: `python okanahub/dev_script.py` (prints `valid/total` + any failures)
- Lint manufacturer records: `python -m yamllint -c .yamllint.yaml --strict manufacturers/`

## How validation works

`tests/definitions_test.py` is the heart of the repo. It validates every YAML file against the JSON Schemas in
`schema/` and enforces business rules implemented in `tests/device_types.py` (`DeviceType` / `ModuleType` /
`RackType`):

- **Slugs** must match `^[-a-z0-9_]+$`, be unique per manufacturer, and start with the manufacturer slug
  (e.g. `fortinet-fap-231f`, `f5-big-ip-r10600`).
- **Filename** must equal the slugified `model` (or `part_number`).
- **Child devices** (`subdevice_role: child`) must have `u_height: 0`.
- **Power**: a device must have power-ports, or PoE interfaces, or `is_powered: false`. Field-replaceable PSUs
  are modeled as `module-bays` on the device + a `power-port` on the PSU module type.

Config (schema paths, component/image types, upstream URL) lives in `tests/test_configuration.py`.

## Generated artifacts — do not hand-edit

`tests/known-slugs.json`, `known-modules.json`, `known-racks.json` are the "master slug list": a
CI-generated index (set of `[slug, path]` tuples) used to detect duplicate slugs. They are regenerated
automatically on push to `master` by `.github/workflows/master-slugs.yml` via `tests/generate-slug-list.py`.
Never edit or manually commit these — let CI produce them. (Serialized as JSON, not pickle, since pickle
executes arbitrary code on load; see `tests/cache_operations.py`.)

`schema/generated_schema.json` is auto-synced from NetBox releases on a schedule
(`.github/workflows/update-generated-schema.yml`); don't edit it by hand.

## Adding a device/module/rack type

1. Create `device-types/<Manufacturer>/<Model>.yaml` (proper-cased manufacturer dir; new vendor → new dir).
2. Minimum device fields: `manufacturer`, `model`, `slug`, `u_height`, `is_full_depth`.
   New entries should also include `airflow`, `weight`, `weight_unit` where known.
3. Run `pre-commit run -a` and `pytest -v` before opening a PR. CI (`validation.yml`) re-runs lint + schema
   validation and blocks merge on failure.

See `README.md` for the full field reference and component definitions, and `CONTRIBUTING.md` for PR guidelines.

## Manufacturer metadata library (fork-specific)

`manufacturers/<slug>_manufacturer.yaml` holds per-vendor metadata (description, `lookup`
aliases, `url`/`support_url`/`cve_portal`, `support_phone`, asset-path pointers). These files
are **generated** — do not hand-edit them.

- **Source of truth:** `okanahub/manufacturer_data.yaml`, keyed by the exact
  `device-types/<dir>` folder name.
- **Generator:** `okanahub/dev_script.py` builds a `Manufacturer` (pydantic) per entry,
  computes the six `*_path` fields from the filesystem (`_compute_paths`), validates against
  `schema/manufacturer.json`, and writes `manufacturers/<slug>_manufacturer.yaml`. It is
  data-driven and idempotent (a full regenerate every run).
- **To add/update:** edit `okanahub/manufacturer_data.yaml`, then run `python okanahub/dev_script.py`
  and `python -m yamllint -c .yamllint.yaml --strict manufacturers/`.
- **Gotchas:** edits to generated files are overwritten; adding a `device-types/<Vendor>/` dir
  alone does not create a record (add the data entry — the script reports "unauthored" dirs);
  the generator only writes, never deletes (a removed/renamed entry leaves an orphan file).

Full how-to and field reference: `okanahub/README.md`.

## Fork sync workflow (fork-specific)

This fork tracks the upstream NetBox library. Custom additions are normally *new* files (new vendors/models),
so merge conflicts are rare. Day-to-day:

- Save your own work: `git add . && git commit -m "…" && git push origin master`
- Pull upstream: `git fetch upstream && git merge upstream/master && git push origin master`

(`upstream` = `https://github.com/netbox-community/devicetype-library.git`.)
