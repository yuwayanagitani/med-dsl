"""S1/S2 の十分条件の認定と、有限の正の Horn 閉包。"""

from dataclasses import dataclass

from .model import Atom, Budget, PROFILE, Proof
from .validation import digest


def check_extension(request, old, combined, old_signature):
    budget = Budget(request["budget"]["max_steps"])
    budget.tick()  # 空の追加でも 0 は未評価。
    old_packages = {p["ref"] for p in old}
    additions = [p for p in combined if p["ref"] not in old_packages]
    introduced = {p["ref"] for package in additions for p in package["predicates"]}
    definitions = {d["symbol"]: d for package in combined for d in package["definitions"]}
    reasons = set()
    for package in additions:
        for _ in package["inclusions"]:
            budget.tick()
            reasons.add("additional_inclusions")
    for symbol in sorted(introduced):
        budget.tick()
        if symbol not in definitions:
            reasons.add("missing_definition")

    # 定義の依存 DAG を調べる。同値を展開した Horn 規則の循環とは別。
    active, done, order = set(), set(), []

    def visit(symbol):
        if symbol in active:
            reasons.add("cyclic_definitions")
            return
        if symbol in done or symbol not in definitions:
            return
        budget.tick()
        active.add(symbol)
        definition = definitions[symbol]
        for target in sorted(definition.get("all_of") or [definition["parent"]]):
            budget.tick()
            visit(target)
        active.remove(symbol)
        done.add(symbol)
        if symbol in introduced:
            order.append(symbol)

    for symbol in sorted(definitions):
        visit(symbol)
    certified = not reasons
    certificate = {
        "status": "certified" if certified else "not_certified",
        "method": "p0-s1-s2-dag-1", "old_signature": sorted(old_signature),
        "introduced": sorted(introduced),
        "base_sha256": digest(request["base_package"]),
        "extension_sha256": digest(request["extension"]),
        "dependencies": {"base": [{"ref": p["ref"], "sha256": digest(p)} for p in sorted(old, key=lambda p: p["ref"])],
                         "added": [{"ref": p["ref"], "sha256": digest(p)} for p in sorted(additions, key=lambda p: p["ref"])]},
        "scope": {"old_data_only": True, "profile": PROFILE,
                  "guarantee": "model_conservative_extension_over_old_signature" if certified else None,
                  "excludes": ["new_membership_data", "adoption_policy_changes", "mapping_changes"]},
        "reason_codes": sorted(reasons),
    }
    if certified:
        certificate["definition_order"] = order
    return {"status": "ok", "certificate": certificate, "reason_codes": [], "incomplete": []}


@dataclass(frozen=True, order=True)
class Rule:
    body: tuple[str, ...]
    head: str
    reference: str


def compile_rules(packages):
    rules, sources = [], []
    for package in sorted(packages, key=lambda p: p["ref"]):
        for field in ("definitions", "inclusions"):
            for index, item in enumerate(package[field]):
                pointer = f"/{field}/{index}"
                reference = package["ref"] + "#" + pointer
                sources.append({"ref": reference, "package_ref": package["ref"],
                                "package_sha256": digest(package), "pointer": pointer})
                if field == "inclusions":
                    rules.append(Rule((item["sub"],), item["super"], reference))
                elif item["kind"] == "subtype":
                    rules.append(Rule((item["symbol"],), item["parent"], reference))
                else:
                    rules.append(Rule(tuple(sorted(item["all_of"])), item["symbol"], reference))
                    rules.extend(Rule((item["symbol"],), target, reference) for target in item["all_of"])
    return sorted(rules), sorted(sources, key=lambda source: source["ref"])


def positive_closure(initial, rules, budget):
    """一つの有限な導出を選ぶ。短い証明を優先し、循環で根拠を水増ししない。"""
    facts = dict(initial)
    changed = True
    while changed:
        changed = False
        for rule in rules:
            candidates = sorted(fact for fact in facts if fact.predicate == rule.body[0])
            for candidate in candidates:
                budget.tick()
                premises = [Atom(predicate, candidate.args) for predicate in rule.body]
                if not all(premise in facts for premise in premises):
                    continue
                proof = Proof()
                for premise in premises:
                    proof = proof.merge(facts[premise])
                proof = proof.derive(rule.reference)
                head = Atom(rule.head, candidate.args)
                if head not in facts or proof.rank() < facts[head].rank():
                    facts[head] = proof
                    changed = True
    return facts
