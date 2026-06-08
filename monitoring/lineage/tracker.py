from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LineageNode:
    id: str
    label: str
    node_type: str          # source | transform | model | output
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LineageEdge:
    source_id: str
    target_id: str
    relationship: str       # feeds | transforms | trains | serves


class LineageGraph:
    def __init__(self):
        self._nodes: dict[str, LineageNode] = {}
        self._edges: list[LineageEdge] = []

    def add_node(self, node: LineageNode) -> None:
        self._nodes[node.id] = node

    def add_edge(self, edge: LineageEdge) -> None:
        self._edges.append(edge)

    def to_dict(self) -> dict:
        return {
            "nodes": [
                {"id": n.id, "label": n.label, "type": n.node_type, **n.metadata}
                for n in self._nodes.values()
            ],
            "edges": [
                {"source": e.source_id, "target": e.target_id, "label": e.relationship}
                for e in self._edges
            ],
        }

    def ancestors(self, node_id: str) -> list[str]:
        result = []
        queue = [node_id]
        while queue:
            current = queue.pop()
            parents = [e.source_id for e in self._edges if e.target_id == current]
            result.extend(parents)
            queue.extend(parents)
        return list(set(result))
