from __future__ import annotations

from dataclasses import dataclass, field

from .models import PlannerStep


@dataclass
class PlannerGraph:
    nodes: list[PlannerStep] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)

    def topological_order(self) -> list[str]:
        self.validate()
        node_ids = {node.id for node in self.nodes}
        incoming = {node_id: 0 for node_id in node_ids}
        outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for source, target in self.edges:
            incoming[target] += 1
            outgoing[source].append(target)

        ready = sorted(node_id for node_id, count in incoming.items() if count == 0)
        ordered: list[str] = []
        while ready:
            node_id = ready.pop(0)
            ordered.append(node_id)
            for target in sorted(outgoing[node_id]):
                incoming[target] -= 1
                if incoming[target] == 0:
                    ready.append(target)
                    ready.sort()

        if len(ordered) != len(node_ids):
            raise ValueError("Planner graph must be acyclic")
        return ordered

    def validate(self) -> bool:
        node_ids = [node.id for node in self.nodes]
        unique_node_ids = set(node_ids)
        if len(node_ids) != len(unique_node_ids):
            raise ValueError("Planner graph contains duplicate node ids")
        if not self.nodes:
            raise ValueError("Planner graph must contain at least one node")

        edge_set = set(self.edges)
        for node in self.nodes:
            missing = [
                dependency
                for dependency in node.dependencies
                if dependency not in unique_node_ids
            ]
            if missing:
                raise ValueError(
                    f"Planner step {node.id} has missing dependencies: {missing}"
                )
            for dependency in node.dependencies:
                edge_set.add((dependency, node.id))

        for source, target in edge_set:
            if source not in unique_node_ids:
                raise ValueError(f"Planner graph edge has missing source: {source}")
            if target not in unique_node_ids:
                raise ValueError(f"Planner graph edge has missing target: {target}")
            if source == target:
                raise ValueError(f"Planner graph edge cannot target itself: {source}")

        self._assert_acyclic(edge_set, unique_node_ids)
        self.edges = sorted(edge_set)
        return True

    def _assert_acyclic(
        self,
        edges: set[tuple[str, str]],
        node_ids: set[str],
    ) -> None:
        dependencies: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for source, target in edges:
            dependencies[target].append(source)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visited:
                return
            if node_id in visiting:
                raise ValueError("Planner graph must be acyclic")
            visiting.add(node_id)
            for dependency in dependencies[node_id]:
                visit(dependency)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in sorted(node_ids):
            visit(node_id)
