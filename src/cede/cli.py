"""CEDE CLI entry point (DS-7.2).

Usage:
    cede build   --target pico [--app-dir ./my_app] [--digest abc123]
    cede deploy  --target pico [--mode gateway|direct]
    cede validate --target pico [--digest abc123]
    cede flash-test --target pico
    cede run --target pico
    cede debug --target pico [--method serial|gdb]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cede import __version__
from cede.config import LabConfig, find_lab_config, find_repo_root, load_app_manifest, load_lab_config
from cede.target_type import load_target_type


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="cede",
        description="CEDE -- Containerized Embedded Development Environment",
    )
    parser.add_argument("--version", action="version", version=f"cede {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_build_parser(subparsers)
    _add_deploy_parser(subparsers)
    _add_validate_parser(subparsers)
    _add_flash_test_parser(subparsers)
    _add_run_parser(subparsers)
    _add_debug_parser(subparsers)
    _add_new_app_parser(subparsers)

    args = parser.parse_args(argv)
    args.func(args)


def _add_build_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("build", help="Build firmware using Docker toolchain")
    p.add_argument("--target", "-t", required=True, help="Target type (e.g. pico, uno)")
    p.add_argument("--app-dir", type=Path, default=Path("."), help="Application directory (default: cwd)")
    p.add_argument("--digest", help="Build Identity token (default: git short SHA)")
    p.set_defaults(func=_cmd_build)


def _add_deploy_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("deploy", help="Deploy artifact to target")
    p.add_argument("--target", "-t", required=True)
    p.add_argument("--mode", choices=["gateway", "direct"], help="Deployment mode")
    p.add_argument("--gateway", help="Gateway SSH address (user@host)")
    p.add_argument("--artifact", type=Path, help="Path to artifact (default: auto-detect)")
    p.set_defaults(func=_cmd_deploy)


def _add_validate_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("validate", help="Validate firmware via serial banner")
    p.add_argument("--target", "-t", required=True)
    p.add_argument("--digest", help="Expected Build Identity")
    p.add_argument("--port", help="Serial port override")
    p.set_defaults(func=_cmd_validate)


def _add_flash_test_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("flash-test", help="Deploy + validate in one step")
    p.add_argument("--target", "-t", required=True)
    p.add_argument("--mode", choices=["gateway", "direct"])
    p.add_argument("--artifact", type=Path, help="Path to artifact")
    p.add_argument("--digest", help="Expected Build Identity")
    p.add_argument("--port", help="Serial port override")
    p.set_defaults(func=_cmd_flash_test)


def _add_run_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("run", help="Build + deploy + validate")
    p.add_argument("--target", "-t", required=True)
    p.add_argument("--app-dir", type=Path, default=Path("."))
    p.add_argument("--mode", choices=["gateway", "direct"])
    p.add_argument("--digest", help="Build Identity token")
    p.add_argument("--port", help="Serial port override")
    p.set_defaults(func=_cmd_run)


def _add_debug_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("debug", help="Open debug session (serial or GDB)")
    p.add_argument("--target", "-t", required=True)
    p.add_argument("--method", choices=["serial", "gdb"], default="serial")
    p.add_argument("--port", help="Serial port override")
    p.add_argument("--log", type=Path, help="Log output to file")
    p.add_argument("--elf", type=Path, help="ELF file for GDB")
    p.set_defaults(func=_cmd_debug)


def _load_lab_config_optional(repo_root: Path) -> LabConfig | None:
    """Load lab.yaml if available, return None otherwise."""
    path = find_lab_config(repo_root)
    if path:
        return load_lab_config(path)
    return None


def _cmd_build(args: argparse.Namespace) -> None:
    """Execute the build command."""
    from cede.build import run_build

    repo_root = find_repo_root(args.app_dir.resolve())
    target_type = load_target_type(args.target, target_types_dir=repo_root / "target-types")

    app_dir = args.app_dir.resolve()

    run_build(
        target_type=target_type,
        app_dir=app_dir,
        workspace=repo_root,
        digest=args.digest,
    )


def _cmd_deploy(args: argparse.Namespace) -> None:
    """Execute the deploy command."""
    from cede.deploy import run_deploy
    from cede.transport import resolve_transport

    repo_root = find_repo_root()
    target_type = load_target_type(args.target, target_types_dir=repo_root / "target-types")

    lab_config = _load_lab_config_optional(repo_root)
    target_entry = lab_config.targets.get(args.target) if lab_config else None

    transport = resolve_transport(
        mode=args.mode,
        target_attach=target_entry.attach if target_entry else None,
        gateway_host=lab_config.gateway.ssh_host if lab_config and lab_config.gateway else None,
        gateway_user=lab_config.gateway.ssh_user if lab_config and lab_config.gateway else None,
        gateway_work_dir=lab_config.gateway.work_dir if lab_config and lab_config.gateway else None,
    )

    artifact = args.artifact
    if not artifact:
        from cede.build import _find_artifact
        artifact = _find_artifact(Path("."), target_type.toolchain.artifact_pattern)
        if not artifact:
            print(f"[cede deploy] ERROR: no artifact found matching '{target_type.toolchain.artifact_pattern}'", file=sys.stderr)
            raise SystemExit(1)

    run_deploy(target_type=target_type, artifact=artifact, transport=transport)


def _cmd_validate(args: argparse.Namespace) -> None:
    """Execute the validate command."""
    from cede.validate import run_validate
    from cede.transport import resolve_transport
    from cede.identity import generate_build_identity

    repo_root = find_repo_root()
    target_type = load_target_type(args.target, target_types_dir=repo_root / "target-types")

    lab_config = _load_lab_config_optional(repo_root)
    target_entry = lab_config.targets.get(args.target) if lab_config else None

    transport = resolve_transport(
        mode=getattr(args, "mode", None),
        target_attach=target_entry.attach if target_entry else None,
        gateway_host=lab_config.gateway.ssh_host if lab_config and lab_config.gateway else None,
        gateway_user=lab_config.gateway.ssh_user if lab_config and lab_config.gateway else None,
        gateway_work_dir=lab_config.gateway.work_dir if lab_config and lab_config.gateway else None,
    )

    digest = args.digest or generate_build_identity(repo_root)

    run_validate(
        target_type=target_type,
        digest=digest,
        transport=transport,
        port=getattr(args, "port", None),
    )


def _cmd_flash_test(args: argparse.Namespace) -> None:
    """Execute the flash-test command (deploy + validate)."""
    from cede.composite import run_flash_test
    from cede.transport import resolve_transport

    repo_root = find_repo_root()
    target_type = load_target_type(args.target, target_types_dir=repo_root / "target-types")

    lab_config = _load_lab_config_optional(repo_root)
    target_entry = lab_config.targets.get(args.target) if lab_config else None

    transport = resolve_transport(
        mode=args.mode,
        target_attach=target_entry.attach if target_entry else None,
        gateway_host=lab_config.gateway.ssh_host if lab_config and lab_config.gateway else None,
        gateway_user=lab_config.gateway.ssh_user if lab_config and lab_config.gateway else None,
        gateway_work_dir=lab_config.gateway.work_dir if lab_config and lab_config.gateway else None,
    )

    artifact = args.artifact
    if not artifact:
        from cede.build import _find_artifact
        artifact = _find_artifact(Path("."), target_type.toolchain.artifact_pattern)
        if not artifact:
            print(f"[cede flash-test] ERROR: no artifact found", file=sys.stderr)
            raise SystemExit(1)

    run_flash_test(
        target_type=target_type,
        artifact=artifact,
        transport=transport,
        digest=args.digest,
        port=getattr(args, "port", None),
    )


def _cmd_run(args: argparse.Namespace) -> None:
    """Execute the run command (build + deploy + validate)."""
    from cede.composite import run_full
    from cede.transport import resolve_transport

    repo_root = find_repo_root(args.app_dir.resolve())
    target_type = load_target_type(args.target, target_types_dir=repo_root / "target-types")

    lab_config = _load_lab_config_optional(repo_root)
    target_entry = lab_config.targets.get(args.target) if lab_config else None

    transport = resolve_transport(
        mode=args.mode,
        target_attach=target_entry.attach if target_entry else None,
        gateway_host=lab_config.gateway.ssh_host if lab_config and lab_config.gateway else None,
        gateway_user=lab_config.gateway.ssh_user if lab_config and lab_config.gateway else None,
        gateway_work_dir=lab_config.gateway.work_dir if lab_config and lab_config.gateway else None,
    )

    run_full(
        target_type=target_type,
        app_dir=args.app_dir.resolve(),
        workspace=repo_root,
        transport=transport,
        digest=args.digest,
        port=getattr(args, "port", None),
    )


def _cmd_debug(args: argparse.Namespace) -> None:
    """Execute the debug command (serial or GDB)."""
    from cede.debug import run_debug_gdb, run_debug_serial
    from cede.transport import resolve_transport

    repo_root = find_repo_root()
    target_type = load_target_type(args.target, target_types_dir=repo_root / "target-types")

    lab_config = _load_lab_config_optional(repo_root)
    target_entry = lab_config.targets.get(args.target) if lab_config else None

    transport = resolve_transport(
        mode=getattr(args, "mode", None),
        target_attach=target_entry.attach if target_entry else None,
        gateway_host=lab_config.gateway.ssh_host if lab_config and lab_config.gateway else None,
        gateway_user=lab_config.gateway.ssh_user if lab_config and lab_config.gateway else None,
        gateway_work_dir=lab_config.gateway.work_dir if lab_config and lab_config.gateway else None,
    )

    if args.method == "gdb":
        run_debug_gdb(
            target_type=target_type,
            transport=transport,
            port=args.port,
            elf_path=args.elf,
        )
    else:
        run_debug_serial(
            target_type=target_type,
            transport=transport,
            port=args.port,
            log_file=args.log,
        )


def _add_new_app_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("new-app", help="Scaffold a new application")
    p.add_argument("name", help="Application name (e.g. my_sensor)")
    p.add_argument("--target", "-t", required=True, help="Target type (e.g. pico, uno)")
    p.add_argument("--output-dir", type=Path, default=None, help="Output directory (default: demo-apps/)")
    p.add_argument("--category", choices=["user", "validation", "gateway"], default="user")
    p.set_defaults(func=_cmd_new_app)


def _cmd_new_app(args: argparse.Namespace) -> None:
    """Execute the new-app scaffolding command."""
    from cede.scaffold import scaffold_app

    repo_root = find_repo_root()
    output_dir = args.output_dir or (repo_root / "demo-apps")
    templates_dir = repo_root / "templates"

    scaffold_app(
        app_name=args.name,
        target=args.target,
        output_dir=output_dir,
        templates_dir=templates_dir,
        category=args.category,
    )


if __name__ == "__main__":
    main()
