#!/usr/bin/env python3
"""Compare frozen CPC records for research; write real records only under data/."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/research/03-materials.json"
OUTPUT = ROOT / "data/research/r4/cpc-probe.json"
MATERIAL_IDS = ("rxnorm-cpc-2026-09-08", "rxnorm-cpc-2026-10-05")


def rows(archive, name, width):
    with archive.open("rrf/" + name + ".RRF") as stream:
        for number, raw in enumerate(stream, 1):
            fields = raw.decode("utf-8").rstrip("\r\n").split("|")
            if len(fields) != width + 1 or fields[-1] != "":
                raise ValueError(f"{name}:{number}: invalid field count or terminator")
            yield fields[:-1]


def frozen_path(material):
    path = ROOT / material["local_path"]
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if not material.get("initial_file_checks_passed"):
        raise ValueError(f"R3 checks are not recorded: {material['id']}")
    if digest.hexdigest() != material["local_sha256"]:
        raise ValueError(f"Frozen SHA-256 mismatch: {material['id']}")
    return path


def names(path, needed=None):
    result = {}
    with zipfile.ZipFile(path) as archive:
        for row in rows(archive, "RXNCONSO", 18):
            if row[11] == "RXNORM" and (needed is None or row[0] in needed):
                result.setdefault(row[0], set()).add((row[12], row[14]))
    return result


def details(path, selected):
    relations = {key: set() for key in selected}
    attributes = {key: set() for key in selected}
    with zipfile.ZipFile(path) as archive:
        for row in rows(archive, "RXNREL", 16):
            # Appendix 1: RXCUI2 --RELA--> RXCUI1, concept-level rows only.
            if (row[10] == "RXNORM" and row[4] in selected
                    and row[2] == "CUI" and row[6] == "CUI"):
                relations[row[4]].add((row[7], row[0], row[3]))
        for row in rows(archive, "RXNSAT", 13):
            if row[9] == "RXNORM" and row[0] in selected:
                attributes[row[0]].add((row[4], row[8], row[10]))
    endpoints = selected | {target for rel in relations.values() for _, target, _ in rel}
    labels = names(path, endpoints)
    return {
        "outgoing_rel": {key: sorted(value) for key, value in relations.items()},
        "attributes": {key: sorted(value) for key, value in attributes.items()},
        "endpoint_names": {key: sorted(value) for key, value in sorted(labels.items())},
    }


def main():
    materials = {item["id"]: item for item in json.loads(MANIFEST.read_text())["materials"]}
    paths = [frozen_path(materials[key]) for key in MATERIAL_IDS]
    before, after = [names(path) for path in paths]
    old, new = set(before), set(after)
    common = old & new
    categories = {
        "unchanged": {key for key in common if before[key] == after[key]},
        "changed_rows": {key for key in common if before[key] != after[key]},
        "source_only": old - new,
        "target_only": new - old,
    }
    samples = {}
    for category, keys in categories.items():
        pool = [key for key in keys if any(
            tty == "SCD" for tty, _ in before.get(key, set()) | after.get(key, set())
        )]
        if not keys:
            samples[category] = None
            continue
        key = min(pool or keys, key=int)
        samples[category] = {
            "rxcui": key,
            "source": sorted(before.get(key, set())),
            "target": sorted(after.get(key, set())),
        }
    selected = {sample["rxcui"] for sample in samples.values() if sample}
    observations = [details(path, selected) for path in paths]
    equality = {}
    for key in sorted(selected, key=int):
        endpoints = {r[1] for observation in observations for r in observation["outgoing_rel"][key]}
        equality[key] = {
            name: observations[0][name][key] == observations[1][name][key]
            for name in ("outgoing_rel", "attributes")
        }
        equality[key]["endpoint_names"] = all(
            observations[0]["endpoint_names"].get(endpoint, [])
            == observations[1]["endpoint_names"].get(endpoint, [])
            for endpoint in endpoints
        )
    counts = {key: len(value) for key, value in categories.items()}
    report = {
        "format_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "SAB=RXNORM; RXCUI -> set(TTY,STR). Sample each category by smallest numeric SCD RXCUI, otherwise any TTY. Equality is limited to recorded projections, not clinical equivalence.",
        "input_sha256": {key: materials[key]["local_sha256"] for key in MATERIAL_IDS},
        "distinct_rxcui": dict(zip(MATERIAL_IDS, (len(before), len(after)))),
        "category_counts": counts,
        "selected": samples,
        "detail": dict(zip(MATERIAL_IDS, observations)),
        "selected_equality": equality,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"category_counts": counts, "samples": len(selected),
                      "local_report": str(OUTPUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"Probe failed: {error}", file=sys.stderr)
        sys.exit(1)
