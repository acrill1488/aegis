from __future__ import annotations

from aegis.planner import AdaptivePlannerRuntime, PlannerGraph, PlannerStep


class FakeKnowledge:
    def search(self, query, limit=5):
        return [
            {
                "score": 1.0,
                "document": {"id": "doc_1", "title": "AEGIS"},
                "chunk": {"id": "chunk_1", "text": query},
            }
        ]


class FakeReflection:
    def list_reports(self, limit=5):
        return [
            {
                "id": "report_1",
                "recommendations": [
                    {
                        "target": "browser.wikipedia.search",
                        "reason": "Skill needs review.",
                    }
                ],
            }
        ]


class FakeMemory:
    def search(self, query, limit=20):
        return [
            {
                "type": "skill.success",
                "source": "browser.wikipedia.search",
                "summary": query,
                "data": {},
            },
            {
                "type": "skill.success",
                "source": "browser.wikipedia.search",
                "summary": query,
                "data": {},
            },
        ]


class FakeProject:
    id = "project_1"
    name = "Test"
    workspace_path = "/tmp/project"


class FakeProjectRuntime:
    def get_active(self):
        return FakeProject()


class FakeEventPlatform:
    def __init__(self):
        self.events = []

    def publish(self, type, source, payload=None, **context):
        self.events.append((type, source, payload or {}, context))


class FakeCore:
    def __init__(self):
        self.knowledge = FakeKnowledge()
        self.reflection_engine = FakeReflection()
        self.operational_memory = FakeMemory()
        self.project_runtime = FakeProjectRuntime()
        self.event_platform = FakeEventPlatform()


def test_planner_graph_topological_order_validates_dependencies():
    graph = PlannerGraph(
        nodes=[
            PlannerStep(id="a", title="A", skill_id="skill.a"),
            PlannerStep(
                id="b",
                title="B",
                skill_id="skill.b",
                dependencies=["a"],
            ),
        ]
    )

    assert graph.topological_order() == ["a", "b"]
    assert graph.edges == [("a", "b")]


def test_adaptive_planner_builds_context_and_wikipedia_plan(tmp_path):
    core = FakeCore()
    runtime = AdaptivePlannerRuntime(core, root=tmp_path)

    plan = runtime.plan("Найди AEGIS в Википедии")

    assert plan.graph.nodes[0].skill_id == "browser.wikipedia.search"
    assert plan.graph.nodes[0].metadata["inputs"] == {"query": "AEGIS"}
    assert plan.context.project_id == "project_1"
    assert plan.context.knowledge_hits
    assert any(event[0] == "planner.context.created" for event in core.event_platform.events)
    assert any(event[0] == "planner.plan.created" for event in core.event_platform.events)


def test_reflection_and_memory_adjust_confidence(tmp_path):
    runtime = AdaptivePlannerRuntime(FakeCore(), root=tmp_path)

    plan = runtime.plan("Wikipedia AEGIS")
    step = plan.graph.nodes[0]

    assert step.confidence == 0.7
    assert "Skill needs review." in step.metadata["warnings"]
    assert step.metadata["operational_memory"]["success_rate"] == 1.0


def test_planner_validate_loads_saved_plan(tmp_path):
    runtime = AdaptivePlannerRuntime(FakeCore(), root=tmp_path)
    plan = runtime.plan("github AEGIS")

    validation = runtime.validate(plan.id)

    assert validation["valid"] is True
    assert validation["topological_order"] == ["step_1"]
    assert runtime.get_plan(plan.id).status == "validated"
