#!/usr/bin/env python3
"""P2-u 追補（設計85）：CPC の旧版にあり新版にない参照（P2-u の監査で `not_found`）の状態を、RxNorm API（RxNav）の `historystatus` で照会する。

照会の対象は、台帳のハッシュを確かめた CPC の二版から作り直した、その参照だけ（P-full の監査の `not_found`）。1秒に5要求以下（上限20の4分の1）で逐次に照会し、
照会の前後に API が返すデータの版を取る。応答の生データは Git 管理外の data/research/r4/rxnorm-history/ に保存し、標準出力には集計だけを出す。
通信するのは `fetch` だけで、応答の読み取り（parse_*）と集計（summarize）は通信を使わず、架空の応答でテストする。"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
API = "https://rxnav.nlm.nih.gov/REST"
MAX_PER_SECOND = 5                                    # 上限は1つの IP から1秒に20要求。その4分の1
USER_AGENT = "med-dsl-research/0.1 (private research; read-only; contact via repository owner)"
STATUSES = ("Active", "Obsolete", "Remapped", "Quantified", "NotCurrent", "Unknown")
DISPENSABLE = ("SCD", "SBD", "GPCK", "BPCK")          # RXNCUI が退役を追跡する用語種別（技術文書の記述）
OUTPUT = ROOT / "data/research/r4/rxnorm-history"


def load_audit_tool():
    spec = importlib.util.spec_from_file_location("audit_cpc_versions", ROOT / "scripts/research/audit-cpc-versions.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_cpc_versions"] = module
    spec.loader.exec_module(module)
    return module


def fetch(url, opener=urllib.request.urlopen, attempts=3, pause=1.0, sleep=time.sleep):
    """一つの URL を取得する。通信の失敗は attempts 回まで再試行し、最後の失敗はその内容を返す。戻り値：(HTTP の状態コード|None, 本文のバイト列|None, 失敗の理由|None)。"""
    reason = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with opener(request, timeout=60) as response:
                return response.status, response.read(), None
        except urllib.error.HTTPError as error:
            reason = f"http_{error.code}"
            if error.code < 500:                    # 4xx は再試行しない
                return error.code, None, reason
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            reason = type(error).__name__
        if attempt + 1 < attempts:
            sleep(pause * (attempt + 1))
    return None, None, reason


def parse_version(raw):
    document = json.loads(raw)
    return {"version": document.get("version"), "apiVersion": document.get("apiVersion")}


def parse_history(raw):
    """historystatus の応答（JSON）から、状態・用語種別・期間・置換先を読む。想定した形でなければ shape_error。名称は読まない。"""
    document = json.loads(raw)
    history = document.get("rxcuiStatusHistory") if isinstance(document, dict) else None
    meta = history.get("metaData") if isinstance(history, dict) else None
    if not isinstance(meta, dict) or "status" not in meta:
        return {"status": None, "shape_error": True}
    attributes = history.get("attributes") or {}
    derived = history.get("derivedConcepts") or {}
    remapped = derived.get("remappedConcept") or []
    return {"status": meta.get("status"), "tty": attributes.get("tty"), "is_current": meta.get("isCurrent"),
            "release_start": meta.get("releaseStartDate"), "release_end": meta.get("releaseEndDate"),
            "active_start": meta.get("activeStartDate"), "active_end": meta.get("activeEndDate"), "remapped_date": meta.get("remappedDate"),
            "remapped": [{"rxcui": item.get("remappedRxCui"), "tty": item.get("remappedTTY"), "active": item.get("remappedActive")} for item in remapped if isinstance(item, dict)],
            "quantified": len(derived.get("quantifiedConcept") or []), "shape_error": False}


def query(references, opener=urllib.request.urlopen, sleep=time.sleep, clock=time.time):
    """参照を一つずつ（1秒に MAX_PER_SECOND 要求以下で）照会し、応答の記録を返す。"""
    records, interval = [], 1.0 / MAX_PER_SECOND
    for reference in references:
        started = clock()
        url = f"{API}/rxcui/{reference}/historystatus.json"
        code, body, reason = fetch(url, opener, sleep=sleep)
        record = {"rxcui": reference, "url": url, "http_status": code, "failure": reason, "sha256": hashlib.sha256(body).hexdigest() if body else None, "bytes": len(body) if body else 0}
        if body:
            try:
                record["parsed"] = parse_history(body)
            except (ValueError, AttributeError) as error:
                record["parsed"] = {"status": None, "shape_error": True}
                record["failure"] = "unreadable:" + type(error).__name__
        else:
            record["parsed"] = None
        record["_body"] = body
        records.append(record)
        wait = interval - (clock() - started)
        if wait > 0:
            sleep(wait)
    return records


def summarize(records, tty_of, new_ids):
    """集計だけ（名称・応答を含まない）。tty_of：参照→旧版の用語種別の集合。new_ids：新版の CPC の概念 id。"""
    counts, groups, remap, ends, obsolete_since, current = Counter(), {"dispensable": Counter(), "other": Counter()}, Counter(), Counter(), Counter(), Counter()
    for record in records:
        parsed = record["parsed"]
        if not parsed or parsed.get("shape_error"):
            counts["unreadable_or_failed"] += 1
            continue
        status = parsed["status"]
        counts[status] += 1
        group = "dispensable" if set(tty_of.get(record["rxcui"], ())) & set(DISPENSABLE) else "other"
        groups[group][status] += 1
        current[(status, parsed.get("is_current"))] += 1
        if status in ("Remapped", "NotCurrent"):
            ends[parsed.get("release_end") or "none"] += 1
        if status == "Obsolete":
            obsolete_since[parsed.get("active_end") or "none"] += 1
        if status == "Remapped":
            targets = [item["rxcui"] for item in parsed["remapped"] if item.get("rxcui")]
            remap["remapped"] += 1
            remap["with_target"] += bool(targets)
            remap["target_in_new_cpc"] += any(t in new_ids for t in targets)
            remap["target_active"] += any(item.get("active") == "YES" for item in parsed["remapped"])
            remap["multiple_targets"] += len(targets) > 1
    return {"references": len(records), "status": dict(sorted(counts.items())), "by_group": {k: dict(sorted(v.items())) for k, v in groups.items()},
            "remapped": dict(sorted(remap.items())), "release_end_of_remapped_or_notcurrent": dict(sorted(ends.items())),
            "active_end_of_obsolete": dict(sorted(obsolete_since.items())), "is_current_by_status": {f"{k[0]}:{k[1]}": v for k, v in sorted(current.items(), key=str)}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--probe", type=int, default=0, help="先頭の N 参照だけを照会して形を見る（保存はする）")
    parser.add_argument("--no-query", action="store_true", help="参照の一覧だけを作る（通信しない）")
    parser.add_argument("--from-saved", action="store_true", help="保存した応答から集計し直す（通信しない）")
    args = parser.parse_args(argv)
    tool = load_audit_tool()
    entries = tool.ledger_entries()
    old, _ = tool.normalize(entries[tool.OLD_ID]["path"], entries[tool.OLD_ID]["version"])
    new, _ = tool.normalize(entries[tool.NEW_ID]["path"], entries[tool.NEW_ID]["version"])
    declared = tool.policies(tool.attribute_names(old) | tool.attribute_names(new))["P-full"]
    rows, _ = tool.run_policy(old, new, declared)
    references = sorted(r["reference"] for r in rows if r["audit_state"] == "not_found")
    tty_of = {c["id"]: {a["kind"] for a in c["atoms"]} for c in old["concepts"] if c["id"] in set(references)}
    new_ids = {c["id"] for c in new["concepts"]}
    print(json.dumps({"references": len(references), "dispensable": sum(1 for r in references if tty_of[r] & set(DISPENSABLE))}))
    if args.no_query:
        return 0
    if args.from_saved:
        manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
        records = [{"rxcui": r["rxcui"], "parsed": parse_history((OUTPUT / f"{r['rxcui']}.json").read_bytes()) if (OUTPUT / f"{r['rxcui']}.json").is_file() else None} for r in manifest["records"]]
        print(json.dumps({"saved": len(records), "versions": manifest["versions"], **summarize(records, tty_of, new_ids)}, ensure_ascii=False, indent=1))
        return 0
    chosen = references[:args.probe] if args.probe else references
    OUTPUT.mkdir(parents=True, exist_ok=True)
    versions = {}
    code, body, reason = fetch(API + "/version.json")
    if not body:
        raise SystemExit(f"API の版を取得できません：{code} {reason}")
    versions["before"] = parse_version(body)
    started = time.time()
    records = query(chosen)
    elapsed = time.time() - started
    code, body, reason = fetch(API + "/version.json")
    versions["after"] = parse_version(body) if body else None
    for record in records:
        if record["_body"]:
            (OUTPUT / f"{record['rxcui']}.json").write_bytes(record["_body"])
    manifest = {"queried_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)), "elapsed_seconds": round(elapsed, 1), "max_per_second": MAX_PER_SECOND,
                "versions": versions, "records": [{k: v for k, v in r.items() if k != "_body"} for r in records]}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    report = {"queried": len(records), "elapsed_seconds": round(elapsed, 1), "versions": versions,
              "http": dict(Counter(str(r["http_status"]) for r in records)), "failures": sum(1 for r in records if r["failure"]), **summarize(records, tty_of, new_ids)}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
