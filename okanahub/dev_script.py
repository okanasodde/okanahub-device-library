from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID

import yaml
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field


class Manufacturer(BaseModel):
    """Pydantic representation of the NetBox Manufacturer organizational model.

    Mirrors the Django `Manufacturer` model and the JSON Schema in
    `schema/manufacturer.json`, and parses the YAML files under `manufacturers/`.
    """

    model_config = ConfigDict(extra="forbid")  # mirrors additionalProperties: false

    # --- Django model fields ---
    name: str = Field(
        ...,
        max_length=255,
        description="Manufacturer name (unique).",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Short free-text description of the manufacturer.",
    )
    lookup: list[Annotated[str, Field(max_length=255)]] = Field(
        default_factory=list,
        description=(
            "Alias tokens used to match discovered vendor strings to this manufacturer "
            "during onboarding (e.g. 'aruba' resolves to 'Aruba Networks'). "
            "Case-insensitive."
            "Use Netmiko's driver as lookup values, if name has underscore (e.g. 'aruba_aoscx') use each of the word sections separate (e.g. 'aruba', 'aoscx') all lower case."
            "Use Netmiko's driver as lookup values remove all underscores (e.g. 'aruba_aoscx'). use (e.g. 'arubaaoscx') all lower case."
        ),
    )
    url: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Manufacturer website.",
    )
    support_url: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Customer / TAC service portal.",
    )
    cve_portal: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Security advisory / CVE portal.",
    )
    support_email: Optional[str] = Field(
        default=None,
        max_length=254,
        description="Support email address.",
    )
    support_phone: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Support phone number.",
    )
    default_account: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Default account / contract number to quote when opening support cases.",
    )
    support_credentials: Optional[UUID] = Field(
        default=None,
        description=(
            "Secrets group used to authenticate to the vendor's support portal / open "
            "TAC cases."
        ),
    )
    logo_light: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Path to the light-theme logo image.",
    )
    logo_dark: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Path to the dark-theme logo image.",
    )

    # --- path pointers present in manufacturers/*.yaml data files ---
    device_types_path: Optional[str] = Field(
        default=None,
        description="Path to this manufacturer's device-type definitions.",
    )
    elevation_images_path: Optional[str] = Field(
        default=None,
        description="Path to this manufacturer's elevation (front/rear) images.",
    )
    platforms_path: Optional[str] = Field(
        default=None,
        description="Path to this manufacturer's platform definitions.",
    )
    module_types_path: Optional[str] = Field(
        default=None,
        description="Path to this manufacturer's module-type definitions.",
    )
    module_images_path: Optional[str] = Field(
        default=None,
        description="Path to this manufacturer's module images.",
    )
    rack_types_path: Optional[str] = Field(
        default=None,
        description="Path to this manufacturer's rack-type definitions.",
    )


# Order keys are emitted in the YAML files (mirrors manufacturers/*.yaml).
FIELD_ORDER = [
    "name",
    "description",
    "lookup",
    "url",
    "support_url",
    "cve_portal",
    "support_email",
    "support_phone",
    "default_account",
    "support_credentials",
    "logo_light",
    "logo_dark",
    "device_types_path",
    "elevation_images_path",
    "platforms_path",
    "module_types_path",
    "module_images_path",
    "rack_types_path",
]

# Optional scalar fields dropped from the YAML when unset (keeps files terse). The
# six *_path fields are exempt: they are always written, rendering `null` when the
# asset directory is absent so the file documents which asset trees exist.
OMIT_IF_NONE = {
    "description",
    "url",
    "support_url",
    "cve_portal",
    "support_email",
    "support_phone",
    "default_account",
    "support_credentials",
    "logo_light",
    "logo_dark",
}

# device-types/<Manufacturer> dir name -> (sibling top-level dir, attribute name).
PATH_DIRS = {
    "device_types_path": "device-types",
    "elevation_images_path": "elevation-images",
    "platforms_path": "platforms",
    "module_types_path": "module-types",
    "module_images_path": "module-images",
    "rack_types_path": "rack-types",
}


def slugify(text: str) -> str:
    """Convert a string to a slug format (lowercase, hyphens instead of spaces)."""
    return text.lower().replace(" ", "-").replace("_", "-")


class _IndentDumper(yaml.SafeDumper):
    """Indent block sequences under their key (yamllint `indent-sequences: true`)."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, indentless=False)


def _repo_root() -> Path:
    """Repository root (parent of the `okanahub/` package), independent of CWD."""
    return Path(__file__).resolve().parent.parent


def _compute_paths(root: Path, dir_name: str) -> dict:
    """Repo-relative POSIX path for each asset dir that exists for this manufacturer."""
    paths = {}
    for field, top_dir in PATH_DIRS.items():
        candidate = root / top_dir / dir_name
        paths[field] = f"{top_dir}/{dir_name}" if candidate.is_dir() else None
    return paths


def _to_yaml_dict(manufacturer: Manufacturer) -> dict:
    """Validated model -> ordered plain dict ready for YAML serialization."""
    dumped = manufacturer.model_dump(mode="json")
    out = {}
    for key in FIELD_ORDER:
        value = dumped.get(key)
        if key in OMIT_IF_NONE and value is None:
            continue
        out[key] = value
    return out


def main():
    root = _repo_root()
    data_file = root / "okanahub" / "manufacturer_data.yaml"
    schema_file = root / "schema" / "manufacturer.json"
    device_types = root / "device-types"
    out_dir = root / "manufacturers"
    out_dir.mkdir(exist_ok=True)

    content = yaml.safe_load(data_file.read_text(encoding="utf-8")) or {}
    validator = Draft202012Validator(
        yaml.safe_load(schema_file.read_text(encoding="utf-8"))
    )

    # Generation is driven by the authored data file: every entry becomes a file,
    # whether or not a matching device-types/ asset dir exists (some manufacturers,
    # e.g. Aruba Networks, ship no device types here).
    total = 0
    valid = 0
    failures = []

    for name, fields in sorted(content.items()):
        total += 1
        try:
            manufacturer = Manufacturer(
                name=name,
                **(fields or {}),
                **_compute_paths(root, name),
            )
            record = _to_yaml_dict(manufacturer)
            errors = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
            if errors:
                failures.append((name, "; ".join(e.message for e in errors)))
                continue
        except Exception as exc:  # pydantic ValidationError or anything else
            failures.append((name, str(exc)))
            continue

        out_path = out_dir / f"{slugify(name)}_manufacturer.yaml"
        out_path.write_text(
            yaml.dump(
                record,
                Dumper=_IndentDumper,
                sort_keys=False,
                default_flow_style=False,
                allow_unicode=True,
                explicit_start=True,
                width=4096,
            ),
            encoding="utf-8",
            newline="\n",  # force LF; yamllint's new-lines rule rejects CRLF
        )
        valid += 1

    # Progress signal for the scale-out phase: device-types dirs still unauthored.
    authored = set(content)
    unauthored = sorted(
        p.name for p in device_types.iterdir() if p.is_dir() and p.name not in authored
    )

    pct = (valid / total * 100) if total else 0.0
    print(f"Generated {valid}/{total} manufacturer files ({pct:.1f}% valid).")
    print(f"device-types dirs still without authored data: {len(unauthored)}")
    for name, reason in failures:
        print(f"  FAILED {name}: {reason}")


if __name__ == "__main__":
    main()
