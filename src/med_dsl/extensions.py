"""拡張契約の宣言（p2-extension-manifest-draft-1）の検査・登録・再検証範囲の列挙。

宣言の書式、hash と実体の一致、所有の素性、クラス別の義務と防護例の対応、依存の閉包を機械的に検査する。
**意味の正しさは検査しない。** 宣言は拡張の作者が書く主張で、ここで確かめるのは、宣言が欠けていないこと・
実体と食い違わないこと・防護例が実際に宣言どおりの結果を返すことである。
"""

import ast
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from pathlib import Path

from .validation import canonical_bytes, decode_json

MANIFEST_SCHEMA = "p2-extension-manifest-draft-1"
CLASSES = ("BASE", "HOST", "R1", "R2", "R3", "R4", "R5", "R6", "COMP", "JOINT")
# 弱い順。拡張全体の強さは、最も弱い義務の強さ
EVIDENCE = ("self_declared", "individual_io", "finite_check", "hand_derivation", "checked_native_template")
COMMON = ("K-ID", "K-STOP", "K-INV", "K-RES")
REQUIRED = {
    "BASE": COMMON,
    "HOST": COMMON,
    "R1": COMMON + tuple(f"R1-{i}" for i in range(1, 6)),
    "R2": COMMON + tuple(f"R2-{i}" for i in range(1, 6)),
    "R3": COMMON + tuple(f"R3-{i}" for i in range(1, 8)),
    "R4": COMMON + tuple(f"R4-{i}" for i in range(1, 4)),
    "R5": COMMON + tuple(f"R5-{i}" for i in range(1, 4)),
    # R6 公理つき読み取りモジュール：R2 の義務に、公理の宣言・旧データでの無矛盾・結論の健全性と公理への相対・範囲・情報要求を加える
    "R6": COMMON + tuple(f"R2-{i}" for i in range(1, 6)) + tuple(f"R6-{i}" for i in range(1, 7)),
    # JOINT 併用（記号を共有し得る拡張の合成）：R6 の義務に、構造の再計算・独立な併用の分解・共有記号の併用の全体での再判定・鎖・範囲・差の開示を加える
    "JOINT": COMMON + tuple(f"R2-{i}" for i in range(1, 6)) + tuple(f"R6-{i}" for i in range(1, 7)) + tuple(f"JOINT-{i}" for i in range(1, 7)),
    "COMP": COMMON + tuple(f"COMP-{i}" for i in range(1, 4)),
}
OWN_KINDS = ("operations", "schema_versions", "profiles", "answer_kinds", "predicates", "capabilities")
TOP_LEVEL = ("schema_version", "id", "version", "title", "status", "class", "spec", "contract_doc", "implementation", "pins",
             "embedded_in", "depends_on", "owns", "scope", "obligations", "stops", "composition", "evaluation")
STOP_KEYS = ("unknown_capability", "unsupported", "resource", "invalid_input")
COMPOSITION_KEYS = ("shares_names_with", "reads_extensions", "order_dependent")
EVALUATION_KEYS = ("examples", "tests", "budget_sweep", "oracle")
GUARD_KINDS = ("refusal", "non_conversion", "boundary")
LOCK = "examples/p1-evaluation/manifest.json"


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    detail: str = ""


class Refused(Exception):
    """宣言の拒否。登録は一切行われない（部分適用をしない）。"""

    def __init__(self, findings):
        super().__init__("; ".join(f"{f.code}@{f.path}" for f in findings))
        self.findings = tuple(findings)

    @property
    def codes(self):
        return sorted({f.code for f in self.findings})


def overlaps(a, b):
    """名前の重なり。末尾が ":" の名前は名前空間（接頭辞）で、その下の名前すべてを所有する。"""
    return a == b or (a.endswith(":") and b.startswith(a)) or (b.endswith(":") and a.startswith(b))


def _is_text(value):
    return type(value) is str and bool(value) and value == value.strip()


def _text_list(value):
    return type(value) is list and all(_is_text(v) for v in value) and len(set(value)) == len(value)


def check_structure(manifest):
    """ファイルを読まない書式の検査。"""
    found = []
    if type(manifest) is not dict:
        return [Finding("expected_object", "$")]
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        found.append(Finding("unsupported_manifest_schema", "schema_version", str(manifest.get("schema_version"))))
    for key in TOP_LEVEL:
        if key not in manifest:
            found.append(Finding("missing_field", key))
    for key in manifest:
        if key not in TOP_LEVEL:
            found.append(Finding("unknown_field", key))
    if found:
        return found
    for key in ("id", "version", "title", "contract_doc"):
        if not _is_text(manifest[key]):
            found.append(Finding("expected_nonempty_string", key))
    if manifest["class"] not in CLASSES:
        found.append(Finding("unknown_class", "class", str(manifest["class"])))
    status = manifest["status"]
    if type(status) is not dict or set(status) != {"review_state", "independent_review"} or type(status["independent_review"]) is not bool \
            or not _is_text(status.get("review_state")):
        found.append(Finding("invalid_status", "status"))
    elif status["independent_review"]:
        found.append(Finding("independent_review_claim_without_record", "status.independent_review"))
    spec = manifest["spec"]
    if spec is not None and not (type(spec) is dict and set(spec) == {"path", "sha256"} and _is_text(spec["path"])
                                 and type(spec["sha256"]) is str and len(spec["sha256"]) == 64):
        found.append(Finding("invalid_spec", "spec"))
    implementation = manifest["implementation"]
    if type(implementation) is not dict or set(implementation) != {"modules"} or not _text_list(implementation["modules"]) \
            or not implementation["modules"]:
        found.append(Finding("invalid_implementation", "implementation"))
    for key in ("pins", "depends_on"):
        if type(manifest[key]) is not list:
            found.append(Finding("expected_array", key))
    if type(manifest["pins"]) is list and not all(type(p) is dict and set(p) == {"path", "role"} and _is_text(p["path"]) and _is_text(p["role"])
                                                  for p in manifest["pins"]):
        found.append(Finding("invalid_pin", "pins"))
    if not _text_list(manifest["embedded_in"]):
        found.append(Finding("invalid_embedded_in", "embedded_in"))
    if type(manifest["depends_on"]) is list and not all(type(d) is dict and set(d) == {"id", "version"} and _is_text(d["id"]) and _is_text(d["version"])
                                                        for d in manifest["depends_on"]):
        found.append(Finding("invalid_dependency", "depends_on"))
    owns = manifest["owns"]
    if type(owns) is not dict or set(owns) != set(OWN_KINDS) or not all(_text_list(owns[k]) for k in OWN_KINDS):
        found.append(Finding("invalid_owns", "owns"))
    if type(manifest["scope"]) is not dict or not manifest["scope"]:
        found.append(Finding("invalid_scope", "scope"))
    stops = manifest["stops"]
    if type(stops) is not dict or set(stops) != set(STOP_KEYS) or not all(_is_text(v) for v in stops.values()):
        found.append(Finding("invalid_stops", "stops"))
    composition = manifest["composition"]
    if type(composition) is not dict or set(composition) != set(COMPOSITION_KEYS) or not _text_list(composition["shares_names_with"]) \
            or not _text_list(composition["reads_extensions"]) or type(composition["order_dependent"]) is not bool:
        found.append(Finding("invalid_composition", "composition"))
    evaluation = manifest["evaluation"]
    if type(evaluation) is not dict or set(evaluation) != set(EVALUATION_KEYS) or not _text_list(evaluation["examples"]) \
            or not _text_list(evaluation["tests"]) or type(evaluation["budget_sweep"]) is not bool or not _is_text(evaluation["oracle"]):
        found.append(Finding("invalid_evaluation", "evaluation"))
    found += _check_obligations(manifest)
    return found


def _check_obligations(manifest):
    found = []
    items = manifest["obligations"]
    if type(items) is not list:
        return [Finding("expected_array", "obligations")]
    seen = set()
    for i, item in enumerate(items):
        where = f"obligations[{i}]"
        if type(item) is not dict or not {"id", "statement", "evidence", "checks", "guards"} <= set(item) \
                or not set(item) <= {"id", "statement", "evidence", "checks", "guards", "guard_gap", "derivation"}:
            found.append(Finding("invalid_obligation", where))
            continue
        if not _is_text(item["id"]) or item["id"] in seen:
            found.append(Finding("invalid_or_duplicate_obligation_id", where, str(item.get("id"))))
        seen.add(item["id"])
        if not _is_text(item["statement"]):
            found.append(Finding("expected_nonempty_string", where + ".statement"))
        if item["evidence"] not in EVIDENCE:
            found.append(Finding("unknown_evidence", where + ".evidence", str(item["evidence"])))
        if not _text_list(item["checks"]):
            found.append(Finding("invalid_checks", where + ".checks"))
        if "derivation" in item and not _is_text(item["derivation"]):
            found.append(Finding("invalid_derivation", where + ".derivation"))
        guards = item["guards"]
        if type(guards) is not list or not all(type(g) is dict and set(g) == {"example", "path", "equals", "kind"} and _is_text(g["example"])
                                               and type(g["path"]) is list and g["path"] and g["kind"] in GUARD_KINDS for g in guards):
            found.append(Finding("invalid_guards", where + ".guards"))
        elif not guards and not _is_text(item.get("guard_gap")):
            # 防護例がない義務は、理由を宣言する（検査の見逃しが宣言から見える）
            found.append(Finding("unexplained_guard_gap", where, str(item["id"])))
        elif guards and "guard_gap" in item:
            found.append(Finding("guard_gap_with_guards", where, str(item["id"])))
        elif "guard_gap" in item and not _is_text(item["guard_gap"]):
            found.append(Finding("invalid_guard_gap", where))
    required = REQUIRED.get(manifest["class"], ())
    for need in required:
        if need not in seen:
            found.append(Finding("missing_obligation", "obligations", need))
    for extra in sorted(seen - set(required)):
        if extra[:2] in ("K-", "R1", "R2", "R3", "R4", "R5", "R6") or extra.startswith(("COMP-", "JOINT-")):
            found.append(Finding("obligation_of_another_class", "obligations", extra))
    return found


def weakest_evidence(manifest):
    return min((o["evidence"] for o in manifest["obligations"]), key=EVIDENCE.index)


def guard_gaps(manifest):
    return sorted(o["id"] for o in manifest["obligations"] if o.get("guard_gap"))


def _read(root, relative):
    return (Path(root) / relative).read_bytes()


def check_files(manifest, root):
    """宣言と実体の一致：仕様の hash、実装・防護例・検査の所在、宣言した名前が実装に現れること。"""
    found = []
    root = Path(root)

    def exists(relative, code, where):
        path = root / relative
        if ".." in Path(relative).parts or not path.is_file():
            found.append(Finding(code, where, relative))
            return False
        return True

    texts = []
    spec = manifest["spec"]
    if spec is not None and exists(spec["path"], "missing_spec", "spec.path"):
        raw = _read(root, spec["path"])
        if hashlib.sha256(raw).hexdigest() != spec["sha256"]:
            found.append(Finding("spec_hash_mismatch", "spec.sha256", spec["path"]))
        texts.append(raw.decode("utf-8", "replace"))
    exists(manifest["contract_doc"], "missing_contract_doc", "contract_doc")
    for module in manifest["implementation"]["modules"]:
        if not module.startswith("src/med_dsl/") or not module.endswith(".py"):
            found.append(Finding("implementation_outside_package", "implementation.modules", module))
        elif exists(module, "missing_module", "implementation.modules"):
            texts.append(_read(root, module).decode("utf-8", "replace"))
    for pin in manifest["pins"]:
        exists(pin["path"], "missing_pin", "pins")
    text = "\n".join(texts)
    for kind in OWN_KINDS:
        for token in manifest["owns"][kind]:
            if token not in text:
                found.append(Finding("owned_name_not_found", f"owns.{kind}", token))
    for i, item in enumerate(manifest["obligations"]):
        for check in item["checks"]:
            target, _, name = check.partition("::")
            if exists(target, "missing_check_file", f"obligations[{i}].checks") and name:
                body = _read(root, target).decode("utf-8", "replace")
                if f"def {name.rsplit('.', 1)[-1]}(" not in body and f"class {name}" not in body:
                    found.append(Finding("missing_check_name", f"obligations[{i}].checks", check))
        for guard in item["guards"]:
            exists(guard["example"], "missing_guard_example", f"obligations[{i}].guards")
    for pattern in manifest["evaluation"]["examples"]:
        if not any(root.glob(pattern)):
            found.append(Finding("evaluation_examples_not_found", "evaluation.examples", pattern))
    for test in manifest["evaluation"]["tests"]:
        exists(test, "missing_test_file", "evaluation.tests")
    return found


def check_guards(manifest, root, evaluate):
    """防護例を実際に評価し、宣言した結果が得られることを確かめる（宣言を信用しない）。"""
    found = []
    for i, item in enumerate(manifest["obligations"]):
        for guard in item["guards"]:
            path = Path(root) / guard["example"]
            if not path.is_file():
                continue
            request = decode_json(path.read_bytes())["request"]
            actual, ok = evaluate(deepcopy(request)), True
            for key in guard["path"]:
                if (type(actual) is dict and type(key) is str and key in actual) or (type(actual) is list and type(key) is int and 0 <= key < len(actual)):
                    actual = actual[key]
                else:
                    ok = False
                    break
            if not ok or canonical_bytes(actual) != canonical_bytes(guard["equals"]):
                found.append(Finding("guard_outcome_mismatch", f"obligations[{i}].guards", f"{item['id']} {guard['example']}"))
    return found


def validate(manifest, root, evaluate=None):
    found = check_structure(manifest)
    if found:
        return found
    found = check_files(manifest, root)
    if evaluate is not None:
        found += check_guards(manifest, root, evaluate)
    return found


class Registry:
    """登録済みの拡張。登録は全か無か：拒否されたら状態は変わらない。"""

    def __init__(self, root, evaluate=None):
        self.root = Path(root)
        self.evaluate = evaluate
        self._items = {}

    def __iter__(self):
        return iter(self._items.values())

    def __contains__(self, ident):
        return ident in self._items

    def get(self, ident):
        return self._items[ident]

    def register(self, manifest):
        found = validate(manifest, self.root, self.evaluate)
        if not found:
            found = self._check_registry_rules(manifest)
        if found:
            raise Refused(found)
        self._items[manifest["id"]] = deepcopy(manifest)

    def _check_registry_rules(self, manifest):
        found = []
        if manifest["id"] in self._items:
            found.append(Finding("duplicate_extension", "id", manifest["id"]))
        for dep in manifest["depends_on"]:
            registered = self._items.get(dep["id"])
            if registered is None or registered["version"] != dep["version"]:
                found.append(Finding("unresolved_dependency", "depends_on", f"{dep['id']}@{dep['version']}"))
        if manifest["class"] == "BASE":
            if self._items:
                found.append(Finding("base_must_be_first", "class"))
            if manifest["depends_on"]:
                found.append(Finding("base_has_no_dependency", "depends_on"))
        elif not any(m["class"] == "BASE" for m in self._items.values()):
            found.append(Finding("base_not_registered", "depends_on"))
        else:
            found += [Finding("must_depend_on_base", "depends_on")] if not self._reaches_base(manifest) else []
        for other in self._items.values():
            for kind in OWN_KINDS:
                for token in manifest["owns"][kind]:
                    for held in other["owns"][kind]:
                        if overlaps(token, held):
                            found.append(Finding("owner_conflict", f"owns.{kind}", f"{token} (owned by {other['id']}: {held})"))
        composition = manifest["composition"]
        if composition["shares_names_with"]:
            # 記号を共有する併用は、個別の宣言では認めない（併用全体で再判定する）
            found.append(Finding("shared_names_need_joint_check", "composition.shares_names_with"))
        declared = {d["id"] for d in manifest["depends_on"]}
        for name in composition["reads_extensions"]:
            if name not in declared:
                found.append(Finding("undeclared_read", "composition.reads_extensions", name))
        return found

    def _reaches_base(self, manifest):
        stack, seen = [d["id"] for d in manifest["depends_on"]], set()
        while stack:
            ident = stack.pop()
            if ident in seen or ident not in self._items:
                continue
            seen.add(ident)
            if self._items[ident]["class"] == "BASE":
                return True
            stack.extend(d["id"] for d in self._items[ident]["depends_on"])
        return False

    def owners(self):
        """(種別, 名前) -> 拡張 ID。名前空間（末尾が ":"）はその接頭辞のまま。"""
        return {(kind, token): m["id"] for m in self._items.values() for kind in OWN_KINDS for token in m["owns"][kind]}


def load_manifests(directory):
    """directory の *.json（index を除く）を、依存の順に並べて返す。"""
    manifests = [decode_json(p.read_bytes()) for p in sorted(Path(directory).glob("*.json")) if p.name != "index.json"]
    ordered, placed = [], set()
    pending = list(manifests)
    while pending:
        progressed = False
        for manifest in list(pending):
            deps = manifest.get("depends_on", []) if type(manifest) is dict else []
            if all(type(d) is dict and d.get("id") in placed for d in deps):
                ordered.append(manifest)
                placed.add(manifest.get("id") if type(manifest) is dict else None)
                pending.remove(manifest)
                progressed = True
        if not progressed:
            ordered.extend(pending)          # 解決できないものは、登録時に unresolved_dependency として拒否される
            break
    return ordered


def standard_registry(root, directory="extensions", evaluate=None):
    registry = Registry(root, evaluate)
    for manifest in load_manifests(Path(root) / directory):
        registry.register(manifest)
    return registry


def module_graph(root):
    """src/med_dsl の相対 import による依存辺（モジュール名 -> 読み込むモジュール名の集合）。"""
    package = Path(root) / "src/med_dsl"
    names = {p.stem for p in package.glob("*.py")}
    graph = {}
    for path in sorted(package.glob("*.py")):
        edges = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                if node.module:
                    edges.add(node.module.split(".")[0])
                else:
                    edges.update(alias.name for alias in node.names)
        graph[path.stem] = {e for e in edges if e in names and e != path.stem}
    return graph


def _closure(graph, start, skip=()):
    """start から import を辿って届くモジュール。skip に含まれるモジュールへの辺は辿らない（start は常に含む）。"""
    seen, stack = set(), list(start)
    while stack:
        name = stack.pop()
        if name in seen or name not in graph:
            continue
        seen.add(name)
        stack.extend(e for e in graph[name] if e not in skip)
    return seen


def _dependents(registry):
    """拡張 ID -> それに（推移的に）依存する拡張 ID の集合。"""
    direct = {ext["id"]: {d["id"] for d in ext["depends_on"]} for ext in registry}
    found = {ident: set() for ident in direct}
    grew = True
    while grew:
        grew = False
        for ident, deps in direct.items():
            for dep in deps:
                new = {ident} | found[ident]
                if dep in found and not new <= found[dep]:
                    found[dep] |= new
                    grew = True
    return found


def independent_pairs(registry, root=None):
    """L3：基底を除く拡張の組のうち、独立と機械的に判定できるもの（id を整列した組の整列した列）。

    独立：どちらも他方に（推移的に）依存せず、他方を読む宣言がなく、順序に依存せず、実装の import の閉包が他方の
    固有のモジュール（基底が宣言した核のモジュールを除く）を含まない。所有する名前の素性は登録時に検査済み。"""
    root = Path(root if root is not None else registry.root)
    graph = module_graph(root)
    items = {ext["id"]: ext for ext in registry}
    kernel = {Path(m).stem for ext in items.values() if ext["class"] == "BASE" for m in ext["implementation"]["modules"]}
    own = {i: {Path(m).stem for m in ext["implementation"]["modules"]} - kernel for i, ext in items.items() if ext["class"] != "BASE"}
    reach = {i: _closure(graph, own[i]) for i in own}
    later = _dependents(registry)
    found = []
    for a in sorted(own):
        for b in sorted(own):
            if a >= b:
                continue
            related = b in later[a] or a in later[b]
            reads = b in items[a]["composition"]["reads_extensions"] or a in items[b]["composition"]["reads_extensions"]
            ordered = items[a]["composition"]["order_dependent"] or items[b]["composition"]["order_dependent"]
            reaches = bool(own[b] & reach[a]) or bool(own[a] & reach[b])
            if not (related or reads or ordered or reaches):
                found.append((a, b))
    return found


def affected(registry, changed, root=None):
    """変更したファイル（リポジトリ相対）から、再検証する拡張と、hash を埋め込んだため再生成が要る実体を列挙する。

    拡張は、(1) 実装モジュールまたはその import 閉包（自分に依存する拡張のモジュールへの登録の辺を除く）、
    (2) 仕様・契約文書、(3) 固定した pin の変更で影響を受け、
    (4) 影響を受けた拡張に依存する拡張も影響を受ける。再生成が要るのは、pin が変わった拡張の `embedded_in`。"""
    root = Path(root if root is not None else registry.root)
    changed = {str(c) for c in changed}
    graph = module_graph(root)
    modules = {ext["id"]: {Path(m).stem for m in ext["implementation"]["modules"]} for ext in registry}
    later = _dependents(registry)
    reasons, pinned = {}, {}
    for ext in registry:
        stems = modules[ext["id"]]
        # 自分に依存する拡張が宣言したモジュールへの import は、登録（振り分け）のための辺として辿らない。
        # 依存の向きは宣言（その拡張が自分に依存する）に書かれており、逆向きの読み取りは非干渉の検査（X03）が見る
        registration = set().union(*(modules[d] for d in later[ext["id"]]))
        paths = {f"src/med_dsl/{s}.py" for s in _closure(graph, stems, registration)}
        if ext["spec"] is not None:
            paths.add(ext["spec"]["path"])
        paths.add(ext["contract_doc"])
        pin_paths = {p["path"] for p in ext["pins"]}
        hit = sorted((paths | pin_paths) & changed)
        if hit:
            reasons[ext["id"]] = hit
        if pin_paths & changed:
            pinned[ext["id"]] = sorted(pin_paths & changed)
    grew = True
    while grew:
        grew = False
        for ext in registry:
            if ext["id"] not in reasons and any(d["id"] in reasons for d in ext["depends_on"]):
                reasons[ext["id"]] = ["depends_on:" + ",".join(sorted(d["id"] for d in ext["depends_on"] if d["id"] in reasons))]
                grew = True
    regenerate = set()
    for ident in pinned:
        for pattern in registry.get(ident)["embedded_in"]:
            regenerate.update(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
    lock = None
    lock_path = root / LOCK
    if lock_path.is_file():
        listed = set(decode_json(lock_path.read_bytes())["files"])
        if listed & changed:
            lock = LOCK
    return {"extensions": sorted(reasons), "reasons": {k: reasons[k] for k in sorted(reasons)},
            "regenerate": sorted(regenerate), "lock": lock}
