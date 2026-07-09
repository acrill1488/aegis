from aegis.goal_engine import GoalEngineRuntime, RuleBasedSkillMatcher
from aegis.skill_engine import Skill, SkillRegistry


class FakeSkillEngine:
    def __init__(self, registry):
        self.skills = registry
        self.calls = []

    def run(self, skill_id, inputs):
        self.calls.append((skill_id, inputs))

        class Result:
            success = True
            error = None
            output = {"ok": True}

        return Result()


def test_goal_matcher_extracts_wikipedia_query():
    registry = SkillRegistry(default_root="missing")
    registry.register(Skill(id="browser.wikipedia.search", name="Wikipedia Search"))
    matcher = RuleBasedSkillMatcher(registry)

    goal = matcher.match("Найди RTX 3090 в Википедии")

    assert goal.intent == "search.wikipedia"
    assert goal.selected_skill == "browser.wikipedia.search"
    assert goal.inputs == {"query": "RTX 3090"}
    assert goal.metadata["status"] == "matched"


def test_goal_matcher_supports_english_wikipedia_prefix():
    registry = SkillRegistry(default_root="missing")
    registry.register(Skill(id="browser.wikipedia.search", name="Wikipedia Search"))
    matcher = RuleBasedSkillMatcher(registry)

    goal = matcher.match("Wikipedia AEGIS")

    assert goal.inputs == {"query": "AEGIS"}


def test_goal_matcher_marks_missing_github_skill_not_available():
    registry = SkillRegistry(default_root="missing")
    matcher = RuleBasedSkillMatcher(registry)

    goal = matcher.match("github AEGIS")

    assert goal.selected_skill == "github.search_repository"
    assert goal.inputs == {"query": "AEGIS"}
    assert goal.metadata["status"] == "not_available"


def test_goal_runtime_executes_matched_skill():
    registry = SkillRegistry(default_root="missing")
    registry.register(Skill(id="browser.wikipedia.search", name="Wikipedia Search"))
    skill_engine = FakeSkillEngine(registry)
    runtime = GoalEngineRuntime(skill_engine=skill_engine)

    execution = runtime.execute("Wikipedia AEGIS")

    assert execution["success"] is True
    assert skill_engine.calls == [
        ("browser.wikipedia.search", {"query": "AEGIS"}),
    ]


def test_goal_runtime_reports_unresolved_goal():
    registry = SkillRegistry(default_root="missing")
    runtime = GoalEngineRuntime(skill_engine=FakeSkillEngine(registry))

    execution = runtime.execute("just saying hello")

    assert execution["success"] is False
    assert execution["error"] == "Goal unresolved"
    assert execution["goal"].intent == "unresolved"
