"""The eval suite, run as part of pytest.

Every scenario is graded by every check. Offline by default, so this runs in CI
with no API key. The same checks grade live model output when a real client is
passed to :func:`run_scenario`.
"""

from __future__ import annotations

import pytest

from evals.harness import (
    ALL_CHECKS,
    check_distinctiveness,
    check_grounding,
    check_schema,
    check_verdict_sanity,
    default_scenarios,
    run_scenario,
)

SCENARIOS = default_scenarios()


@pytest.fixture(scope="module", params=SCENARIOS, ids=lambda s: s.name)
def graded(request):
    scenario = request.param
    return scenario, run_scenario(scenario)


def test_schema_valid(graded):
    _, result = graded
    assert check_schema(result) == []


def test_grounding(graded):
    _, result = graded
    failures = check_grounding(result)
    assert failures == [], failures


def test_distinctiveness(graded):
    _, result = graded
    failures = check_distinctiveness(result)
    assert failures == [], failures


def test_verdict_sanity(graded):
    scenario, result = graded
    failures = check_verdict_sanity(result, scenario)
    assert failures == [], failures


def test_scenario_directional_expectation(graded):
    scenario, result = graded
    if scenario.expect_not:
        assert result.verdict.verdict != scenario.expect_not


def test_offline_engine_is_deterministic():
    scenario = SCENARIOS[0]
    a = run_scenario(scenario).to_json()
    b = run_scenario(scenario).to_json()
    assert a == b


def test_all_checks_pass_on_every_scenario():
    for scenario in SCENARIOS:
        result = run_scenario(scenario)
        for name, check in ALL_CHECKS.items():
            failures = check(result, scenario) if name == "verdict" else check(result)
            assert failures == [], f"{scenario.name}/{name}: {failures}"
