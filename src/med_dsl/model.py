"""P0 の共通値と決定的な処理上限。"""

from dataclasses import dataclass

PROFILE = "p0-positive-1"
POLICY = "fiction:confirmed-explicit-revision@1"
MAX_BYTES = 1024 * 1024


class Problem(Exception):
    def __init__(self, code, path="$", status="invalid_input"):
        super().__init__(code)
        self.code = code
        self.path = path
        self.status = status


@dataclass(frozen=True, order=True)
class Atom:
    predicate: str
    args: tuple[str, ...]


@dataclass(frozen=True)
class Proof:
    assertions: frozenset[str] = frozenset()
    reviews: frozenset[str] = frozenset()
    definitions: frozenset[str] = frozenset()
    depth: int = 0

    def merge(self, other):
        return Proof(self.assertions | other.assertions, self.reviews | other.reviews,
                     self.definitions | other.definitions, max(self.depth, other.depth))

    def derive(self, reference):
        return Proof(self.assertions, self.reviews, self.definitions | {reference}, self.depth + 1)

    def rank(self):
        return (self.depth, sorted(self.assertions), sorted(self.reviews), sorted(self.definitions))

    def evidence(self, binding):
        return {"binding": dict(binding), "assertion_refs": sorted(self.assertions),
                "review_refs": sorted(self.reviews), "definition_refs": sorted(self.definitions)}


@dataclass
class Budget:
    maximum: int
    used: int = 0

    def tick(self):
        if self.used >= self.maximum:
            raise Problem("step_limit", status="resource_limit")
        self.used += 1


def atom(value):
    return Atom(value["predicate"], tuple(value["args"]))
