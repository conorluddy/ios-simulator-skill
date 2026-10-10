"""Guard: every blocking ``subprocess.run`` in the scripts must pass a timeout.

A wedged ``simctl``/``idb`` call without a timeout hangs the script and the
agent session that launched it. Streaming ``Popen`` users are out of scope.
"""

import ast
from pathlib import Path

SCRIPTS = (
    Path(__file__).resolve().parents[1] / "ios-simulator-skill/skills/ios-simulator-skill/scripts"
)


def _untimed_runs(path: Path) -> list[int]:
    lines = []
    for node in ast.walk(ast.parse(path.read_text())):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and node.func.attr == "run"
            and not any(kw.arg == "timeout" for kw in node.keywords)
        ):
            lines.append(node.lineno)
    return lines


def test_all_subprocess_run_calls_have_a_timeout():
    offenders = {
        str(p.relative_to(SCRIPTS)): lines
        for p in sorted(SCRIPTS.rglob("*.py"))
        if (lines := _untimed_runs(p))
    }
    assert not offenders, f"subprocess.run without timeout: {offenders}"
