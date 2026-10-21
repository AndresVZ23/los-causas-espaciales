#!/usr/bin/env python3
"""Auditoría estática mínima de estructura, Skills, pruebas y secretos obvios."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

REQUIRED_SKILLS = {
    "nasa-earth-data",
    "geospatial-engineering",
    "statistical-trend-analysis",
    "infrastructure-investment",
    "scientific-quality-assurance",
}
SECRET_PATTERNS = {
    "OpenAI key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    required = ["AGENTS.md", "README.md", "PROGRESS.md", "frontend/package.json", "backend/app/main.py"]
    for relative in required:
        if not (root / relative).is_file():
            errors.append(f"Archivo requerido ausente: {relative}")
    skill_root = root / ".agents" / "skills"
    found = {item.name for item in skill_root.iterdir() if item.is_dir()} if skill_root.is_dir() else set()
    for name in sorted(REQUIRED_SKILLS - found):
        errors.append(f"Skill requerida ausente: {name}")
    for name in sorted(REQUIRED_SKILLS & found):
        skill_file = skill_root / name / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"SKILL.md ausente: {name}")
        elif "TODO" in skill_file.read_text(encoding="utf-8"):
            errors.append(f"Skill contiene TODO: {name}")
    tests = list((root / "backend" / "tests").glob("test_*.py")) if (root / "backend" / "tests").is_dir() else []
    if not tests:
        errors.append("No se encontraron pruebas backend")
    gitignore = (root / ".gitignore").read_text(encoding="utf-8") if (root / ".gitignore").is_file() else ""
    if ".env" not in gitignore:
        errors.append(".gitignore no excluye .env")
    ignored = {".git", ".venv", "node_modules", ".next", ".pytest_cache", "data"}
    extensions = {".py", ".ts", ".tsx", ".js", ".json", ".md", ".yml", ".yaml"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in extensions or any(part in ignored for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                errors.append(f"Posible {label} en {path.relative_to(root)}")
        if path.suffix in {".ts", ".tsx", ".py"} and any(len(line) > 500 for line in content.splitlines()):
            warnings.append(f"Línea >500 caracteres; revisar mantenibilidad: {path.relative_to(root)}")
    report = {"ok": not errors, "root": str(root), "checks": {"required_skills": len(REQUIRED_SKILLS), "backend_tests": len(tests)}, "errors": sorted(set(errors)), "warnings": sorted(set(warnings))}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

