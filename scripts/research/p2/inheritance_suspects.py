#!/usr/bin/env python3
"""継承の疑いの機械的な探索（P2-n、設計59 の E2）。宣言の登録条件ではなく、測定のための道具。

依存・読み取り・import の関係がない（independent_pairs の）拡張の組のうち、実装モジュールが識別子らしい文字列定数
（8文字以上、英小文字・数字・下線で、下線を含む）を一定数以上**その二つの拡張だけで**共有するものを疑いとして挙げる。
核のモジュールが持つ定数と、三つ以上の拡張が持つ定数（結果の欄名など共通の語彙）は除く。
使い方: python3 -B scripts/research/p2/inheritance_suspects.py [--min N]"""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(os.environ.get("P2_REPO") or Path(__file__).resolve().parents[3]).resolve()
sys.path.insert(0, str(ROOT / "src"))

from med_dsl.extensions import independent_pairs, load_manifests, Registry

TOKEN = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+")
MINIMUM_LENGTH = 8


def literals(path):
    found = set()
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) >= MINIMUM_LENGTH and TOKEN.fullmatch(node.value):
            found.add(node.value)
    return found


class _Uncoupled:
    """継承の宣言を除いた登録簿（宣言する前の独立の判定を再現する）。"""

    def __init__(self, registry):
        self.root = registry.root
        self._items = {m["id"]: {**m, "inherits": []} for m in registry}

    def __iter__(self):
        return iter(self._items.values())

    def get(self, ident):
        return self._items[ident]


def suspects(root=ROOT, minimum=3, exclusive=True, ignore_declared=True):
    """(拡張の組 -> 共有する定数) のうち、共有が minimum 以上のもの。独立と判定された組だけを調べる。

    exclusive：その二つの拡張だけが持つ定数に限る（偽）と、共通の語彙も数える。
    ignore_declared：宣言した継承を、独立の判定から除く（宣言する前に探索した場合を再現する）。"""
    registry = Registry(root)
    for manifest in load_manifests(Path(root) / "extensions"):
        registry.register(manifest)
    items = {m["id"]: m for m in registry}
    kernel = set()
    for manifest in items.values():
        if manifest["class"] == "BASE":
            for module in manifest["implementation"]["modules"]:
                kernel |= literals(Path(root) / module)
    own = {ident: set().union(*(literals(Path(root) / module) for module in manifest["implementation"]["modules"])) - kernel
           for ident, manifest in items.items() if manifest["class"] != "BASE"}
    holders = {}
    for ident, tokens in own.items():
        for token in tokens:
            holders.setdefault(token, set()).add(ident)
    pairs = independent_pairs(_Uncoupled(registry) if ignore_declared else registry, root)
    found = {}
    for a, b in pairs:
        shared = {token for token in own[a] & own[b] if not exclusive or holders[token] == {a, b}}
        if len(shared) >= minimum:
            found[(a, b)] = sorted(shared)
    return {"independent_pairs": len(pairs), "suspects": found}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min", type=int, default=2)
    parser.add_argument("--shared-vocabulary", action="store_true", help="三つ以上の拡張が持つ定数も数える")
    args = parser.parse_args(argv)
    report = suspects(minimum=args.min, exclusive=not args.shared_vocabulary)
    print(json.dumps({"independent_pairs": report["independent_pairs"],
                      "suspects": {f"{a} | {b}": tokens for (a, b), tokens in report["suspects"].items()}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
