from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STRATEGY_ROOT = ROOT / "strategies"
FORBIDDEN_SHARED_IMPORTS = ("shared.context", "shared.slicing")
EXEMPT_STRATEGY_FILES = {"research_indicators.py"}


def test_trade_generating_strategy_files_do_not_import_forbidden_modules() -> None:
    violations: list[str] = []

    for path in _trade_generating_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(_forbidden_imports(path, tree))

    assert not violations, "Forbidden strategy imports found:\n" + "\n".join(
        violations
    )


def _trade_generating_python_files() -> list[Path]:
    # research_indicators.py is context-only; all other strategy-local Python
    # files are treated as trade-generating unless a future spec says otherwise.
    return [
        path
        for path in sorted(STRATEGY_ROOT.glob("**/*.py"))
        if path.name not in EXEMPT_STRATEGY_FILES
    ]


def _forbidden_imports(path: Path, tree: ast.AST) -> list[str]:
    violations: list[str] = []

    for node in ast.walk(tree):
        for imported_name in _imported_names(node):
            if _matches_forbidden_shared_import(imported_name):
                violations.append(_message(path, imported_name))

            if _matches_research_indicators_import(imported_name):
                violations.append(_message(path, imported_name))

    return violations


def _imported_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]

    if isinstance(node, ast.ImportFrom):
        names: list[str] = []
        if node.module:
            names.append(node.module)
            names.extend(f"{node.module}.{alias.name}" for alias in node.names)
        else:
            names.extend(alias.name for alias in node.names)
        return names

    return []


def _matches_forbidden_shared_import(imported_name: str) -> bool:
    return any(
        imported_name == forbidden or imported_name.startswith(f"{forbidden}.")
        for forbidden in FORBIDDEN_SHARED_IMPORTS
    )


def _matches_research_indicators_import(imported_name: str) -> bool:
    return (
        imported_name == "research_indicators"
        or imported_name.endswith(".research_indicators")
    )


def _message(path: Path, imported_name: str) -> str:
    return f"{path.relative_to(ROOT)} imports {imported_name}"
