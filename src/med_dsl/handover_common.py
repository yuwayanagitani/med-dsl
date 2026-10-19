"""引き継ぎの各操作が共有する固定値と、操作の登録の形。操作の実装を持たない。"""

from typing import Callable, NamedTuple

from .validation import fields

P0_SPEC_SHA256 = "3ae222d252a46ad6a1cf2221a230a5218170ed13f8ccf645c22249e957c3ac72"
P0_RUNTIME_SHA256 = "2d30169e3d12cb005cc74e152012afffae4e8ae0eec78bd4452f9fc168966e27"
P0_RUNTIME_REF = "med-dsl:p0-native@1"
CHAIN_FIELDS = ("source", "relation_ref", "intermediate", "target", "renames", "stages", "views", "queries")


class Operation(NamedTuple):
    """引き継ぎの操作 1 つ。ホスト（handover.py）が、ヘッダーの検査の後に validate、run の順に呼ぶ。"""
    name: str
    fields: tuple              # 共通の項目（schema_version・operation・consumer・budget）に加えて必要な項目
    needs_p0: bool             # P0 の契約・実行体の hash を検査してから実行するか
    validate: Callable         # (request, budget) -> 検証済みの状態。入力不正は Problem
    run: Callable              # (request, 検証済みの状態, budget) -> 結果


def p0_request(source, views, queries, budget):
    fields(source, ("package", "dependency_packages", "contexts", "ledger"), path="source")
    return {"schema_version": "p0-request-draft-1", "operation": "query", **source,
            "views": views, "queries": queries, "budget": {"max_steps": budget.maximum}}
