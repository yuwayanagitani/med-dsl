#!/usr/bin/env python3
"""RxNorm CPC 2026-09-08 → 2026-10-05 の版更新を、契約（src/med_dsl/terminology_audit.py）の核の関数で監査する（P2-u、設計82）。

台帳（docs/research/03-materials.json）の SHA-256 と取得状態を確かめた ZIP だけを読む。ZIP は展開せず、配布された SQL・シェルは実行しない。
列の位置は、ZIP に同梱された Table_scripts_mysql_rxn.sql の列の並びから名前で引く。ネットワーク通信はしない。
実レコード（概念の ID・名称・属性）を含む結果は Git 管理外の data/research/r4/ に書き、標準出力には集計だけを出す。"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from med_dsl import terminology_audit as audit

LEDGER = ROOT / "docs/research/03-materials.json"
OLD_ID, NEW_ID = "rxnorm-cpc-2026-09-08", "rxnorm-cpc-2026-10-05"
SOURCE = "RXNORM"
SQL_MEMBER = "scripts/mysql/Table_scripts_mysql_rxn.sql"
STRENGTH_ATTRIBUTES = ("RXN_AVAILABLE_STRENGTH", "RXN_STRENGTH", "RXN_BOSS_STRENGTH_NUM_VALUE", "RXN_BOSS_STRENGTH_NUM_UNIT",
                       "RXN_BOSS_STRENGTH_DENOM_VALUE", "RXN_BOSS_STRENGTH_DENOM_UNIT")
NEEDED = {"RXNCONSO": ("RXCUI", "RXAUI", "SAB", "TTY", "STR"), "RXNREL": ("RXCUI1", "STYPE1", "REL", "RXCUI2", "STYPE2", "RELA", "SAB"),
          "RXNSAT": ("RXAUI", "STYPE", "ATN", "SAB", "ATV")}


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def columns_from_sql(text):
    """CREATE TABLE の列の並びを、表ごとに名前の列で返す。"""
    found = {}
    for name, body in re.findall(r"CREATE\s+TABLE\s+(\w+)\s*\((.*?)\)\s*;", text, flags=re.S | re.I):
        names = []
        for line in body.splitlines():
            token = line.strip().rstrip(",").split()
            if token and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token[0]):
                names.append(token[0].upper())
        found[name.upper()] = names
    return found


def position_tables(archive):
    columns = columns_from_sql(archive.read(SQL_MEMBER).decode("utf-8"))
    tables = {}
    for table, names in NEEDED.items():
        if table not in columns:
            raise SystemExit(f"{table} の列の定義が {SQL_MEMBER} にありません")
        missing = [n for n in names if n not in columns[table]]
        if missing:
            raise SystemExit(f"{table} に列 {missing} がありません")
        tables[table] = {n: columns[table].index(n) for n in names}
    return tables, columns


def lines(archive, member):
    with archive.open(member) as stream:
        for raw in stream:
            yield raw.decode("utf-8").rstrip("\n").split("|")


def normalize(path, version, tables=None):
    """ZIP の三つの RRF から、契約の snapshot（出典 RXNORM のみ）と、読み飛ばした行の件数を作る。"""
    archive = zipfile.ZipFile(path)
    positions, _ = position_tables(archive)
    stats = Counter()
    p = positions["RXNCONSO"]
    atoms, concept_atoms = {}, defaultdict(list)
    for row in lines(archive, "rrf/RXNCONSO.RRF"):
        if row[p["SAB"]] != SOURCE:
            stats["conso_other_source"] += 1
            continue
        atom_id = row[p["RXAUI"]]
        if atom_id in atoms:
            stats["conso_duplicate_atom"] += 1
            continue
        atoms[atom_id] = {"id": atom_id, "kind": row[p["TTY"]], "name": row[p["STR"]], "attributes": set()}
        concept_atoms[row[p["RXCUI"]]].append(atom_id)
        stats["conso_atoms"] += 1
    p = positions["RXNSAT"]
    for row in lines(archive, "rrf/RXNSAT.RRF"):
        if row[p["SAB"]] != SOURCE:
            stats["sat_other_source"] += 1
            continue
        if row[p["STYPE"]] != "AUI":
            stats["sat_not_atom"] += 1
            continue
        atom = atoms.get(row[p["RXAUI"]])
        if atom is None:
            stats["sat_orphan_atom"] += 1
            continue
        pair = (row[p["ATN"]], row[p["ATV"]])
        if pair in atom["attributes"]:
            stats["sat_duplicate"] += 1
            continue
        atom["attributes"].add(pair)
        stats["sat_attributes"] += 1
    p = positions["RXNREL"]
    relations = defaultdict(set)
    for row in lines(archive, "rrf/RXNREL.RRF"):
        if row[p["SAB"]] != SOURCE:
            stats["rel_other_source"] += 1
            continue
        if row[p["STYPE1"]] != "CUI" or row[p["STYPE2"]] != "CUI":
            stats["rel_not_concept"] += 1
            continue
        owner = row[p["RXCUI2"]]
        if owner not in concept_atoms:
            stats["rel_orphan_owner"] += 1
            continue
        pair = (row[p["RELA"]] or row[p["REL"]], row[p["RXCUI1"]])
        if pair in relations[owner]:
            stats["rel_duplicate"] += 1
            continue
        relations[owner].add(pair)
        stats["rel_relations"] += 1
    concepts = []
    for rxcui in sorted(concept_atoms):
        concept_atoms_list = [{"id": a["id"], "kind": a["kind"], "name": a["name"], "attributes": [{"name": n, "value": v} for n, v in sorted(a["attributes"])]}
                              for a in (atoms[i] for i in sorted(concept_atoms[rxcui]))]
        concepts.append({"id": rxcui, "source": SOURCE, "atoms": concept_atoms_list, "relations": [{"kind": k, "target": t} for k, t in sorted(relations.get(rxcui, ()))]})
    return {"ref": "rxnorm:cpc", "version": version, "concepts": concepts}, dict(stats)


def ledger_entries():
    ledger = {m["id"]: m for m in json.loads(LEDGER.read_text(encoding="utf-8"))["materials"]}
    entries = {}
    for ident in (OLD_ID, NEW_ID):
        material = ledger[ident]
        path = ROOT / material["local_path"]
        if material.get("acquisition_status") != "acquired_file_checks_passed" or not path.is_file():
            raise SystemExit(f"{ident}: 取得状態またはファイルが台帳と合いません")
        if sha256_of(path) != material["local_sha256"]:
            raise SystemExit(f"{ident}: SHA-256 が台帳と一致しません")
        entries[ident] = {"path": path, "version": material["version"], "sha256": material["local_sha256"]}
    return entries


def policies(names):
    """作り手の研究上の仮定（医学的判断ではない）。P-full：NDC は管理上、他の全ては定義にあたる。P-partial：NDC は管理上、強度に関わる名前だけが定義にあたり、他は未宣言。"""
    full = [{"name": n, "class": "administrative" if n == "NDC" else "definitional"} for n in sorted(names)]
    partial = [{"name": "NDC", "class": "administrative"}] + [{"name": n, "class": "definitional"} for n in STRENGTH_ATTRIBUTES if n in names]
    return {"P-full": full, "P-partial": sorted(partial, key=lambda item: item["name"])}


def run_policy(old, new, policy):
    spec = audit._spec()
    old_concepts, new_concepts = {c["id"]: c for c in old["concepts"]}, {c["id"]: c for c in new["concepts"]}
    classes = {item["name"]: item["class"] for item in policy}
    sources = {SOURCE}
    references = sorted(i for i, c in old_concepts.items() if c["source"] in sources)
    rows = [audit.audit_reference(r, old_concepts, new_concepts, sources, classes, spec) for r in references]
    return rows, audit.summarize(rows, old_concepts, new_concepts, sources)


def aggregate(rows):
    """集計だけ（概念の ID・名称・属性値を含まない）。"""
    out = Counter()
    by_name = defaultdict(Counter)
    for row in rows:
        out["state:" + row["audit_state"]] += 1
        facets = row["facets"]
        if not facets:
            continue
        names, relations, attributes = facets["names"], facets["relations"], facets["attributes"]
        out["atoms_added"] += len(names["added"])
        out["atoms_removed"] += len(names["removed"])
        out["atoms_modified"] += len(names["modified"])
        out["refs_names_changed"] += names["state"] == "changed"
        out["refs_relations_changed"] += relations["state"] == "changed"
        out["relations_added"] += len(relations["added"])
        out["relations_removed"] += len(relations["removed"])
        out["relations_removed_target_still_in_to"] += sum(1 for r in relations["removed"] if r["target_in_to"])
        out["relations_added_target_already_in_from"] += sum(1 for r in relations["added"] if r["target_in_from"])
        out["unresolved_in_to_known_in_from"] += sum(1 for u in relations["unresolved_in_to"] if u["in_from"])
        out["unresolved_in_to_unknown_in_from"] += sum(1 for u in relations["unresolved_in_to"] if not u["in_from"])
        entries = attributes["definitional"] + attributes["administrative"] + attributes["undeclared"]
        out["refs_attribute_difference"] += bool(entries)
        out["refs_attribute_difference_not_ndc"] += any(e["name"] != "NDC" for e in entries)
        out["refs_definitional_difference"] += bool(attributes["definitional"])
        out["refs_undeclared_difference"] += bool(attributes["undeclared"])
        out["attributes_added_with_atoms"] += attributes["with_atom_change"]["added"]
        out["attributes_removed_with_atoms"] += attributes["with_atom_change"]["removed"]
        for kind in ("definitional", "administrative", "undeclared"):
            for entry in attributes[kind]:
                by_name[entry["name"]][kind] += 1
    return {"counts": dict(sorted(out.items())), "attribute_differences_by_name": {n: dict(c) for n, c in sorted(by_name.items())}}


def attribute_names(snapshot):
    return {a["name"] for c in snapshot["concepts"] for atom in c["atoms"] for a in atom["attributes"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=ROOT / "data/research/r4/cpc-audit.json")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    entries = ledger_entries()
    old, old_stats = normalize(entries[OLD_ID]["path"], entries[OLD_ID]["version"])
    new, new_stats = normalize(entries[NEW_ID]["path"], entries[NEW_ID]["version"])
    for snapshot, key in ((old, OLD_ID), (new, NEW_ID)):
        snapshot["source_sha256"] = entries[key]["sha256"]
    declared = policies(attribute_names(old) | attribute_names(new))
    report = {"versions": {"from": {"version": old["version"], "sha256": old["source_sha256"]}, "to": {"version": new["version"], "sha256": new["source_sha256"]}},
              "normalization": {"from": old_stats, "to": new_stats}, "policies": {}}
    kept = {}
    for name, policy in declared.items():
        rows, summary = run_policy(old, new, policy)
        report["policies"][name] = {"declared": len(policy), "summary": summary, **aggregate(rows)}
        kept[name] = [r for r in rows if r["audit_state"] != "unchanged_in_scope"]
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if not args.no_write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({**report, "differences": kept}, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
