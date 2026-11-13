"""Application scaffolding: cede new-app (DS-18.5)."""

from __future__ import annotations

import sys
from pathlib import Path


SUPPORTED_TARGETS = ("pico", "uno")


def scaffold_app(
    *,
    app_name: str,
    target: str,
    output_dir: Path,
    templates_dir: Path,
    category: str = "user",
) -> Path:
    """Scaffold a new application from templates.

    Args:
        app_name: Name of the new application (e.g. "my_sensor").
        target: Target type (e.g. "pico", "uno").
        output_dir: Parent directory where the app folder will be created.
        templates_dir: Path to the templates/ directory.
        category: Application category ("user", "validation", "gateway").

    Returns:
        Path to the created application directory.

    Raises:
        SystemExit: If target is unsupported or directory already exists.
    """
    if target not in SUPPORTED_TARGETS:
        print(f"[cede new-app] ERROR: unsupported target '{target}'. Choose from: {SUPPORTED_TARGETS}", file=sys.stderr)
        raise SystemExit(1)

    app_dir = output_dir / app_name / target
    if app_dir.exists():
        print(f"[cede new-app] ERROR: directory already exists: {app_dir}", file=sys.stderr)
        raise SystemExit(1)

    template_dir = templates_dir / target
    if not template_dir.exists():
        print(f"[cede new-app] ERROR: no templates for target '{target}' at {template_dir}", file=sys.stderr)
        raise SystemExit(1)

    app_dir.mkdir(parents=True)

    context = {"app_name": app_name, "category": category}

    for tpl_file in template_dir.rglob("*.tpl"):
        rel = tpl_file.relative_to(template_dir)
        out_name = str(rel).removesuffix(".tpl")
        out_path = app_dir / out_name
        out_path.parent.mkdir(parents=True, exist_ok=True)

        content = tpl_file.read_text(encoding="utf-8")
        for key, value in context.items():
            content = content.replace("{{" + key + "}}", value)

        out_path.write_text(content, encoding="utf-8")

    print(f"[cede new-app] Created {app_dir}", file=sys.stderr)
    print(f"[cede new-app] Files:", file=sys.stderr)
    for f in sorted(app_dir.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(output_dir)}", file=sys.stderr)

    return app_dir
