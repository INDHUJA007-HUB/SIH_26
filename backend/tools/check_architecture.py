"""Keep domain code pure; cross-module calls use explicit public package exports."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src/workbench/modules"
violations: list[str] = []
for source in ROOT.rglob("*.py"):
    own_module = source.relative_to(ROOT).parts[0]
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        imports = []
        if isinstance(node, ast.Import):
            imports = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports = [node.module]
        for imported in imports:
            if imported.split(".")[0] in {
                "fastapi",
                "starlette",
                "sqlalchemy",
                "boto3",
                "httpx",
                "temporalio",
            }:
                violations.append(f"{source.name}:{node.lineno}: framework import {imported}")
            if (
                imported.startswith("workbench.modules.")
                and imported.split(".")[2] != own_module
                and len(imported.split(".")) > 3
            ):
                violations.append(f"{source.name}:{node.lineno}: cross-module import {imported}")
            if imported.startswith("workbench.adapters"):
                violations.append(f"{source.name}:{node.lineno}: infrastructure import {imported}")
if violations:
    raise SystemExit("\n".join(violations))
print("Module architecture boundaries: PASS")
