"""Generate the platform library from the Netmiko driver CSV.

Reads `netmiko_platforms_2.csv` (columns: netmiko_driver, platform_name, description),
maps each driver to an existing manufacturer directory, builds a `Platform` (pydantic)
record mirroring the Nautobot `Platform` model, validates it against
`schema/platform.json`, and writes `platforms/<Manufacturer>/<netmiko_driver>.yaml`.

Data-driven and idempotent (a full regenerate every run), mirroring okanahub/dev_script.py.
Manufacturer directory names must match the `okanahub/manufacturer_data.yaml` keys exactly,
so that `dev_script.py`'s `_compute_paths` picks up `platforms/<Manufacturer>` and emits
`platforms_path` on each manufacturer record.
"""

import csv
from pathlib import Path
from typing import Optional

import yaml
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field

# Reuse the shared YAML dumper + slug helper from the manufacturer generator so both
# libraries emit byte-identical formatting (indented sequences, LF newlines, etc.).
from dev_script import _IndentDumper


class Platform(BaseModel):
    """Pydantic representation of the Nautobot Platform organizational model.

    Mirrors the Django `Platform` model and the JSON Schema in `schema/platform.json`,
    and parses the YAML files under `platforms/`.
    """

    model_config = ConfigDict(extra="forbid")  # mirrors additionalProperties: false

    name: str = Field(..., max_length=255, description="Platform name (unique).")
    manufacturer: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Manufacturer this platform is limited to.",
    )
    network_driver: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Normalized network driver, e.g. cisco_ios, arista_eos.",
    )
    napalm_driver: Optional[str] = Field(
        default=None,
        max_length=255,
        description="NAPALM driver name.",
    )
    napalm_args: Optional[dict] = Field(
        default=None,
        description="Additional NAPALM driver arguments (JSON object).",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Short free-text description of the platform.",
    )


# Order keys are emitted in the YAML files.
FIELD_ORDER = [
    "name",
    "manufacturer",
    "network_driver",
    "napalm_driver",
    "napalm_args",
    "description",
]

# Optional fields dropped from the YAML when unset (keeps files terse).
OMIT_IF_NONE = {"napalm_driver", "napalm_args"}

# netmiko_driver -> manufacturer directory (exact okanahub/manufacturer_data.yaml key).
# Drivers absent from this map have no manufacturer record and are skipped (reported).
DRIVER_TO_MANUFACTURER = {
    # --- direct prefix matches ---
    "a10": "A10",
    "accedian": "Accedian",
    "adtran_os": "Adtran",
    "adva_fsp150f2": "ADVA",
    "adva_fsp150f3": "ADVA",
    "alcatel_aos": "Alcatel-Lucent",
    "alcatel_sros": "Alcatel-Lucent",
    "allied_telesis_awplus": "Allied Telesis",
    "arista_eos": "Arista",
    "arris_cer": "ARRIS",
    "aruba_aoscx": "Aruba Networks",
    "aruba_os": "Aruba Networks",
    "aruba_osswitch": "Aruba Networks",
    "aruba_procurve": "Aruba Networks",
    "audiocode_66": "AudioCodes",
    "audiocode_72": "AudioCodes",
    "audiocode_shell": "AudioCodes",
    "avaya_ers": "Avaya",
    "avaya_vsp": "Avaya",
    "brocade_fastiron": "Brocade",
    "brocade_fos": "Brocade",
    "brocade_netiron": "Brocade",
    "brocade_nos": "Brocade",
    "brocade_vdx": "Brocade",
    "brocade_vyos": "Brocade",
    "calix_b6": "Calix",
    "checkpoint_gaia": "Check Point",
    "ciena_saos": "Ciena",
    "ciena_saos10": "Ciena",
    "ciena_waveserver": "Ciena",
    "cisco_apic": "Cisco",
    "cisco_asa": "Cisco",
    "cisco_ftd": "Cisco",
    "cisco_ios": "Cisco",
    "cisco_nxos": "Cisco",
    "cisco_s200": "Cisco",
    "cisco_s300": "Cisco",
    "cisco_s500": "Cisco",
    "cisco_tp": "Cisco",
    "cisco_viptela": "Cisco",
    "cisco_wlc": "Cisco",
    "cisco_xe": "Cisco",
    "cisco_xr": "Cisco",
    "dell_dnos9": "Dell",
    "dell_force10": "Dell",
    "dell_isilon": "Dell",
    "dell_os10": "Dell",
    "dell_os6": "Dell",
    "dell_os9": "Dell",
    "dell_powerconnect": "Dell",
    "dell_sonic": "Dell",
    "digi_transport": "Digi",
    "dlink_ds": "D-Link",
    "edgecore_sonic": "Edgecore",
    "eltex": "Eltex",
    "eltex_esr": "Eltex",
    "ericsson_ipos": "Ericsson",
    "ericsson_mltn63": "Ericsson",
    "ericsson_mltn66": "Ericsson",
    "extreme": "Extreme Networks",
    "extreme_ers": "Extreme Networks",
    "extreme_exos": "Extreme Networks",
    "extreme_netiron": "Extreme Networks",
    "extreme_nos": "Extreme Networks",
    "extreme_slx": "Extreme Networks",
    "extreme_tierra": "Extreme Networks",
    "extreme_vdx": "Extreme Networks",
    "extreme_vsp": "Extreme Networks",
    "extreme_wing": "Extreme Networks",
    "f5_linux": "F5",
    "f5_ltm": "F5",
    "f5_tmsh": "F5",
    "fiberstore_fsos": "FS",
    "fiberstore_fsosv2": "FS",
    "fiberstore_networkos": "FS",
    "fortinet": "Fortinet",
    "fujitsu_sir": "Fujitsu",
    "generic": "Generic",
    "generic_termserver": "Generic",
    "hp_comware": "HP",
    "hp_procurve": "HP",
    "huawei": "Huawei",
    "huawei_olt": "Huawei",
    "huawei_ont": "Huawei",
    "huawei_smartax": "Huawei",
    "huawei_smartaxmmi": "Huawei",
    "huawei_vrp": "Huawei",
    "huawei_vrpv8": "Huawei",
    "infinera_packet": "Infinera",
    "juniper": "Juniper",
    "juniper_junos": "Juniper",
    "juniper_screenos": "Juniper",
    "lancom_lcossx4": "LANCOM",
    "lancom_lcossx5": "LANCOM",
    "mellanox": "Mellanox",
    "mellanox_mlnxos": "Mellanox",
    "mikrotik_routeros": "MikroTik",
    "mikrotik_switchos": "MikroTik",
    "moxa_nos": "Moxa",
    "nec_ix": "NEC",
    "netapp_cdot": "NetApp",
    "netgear_prosafe": "Netgear",
    "nokia_srl": "Nokia",
    "nokia_sros": "Nokia",
    "paloalto_panos": "Palo Alto",
    "pluribus": "Pluribus",
    "quanta_mesh": "QCT",
    "rad_etx": "RAD",
    "raisecom_roap": "Raisecom",
    "raisecom_ros": "Raisecom",
    "ruckus_fastiron": "Ruckus",
    "ruijie_os": "Ruijie",
    "sophos_sfos": "Sophos",
    "supermicro_smis": "Supermicro",
    "telcosystems_binos": "Telco Systems",
    "tplink_jetstream": "TP-Link",
    "ubiquiti_edge": "Ubiquiti",
    "ubiquiti_edgerouter": "Ubiquiti",
    "ubiquiti_edgeswitch": "Ubiquiti",
    "ubiquiti_unifiswitch": "Ubiquiti",
    "vertiv_mph": "Vertiv",
    "watchguard_fireware": "WatchGuard",
    "yamaha": "YAMAHA",
    "zpe_nodegrid": "ZPE",
    "zte_zxros": "ZTE",
    "zyxel_os": "Zyxel",
    # --- acquired brand -> acquirer's existing manufacturer record ---
    "netscaler": "Citrix",
    "enterasys": "Extreme Networks",
    "coriant": "Infinera",
    "cumulus_linux": "Nvidia",
    "cloudgenix_ion": "Palo Alto",
    "silverpeak_vxoa": "Aruba Networks",
    "hirschmann_hios": "Belden",
    # --- newly authored manufacturer records (see okanahub/manufacturer_data.yaml) ---
    "alaxala_ax26s": "ALAXALA",
    "alaxala_ax36s": "ALAXALA",
    "apresia_aeos": "APRESIA Systems",
    "asterfusion_asternos": "Asterfusion",
    "avara_aos": "Avara Technologies",
    "aviat_wtm": "Aviat Networks",
    "broadcom_icos": "Broadcom",
    "casa_cmts": "Casa Systems",
    "cdot_cros": "C-DOT",
    "centec_os": "Centec Networks",
    "corelight_linux": "Corelight",
    "ekinops_ek360": "Ekinops",
    "oneaccess_oneos": "Ekinops",  # OneAccess acquired by Ekinops (2018)
    "endace": "Endace",
    "flexvnf": "Versa Networks",
    "furukawa_fitelnet": "Furukawa Electric",
    "garderos_grs": "Garderos",
    "h3c_comware": "H3C",
    "hillstone_stoneos": "Hillstone Networks",
    "iij_seilos": "IIJ",
    "ipinfusion_ocnos": "IP Infusion",
    "maipu": "Maipu",
    "sixwind_os": "6WIND",
    "teldat_cit": "Teldat",
    "bintec_boss": "Teldat",  # bintec elmeg brand now under Teldat
    "vyos": "VyOS",
    "vyatta_vyos": "VyOS",  # VyOS is the open successor to Vyatta
    # --- absorbed brands folded into existing owners ---
    "keymile": "Adtran",  # Keymile now under Adtran (via ADVA)
    "keymile_nos": "Adtran",
    "mrv_lx": "Adtran",  # MRV now under Adtran (via ADVA)
    "mrv_optiswitch": "Adtran",
    # --- generic host / software OSes (no vendor) ---
    "linux": "Generic",
    "ovs_linux": "Generic",
}

# netmiko_driver -> well-established NAPALM driver. Others are left unset.
NAPALM_DRIVERS = {
    "cisco_ios": "ios",
    "cisco_xe": "ios",
    "cisco_nxos": "nxos",
    "cisco_xr": "iosxr",
    "arista_eos": "eos",
    "juniper_junos": "junos",
    "juniper": "junos",
    "paloalto_panos": "panos",
}


# Typographic characters that appear in the CSV, mapped to ASCII. The library requires
# ASCII-only definition files (tests/definitions_test.py rejects non-ASCII), so normalize
# on the way in rather than carrying the offending code points into the YAML.
_ASCII_MAP = str.maketrans({
    "—": "-",    # em dash
    "–": "-",    # en dash
    "→": "->",   # rightwards arrow
    "‘": "'",    # left single quote
    "’": "'",    # right single quote
    "“": '"',    # left double quote
    "”": '"',    # right double quote
})


def _ascii(text: Optional[str]) -> Optional[str]:
    """Fold known typographic characters to ASCII; None passes through unchanged."""
    return text.translate(_ASCII_MAP) if text else text


def _repo_root() -> Path:
    """Repository root (parent of the `okanahub/` package), independent of CWD."""
    return Path(__file__).resolve().parent.parent


def _to_yaml_dict(platform: Platform) -> dict:
    """Validated model -> ordered plain dict ready for YAML serialization."""
    dumped = platform.model_dump(mode="json")
    out = {}
    for key in FIELD_ORDER:
        value = dumped.get(key)
        if key in OMIT_IF_NONE and value is None:
            continue
        out[key] = value
    return out


def main():
    root = _repo_root()
    csv_file = root / "netmiko_platforms_2.csv"
    schema_file = root / "schema" / "platform.json"
    out_root = root / "platforms"
    out_root.mkdir(exist_ok=True)

    validator = Draft202012Validator(
        yaml.safe_load(schema_file.read_text(encoding="utf-8"))
    )

    written = 0
    vendors = set()
    skipped = []
    failures = []

    with csv_file.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            driver = (row.get("netmiko_driver") or "").strip()
            if not driver:
                continue

            manufacturer = DRIVER_TO_MANUFACTURER.get(driver)
            if manufacturer is None:
                skipped.append(driver)
                continue

            try:
                platform = Platform(
                    name=_ascii((row.get("platform_name") or "").strip()),
                    manufacturer=manufacturer,
                    network_driver=driver,
                    napalm_driver=NAPALM_DRIVERS.get(driver),
                    description=_ascii((row.get("description") or "").strip()) or None,
                )
                record = _to_yaml_dict(platform)
                errors = sorted(
                    validator.iter_errors(record), key=lambda e: list(e.path)
                )
                if errors:
                    failures.append((driver, "; ".join(e.message for e in errors)))
                    continue
            except Exception as exc:  # pydantic ValidationError or anything else
                failures.append((driver, str(exc)))
                continue

            vendor_dir = out_root / manufacturer
            vendor_dir.mkdir(exist_ok=True)
            out_path = vendor_dir / f"{driver}.yaml"
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
            written += 1
            vendors.add(manufacturer)

    print(f"Generated {written} platform files across {len(vendors)} vendors.")
    print(f"Skipped {len(skipped)} drivers with no manufacturer record:")
    for driver in sorted(skipped):
        print(f"  - {driver}")
    for driver, reason in failures:
        print(f"  FAILED {driver}: {reason}")


if __name__ == "__main__":
    main()
