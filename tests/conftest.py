import httpx
import pytest
import json
from pathlib import Path

RESULTS = {}


def pytest_runtest_logreport(report):
    if report.when == "call" or report.failed:
        RESULTS[report.nodeid] = report.outcome


def pytest_sessionfinish(session, exitstatus):
    root = Path(__file__).resolve().parents[1]
    mapping = json.loads((root / "tests/requirements_map.json").read_text())
    lines = [
        "# Backend requirements verification",
        "",
        "Automated local and mocked-contract verification. Live government acceptance is explicitly deferred until restaurant credentials are available.",
        "",
        "| Requirement | Result | Test evidence |",
        "|---|---|---|",
    ]
    passed = 0
    for requirement, tests in sorted(mapping.items()):
        outcomes = []
        for test in tests:
            matched = [
                outcome
                for node, outcome in RESULTS.items()
                if node.split("[")[0] == test
            ]
            outcomes.extend(matched or ["not run"])
        status = (
            "PASS"
            if outcomes and all(x == "passed" for x in outcomes)
            else "FAIL"
            if "failed" in outcomes
            else "NOT RUN"
        )
        passed += status == "PASS"
        lines.append(
            f"| {requirement} | {status} | "
            + "<br>".join("`" + test + "`" for test in tests)
            + " |"
        )
    lines[2:2] = [
        f"{passed}/94 requirement mappings passed. {sum(v == 'passed' for v in RESULTS.values())} test cases passed; {sum(v == 'failed' for v in RESULTS.values())} failed.",
        "",
    ]
    (root / "QA_REQUIREMENTS_REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


@pytest.fixture(autouse=True)
def prevent_live_government_requests(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Tests must mock every external HTTP request")

    monkeypatch.setattr(httpx, "post", denied)
