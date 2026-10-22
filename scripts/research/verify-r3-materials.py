#!/usr/bin/env python3
"""Inspect the four selected R3 files without extracting or executing their contents."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/research/03-materials.json"
RRF_LAYOUTS = {"RXNCONSO.RRF": (18, 11), "RXNSAT.RRF": (13, 9), "RXNREL.RRF": (16, 10)}
ALLOWED_SOURCES = {"RXNORM", "MTHSPL", "MTHCMSFRF"}


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title_seen = False
        self.title = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag == "title" and not self.title_seen:
            self.in_title = True
            self.title_seen = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        self.text.append(data)
        if self.in_title:
            self.title.append(data)


# 資料の種類ごとの、ページ名と、版ごとに必ず現れるべき項目（版の取り違えを検出するための目印）
HTML_RESOURCES = {
    "Procedure": {"4.0.1": "performed[x]", "5.0.0": "occurrence[x]"},
    "Observation": {"5.0.0": "dataAbsentReason"},
    "Specimen": {"5.0.0": "accessionIdentifier"},
    "Datatypes": {"5.0.0": "comparator"},
    "Codesystem-observation-status": {"5.0.0": "entered-in-error"},
    "Codesystem-provenance-entity-role": {"5.0.0": "instantiates"},
    "Valueset-data-absent-reason": {"5.0.0": "not-asked"},
    "Provenance": {"5.0.0": "onBehalfOf"},
    "Extensibility": {"5.0.0": "modifierExtension"},
}
# NLM の RxNorm 文書（HTML）：ページ名と、目印の語（版は取得日で、ページ自体は版を持たない）
NLM_PAGES = {
    "NLM-RxNorm-techdoc": ("RxNorm Technical Documentation", "HAS TO the FIRST concept or atom"),
    "NLM-RxNorm-prescribe": ("RxNorm Current Prescribable Content", "approximation of the prescription drugs currently marketed in the US"),
    "NLM-RxNorm-appendix-1": ("Appendix 1 - RxNorm Relationships (RELA)", "has_ingredient"),
    # 利用条件の根拠のページ
    "NLM-RxNorm-terms": ("RxNorm Terms of Service", "A free UMLS License is required to download the full RxNorm releases"),
    "NLM-RxNorm-files": ("RxNorm Files", "(no license required)"),
    "NLM-UMLS-license": ("How to License and Access the Unified Medical Language System® (UMLS®) Data", "UMLS licenses are issued only to individuals"),
    "NLM-RxNav-terms": ("Terms of Service", "With one exception, no license is needed to use these APIs"),
    "NLM-RxNorm-API": ("RxNorm API - APIs", "getRxcuiHistoryStatus"),
    "NLM-RxNorm-API-historystatus": ("getRxcuiHistoryStatus - RxNorm API", "Concept status values"),
    "NLM-RxNorm-API-version": ("getRxNormVersion - RxNorm API", "Get the version of the RxNorm data set"),
}


def check_html(path, material):
    page = PageText()
    page.feed(path.read_text(encoding="utf-8-sig"))
    title = " ".join("".join(page.title).split())
    text = " ".join(page.text)
    resource = material.get("resource", "Procedure")
    field = HTML_RESOURCES[resource][material["version"]]
    version = re.search(r"FHIR v([0-9.]+)", title)
    if not re.search(rf"\b{resource}\b", title) or not version or version.group(1) != material["version"]:
        raise ValueError(f"{resource} のページ名・版が一致しません")
    if field not in text:
        raise ValueError(f"目印の項目 {field} を確認できません")
    return {"kind": "html_identity", "title": title, "time_field" if resource == "Procedure" else "marker_field": field}


def check_nlm_html(path, material):
    page = PageText()
    page.feed(path.read_text(encoding="utf-8-sig"))
    title = " ".join("".join(page.title).split())
    text = " ".join(" ".join(page.text).split())
    expected_title, marker = NLM_PAGES[material["resource"]]
    if title != expected_title:
        raise ValueError(f"ページ名が一致しません：{title}")
    if marker not in text:
        raise ValueError(f"目印の語 {marker} を確認できません")
    return {"kind": "html_identity", "title": title, "marker_field": marker}


def check_zip(path, material):
    with zipfile.ZipFile(path) as archive:
        broken = archive.testzip()
        if broken:
            raise ValueError("ZIP 内の CRC 検査に失敗しました")
        members = [m for m in archive.infolist() if not m.is_dir()]
        rrf = [m for m in members if m.filename.upper().endswith(".RRF")]
        names = [PurePosixPath(m.filename).name.upper() for m in rrf]
        if sorted(names) != sorted(RRF_LAYOUTS):
            raise ValueError("CPC の三つの RRF ファイルと一致しません。全体版等でないか確認してください")
        readmes = [m for m in members if "readme" in PurePosixPath(m.filename).name.lower()]
        if not readmes:
            raise ValueError("README が見つかりません")
        release = datetime.strptime(material["version"], "%Y-%m-%d")
        dates = [release.strftime(fmt).lower() for fmt in ("%Y-%m-%d", "%m%d%Y", "%m/%d/%Y", "%B %d, %Y")]
        dates.append(f"{release.strftime('%B').lower()} {release.day}, {release.year}")
        readme_text = "\n".join(archive.read(m).decode("utf-8-sig").lower() for m in readmes)
        normalized = " ".join(readme_text.split())
        release_marker = any(date in normalized for date in dates)
        if not release_marker:
            raise ValueError("README で選定したリリース日を確認できません")
        stats = {}
        for member, name in zip(rrf, names):
            width, source_column = RRF_LAYOUTS[name]
            sources = Counter()
            rows = 0
            with archive.open(member) as stream:
                for rows, raw in enumerate(stream, 1):
                    fields = raw.decode("utf-8-sig").rstrip("\r\n").split("|")
                    if len(fields) != width + 1 or fields[-1] != "":
                        raise ValueError(f"{name} の {rows} 行目の列数・終端区切りが不正です")
                    sources[fields[source_column]] += 1
            if not rows:
                raise ValueError(f"{name} が空です")
            if set(sources) - ALLOWED_SOURCES:
                raise ValueError(f"{name} に選定範囲外の出典があります。条件と収録内容を再確認してください")
            stats[name] = {"rows": rows, "columns": width, "sources": dict(sorted(sources.items()))}
        return {
            "kind": "cpc_archive_structure",
            "crc_passed": True,
            "members": [m.filename for m in members],
            "readme_files": [m.filename for m in readmes],
            "release_marker_found": release_marker,
            "rrf": stats,
        }


def inspect(material, directory, observed_at):
    filename = material.get("local_filename")
    if not filename or Path(filename).name != filename:
        raise ValueError("台帳の local_filename が不正です")
    path = directory / filename
    result = {"id": material["id"], "filename": filename, "observed_at": observed_at}
    if not path.is_file():
        return {**result, "status": "missing", "error": "ファイルがありません"}
    try:
        sha256, md5 = hashlib.sha256(), hashlib.md5(usedforsecurity=False)
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                sha256.update(block)
                md5.update(block)
        result.update(bytes=path.stat().st_size, sha256=sha256.hexdigest(), md5=md5.hexdigest())
        expected = material.get("publisher_md5")
        result["publisher_md5_status"] = "matched" if expected else "not_available"
        if expected and result["md5"] != expected:
            result["publisher_md5_status"] = "mismatched"
            raise ValueError("公表 MD5 と一致しません。期待値を変更せず、取得物を確認してください")
        check = check_zip if filename.endswith(".zip") else check_nlm_html if material.get("resource", "").startswith("NLM-") else check_html
        result["inspection"] = check(path, material)
        previous = material.get("local_sha256")
        result["previous_local_sha256_status"] = (
            "matched" if previous == result["sha256"] else "changed" if previous else "not_available"
        )
        if previous and previous != result["sha256"]:
            raise ValueError("記録済みのローカル SHA-256 から変わっています。台帳を上書きせず確認してください")
        result["status"] = "file_checks_passed"
    except (OSError, UnicodeError, ValueError, zipfile.BadZipFile, RuntimeError, zlib.error) as error:
        result.update(status="failed", error=str(error))
    return result


def main():
    parser = argparse.ArgumentParser(description="R3 の実ファイルのハッシュ・版・初期構造を検査します")
    parser.add_argument("--record", action="store_true", help="合格したファイルの取得台帳を更新する")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    directory = ROOT / "data/research/r3"
    directory.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    results = []
    for material in manifest["materials"]:
        result = inspect(material, directory, now)
        results.append(result)
        print(f"{material['id']}: {result['status']}" + (f" — {result['error']}" if "error" in result else ""))
        if args.record:
            material.update(last_check_status=result["status"], last_checked_at=now)
        if args.record and result["status"] == "file_checks_passed":
            receipt_path = directory / f"{material['id']}.receipt.json"
            try:
                receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
            except (OSError, json.JSONDecodeError):
                receipt = {}
            matched_receipt = receipt.get("sha256") == result["sha256"]
            material.update(
                acquisition_status="acquired_file_checks_passed",
                access_observation="実ファイルのハッシュと初期構造を検査。意味対応の検証は未実施。",
                local_sha256=result["sha256"],
                local_md5=result["md5"],
                local_bytes=result["bytes"],
                local_path=str((directory / material["local_filename"]).relative_to(ROOT)),
                retrieved_at=receipt.get("retrieved_at") if matched_receipt else None,
                final_url=receipt.get("final_url") if matched_receipt else None,
                response_content_type=receipt.get("content_type") if matched_receipt else None,
                verified_at=now,
                publisher_md5_status=result["publisher_md5_status"],
                initial_file_checks_passed=True,
                content_verified=False,
                inspection=result["inspection"],
            )
    report = {"checked_at": now, "scope": "ファイルの初期検査。意味・医学的妥当性の検証は含まない。", "materials": results}
    (directory / "verification-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if args.record:
        pending = MANIFEST.with_suffix(".json.tmp")
        pending.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        pending.replace(MANIFEST)
    print("検査記録: data/research/r3/verification-report.json")
    return int(any(result["status"] != "file_checks_passed" for result in results))


if __name__ == "__main__":
    sys.exit(main())
