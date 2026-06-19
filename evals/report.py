"""Print an eval report to the terminal.

    python -m evals.report

Runs every scenario through every check and prints a pass/fail grid. Offline by
default; this is the human-friendly companion to the pytest suite.
"""

from __future__ import annotations

from evals.harness import ALL_CHECKS, default_scenarios, run_scenario


def main() -> int:
    scenarios = default_scenarios()
    total_failures = 0

    print("BoardRoom eval report (offline engine)\n")
    for scenario in scenarios:
        result = run_scenario(scenario)
        print(f"Scenario: {scenario.name}  ->  verdict {result.verdict.verdict}")
        for name, check in ALL_CHECKS.items():
            failures = check(result, scenario) if name == "verdict" else check(result)
            status = "PASS" if not failures else "FAIL"
            print(f"  [{status}] {name}")
            for f in failures:
                print(f"         - {f}")
            total_failures += len(failures)
        print()

    print("All checks passed." if total_failures == 0 else f"{total_failures} check failure(s).")
    return 1 if total_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
