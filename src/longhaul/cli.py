"""The `longhaul` command.

v0.0.1 is scaffolding: `doctor`, `gate` and `version` do real work; the rest of
the surface is declared so the shape is visible and stable, and exits 2 with a
pointer to the roadmap. See plan.md for the design and ROADMAP.md for staging.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import __version__, doctor
from .gates.cheat import CheatGate

NOT_YET = 2


def _unimplemented(name: str, version: str) -> int:
    print(f"`longhaul {name}` is not implemented yet — planned for {version}.")
    print("See ROADMAP.md. This is a pre-alpha scaffold; nothing ships work yet.")
    return NOT_YET


def cmd_doctor(args: argparse.Namespace) -> int:
    print("longhaul doctor")
    checks = doctor.run(quick=args.quick)
    return doctor.report(checks)


def cmd_gate(args: argparse.Namespace) -> int:
    """Run the deterministic gates over a diff. Useful on its own, today."""
    if args.diff and args.diff != "-":
        diff = Path(args.diff).read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        diff = sys.stdin.read()
    else:
        diff = subprocess.run(
            ["git", "diff", args.rev], capture_output=True, text=True, check=False
        ).stdout

    result = CheatGate().check(diff)
    for finding in result.findings:
        print(f"  {'✗' if finding.severity == 'block' else '!'} {finding}")

    blocking = sum(1 for f in result.findings if f.severity == "block")
    warnings = len(result.findings) - blocking
    print(f"\nfiles checked: {result.checked}  blocking: {blocking}  warnings: {warnings}")
    if result.checked == 0:
        # Exit code 0 has already meant "did nothing" too often to be trusted.
        # A gate that examined no files has not cleared anything.
        print("nothing was checked — an empty diff is not a pass")
        return 1
    return 1 if result.blocked else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="longhaul",
        description="Give it a target and a deadline. It ships a day's work every day.",
    )
    parser.add_argument("--version", action="version", version=f"longhaul {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("doctor", help="check the environment before anything runs")
    d.add_argument("--quick", action="store_true", help="skip the round-trip to Claude")
    d.set_defaults(func=cmd_doctor)

    g = sub.add_parser("gate", help="run the deterministic gates over a diff")
    g.add_argument("--diff", help="path to a diff file, or - for stdin")
    g.add_argument("--rev", default="HEAD", help="git rev to diff against (default: HEAD)")
    g.set_defaults(func=cmd_gate)

    planned = {
        "init": "v0.1",
        "plan": "v0.1",
        "simulate": "v0.1",
        "run": "v0.1",
        "status": "v0.1",
        "report": "v0.1",
        "ui": "v0.2",
        "rollback": "v0.2",
        "kill": "v0.2",
    }
    for name, version in planned.items():
        p = sub.add_parser(name, help=f"(planned, {version})")
        p.set_defaults(func=lambda _a, n=name, v=version: _unimplemented(n, v))

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
