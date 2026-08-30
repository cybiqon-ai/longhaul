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

import yaml

from . import __version__, doctor, profiles
from .core import orchestrator, planner, worktree
from .core import state as state_io
from .driver.cli_driver import ClaudeAuthError, CliDriver
from .gates.cheat import CheatGate
from .schema.plan import Plan, PlanError
from .schema.state import DONE, FAILED, PARKED

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


def _plan_or_die(args: argparse.Namespace) -> tuple[Plan, float]:
    try:
        return planner.run(
            CliDriver(),
            target=Path(args.target),
            days=args.days,
            profile_name=args.profile,
            model=args.model,
        )
    except ClaudeAuthError as exc:
        print(f"claude is not usable: {exc}")
        print("run `longhaul doctor` — an expired session can look like success.")
        raise SystemExit(1) from exc
    except (FileNotFoundError, ValueError) as exc:
        print(f"cannot plan: {exc}")
        raise SystemExit(1) from exc
    except PlanError as exc:
        print("the planner produced a plan that cannot be executed:")
        for problem in exc.problems:
            print(f"  ✗ {problem}")
        print(f"\nproblems: {len(exc.problems)}")
        raise SystemExit(1) from exc


def cmd_plan(args: argparse.Namespace) -> int:
    """Plan the project and write .longhaul/plan.yaml."""
    out = Path(planner.PLAN_PATH)
    if out.exists() and not args.force:
        print(f"{out} already exists. Re-plan with --force, or read it with `longhaul simulate`.")
        return 1

    plan, cost = _plan_or_die(args)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(plan.to_dict(), sort_keys=False, allow_unicode=True), "utf-8")

    print(planner.render(plan))
    print(f"\nwritten to {out}   cost: ${cost:.2f}")
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    """Show the arc without writing anything."""
    if args.from_file:
        source = Path(args.from_file)
        try:
            plan = Plan.from_dict(yaml.safe_load(source.read_text(encoding="utf-8")))
        except FileNotFoundError:
            print(f"no plan at {source}")
            return 1
        except PlanError as exc:
            print(f"{source} is not a usable plan:")
            for problem in exc.problems:
                print(f"  ✗ {problem}")
            print(f"\nproblems: {len(exc.problems)}")
            return 1
        cost = 0.0
    else:
        plan, cost = _plan_or_die(args)

    print(planner.render(plan))
    print(f"\nnothing was written   cost: ${cost:.2f}")
    return 0


def _load_plan() -> Plan:
    path = Path(planner.PLAN_PATH)
    if not path.is_file():
        print(f"no plan at {path} — run `longhaul plan` first.")
        raise SystemExit(1)
    try:
        return Plan.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")))
    except PlanError as exc:
        print(f"{path} is not a usable plan:")
        for problem in exc.problems:
            print(f"  ✗ {problem}")
        raise SystemExit(1) from exc


def cmd_run(args: argparse.Namespace) -> int:
    root = Path.cwd()
    if not worktree.is_repo(root):
        print("not a git repository — longhaul works in worktrees, so it needs one.")
        return 1

    plan = _load_plan()
    state = state_io.load(root)
    state.project = state.project or plan.project

    task = orchestrator.next_task(plan, state)
    if task is None:
        counts = state.counts()
        print("nothing eligible to run.")
        print(f"  done: {counts['done']}  parked: {counts['parked']}  failed: {counts['failed']}")
        return 0
    if args.dry_run:
        print(f"next: day {task.day}  {task.id}  {task.title}")
        for c in task.acceptance_criteria:
            print(f"  · {c}")
        print("\nnothing was run (--dry-run)")
        return 0

    print(f"day {task.day}/{plan.target_days}  {task.id}  {task.title}")
    try:
        outcome = orchestrator.run_day(CliDriver(), plan, state, root)
    except ClaudeAuthError as exc:
        print(f"\nclaude is not usable: {exc}")
        print("run `longhaul doctor` — an expired session can look like success.")
        return 1

    print(f"\n{outcome.status}: {outcome.detail}")
    counts = state.counts()
    print(
        f"\ntasks: {len(plan.tasks)}  done: {counts['done']}  failed: {counts['failed']}  "
        f"parked: {counts['parked']}  spent: ${state.total_cost_usd:.2f}"
    )
    return outcome.exit_code


def cmd_status(args: argparse.Namespace) -> int:
    plan = _load_plan()
    state = state_io.load(Path.cwd())
    mark = {DONE: "✓", FAILED: "✗", PARKED: "?"}

    print(f"{plan.project}  ·  {plan.profile}")
    for task in sorted(plan.tasks, key=lambda t: (t.day, t.id)):
        ts = state.tasks.get(task.id)
        status = ts.status if ts else "pending"
        attempts = f"  (attempt {ts.attempts})" if ts and ts.attempts > 1 else ""
        icon = mark.get(status, "·")
        print(f"  {icon} day {task.day:>2}  {task.id:<4} {task.title[:56]}{attempts}")
        if ts and ts.status == FAILED and ts.last_error:
            print(f"        {ts.last_error.splitlines()[0][:70]}")

    counts = state.counts()
    # A task the plan names but state has never seen is pending, not invisible.
    counts["pending"] += sum(1 for t in plan.tasks if t.id not in state.tasks)
    ledger = state_io.read_ledger(Path.cwd())
    print(
        f"\ntasks: {len(plan.tasks)}  done: {counts['done']}  failed: {counts['failed']}  "
        f"parked: {counts['parked']}  pending: {counts['pending']}"
    )
    print(f"agent calls: {len(ledger)}  spent: ${state.total_cost_usd:.2f}")
    return 0


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

    for name, help_text in (
        ("plan", "plan the project and write .longhaul/plan.yaml"),
        ("simulate", "show the day-by-day arc without writing anything"),
    ):
        c = sub.add_parser(name, help=help_text)
        c.add_argument("--target", default="target.md", help="the target file (default: target.md)")
        c.add_argument("--days", type=int, default=14, help="deadline in days (default: 14)")
        c.add_argument(
            "--profile",
            default="flutter-android",
            choices=profiles.available(),
            help="project stack",
        )
        c.add_argument("--model", help="override the model for this role")
        if name == "plan":
            c.add_argument("--force", action="store_true", help="overwrite an existing plan")
            c.set_defaults(func=cmd_plan)
        else:
            c.add_argument(
                "--from",
                dest="from_file",
                nargs="?",
                const=str(planner.PLAN_PATH),
                help="render an existing plan instead of generating one",
            )
            c.set_defaults(func=cmd_simulate)

    r = sub.add_parser("run", help="run the next eligible task")
    r.add_argument("--dry-run", action="store_true", help="show the next task without running it")
    r.set_defaults(func=cmd_run)

    st = sub.add_parser("status", help="show progress against the plan")
    st.set_defaults(func=cmd_status)

    planned = {
        "init": "v0.1",
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
