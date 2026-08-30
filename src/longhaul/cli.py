"""The `longhaul` command.

Working today: `doctor`, `gate`, `plan`, `simulate`, `run`, `status`, `kill`.
Still declared but unimplemented — `init`, `report`, `ui`, `rollback` — so the
shape of the tool is visible; those exit 2 with a pointer to the roadmap.

See plan.md for the design, with live build-status markers, and ROADMAP.md for
what lands when.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

from . import __version__, doctor, profiles
from .core import init as init_mod
from .core import notify, orchestrator, planner, worktree
from .core import state as state_io
from .core.lock import AlreadyRunning, acquire
from .driver.cli_driver import ClaudeAuthError, CliDriver
from .gates.cheat import CheatGate
from .gates.secrets import SecretsGate
from .schema.config import Config
from .schema.plan import Plan, PlanError
from .schema.state import DONE, FAILED, HALTED, PARKED
from .ui import render as ui_render

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

    findings, checked = [], 0
    for gate in (CheatGate(), SecretsGate()):
        result = gate.check(diff)
        findings += result.findings
        checked = max(checked, result.checked)
    for finding in findings:
        print(f"  {'✗' if finding.severity == 'block' else '!'} {finding}")

    blocking = sum(1 for f in findings if f.severity == "block")
    warnings = len(findings) - blocking
    print(f"\nfiles checked: {checked}  blocking: {blocking}  warnings: {warnings}")
    if checked == 0:
        # Exit code 0 has already meant "did nothing" too often to be trusted.
        # A gate that examined no files has not cleared anything.
        print("nothing was checked — an empty diff is not a pass")
        return 1
    return 1 if blocking else 0


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


def cmd_init(args: argparse.Namespace) -> int:
    """Make a repository ready, and refuse if it is not."""
    root = Path.cwd()
    result = init_mod.run(
        root,
        profile=args.profile,
        target=Path(args.target),
        schedule=args.schedule,
        is_repo=worktree.is_repo(root),
    )

    for path in result.created:
        print(f"  + {path}")
    for path in result.skipped:
        print(f"  · {path}")
    for problem in result.problems:
        print(f"  ✗ {problem}")

    print(f"\ncreated: {len(result.created)}  skipped: {len(result.skipped)}  "
          f"problems: {len(result.problems)}")
    if not result.ok:
        return 1

    print("\nchecking the environment before you spend anything:")
    checks = doctor.run(quick=args.quick)
    doctor.report(checks)

    print("\nnext:")
    print(f"  1. describe the project in {args.target}")
    print(f"  2. longhaul plan --target {args.target} --days N --profile {args.profile}")
    print("  3. longhaul simulate --from .longhaul/plan.yaml   # read it before committing")
    print("  4. longhaul run")
    return 0


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

    config = Config.load(root)
    print(f"day {task.day}/{plan.target_days}  {task.id}  {task.title}")
    try:
        with acquire(root):
            outcome = orchestrator.run_day(
                CliDriver(), plan, state, root,
                config=config, do_push=not args.no_push,
            )
    except AlreadyRunning as exc:
        print(f"{exc}")
        return 0  # a skipped overlapping run is not an error
    except ClaudeAuthError as exc:
        print(f"\nclaude is not usable: {exc}")
        print("run `longhaul doctor` — an expired session can look like success.")
        return 1

    print(f"\n{outcome.status}: {outcome.detail}")
    counts = state.counts()
    counts["pending"] += sum(1 for t in plan.tasks if t.id not in state.tasks)
    print(
        f"\ntasks: {len(plan.tasks)}  done: {counts['done']}  failed: {counts['failed']}  "
        f"parked: {counts['parked']}  halted: {counts['halted']}  "
        f"pending: {counts['pending']}  spent: ${state.total_cost_usd:.2f}"
    )

    delivery = notify.send(
        config, plan, state,
        f"{outcome.status}: {outcome.detail.splitlines()[0]}",
        failure=outcome.status not in (DONE, "idle"),
    )
    if delivery.attempted:
        # A notification that did not land is worse than none, because it looks
        # like everything is fine.
        print(f"notify: {delivery.detail}")
    return outcome.exit_code


def cmd_report(args: argparse.Namespace) -> int:
    """Write a self-contained HTML page from .longhaul/. No server, no network."""
    root = Path.cwd()
    plan = _load_plan()
    state = state_io.load(root)
    ledger = state_io.read_ledger(root)

    if args.json:
        print(ui_render.to_json(plan, state))
        return 0

    out = ui_render.write(plan, state, Path(args.out), ledger)
    summary = ui_render.summary(plan, state)
    print(f"wrote {out}  ({out.stat().st_size:,} bytes)")
    print(
        f"tasks: {summary['tasks']}  done: {summary['done']}  failed: {summary['failed']}  "
        f"parked: {summary['parked']}  halted: {summary['halted']}  "
        f"running: {summary['in_progress']}  pending: {summary['pending']}  "
        f"spent: ${summary['total_cost_usd']:.2f}"
    )
    return 0


def cmd_kill(args: argparse.Namespace) -> int:
    """Stop the run in progress — the whole process group, not just the parent.

    Signalling the orchestrator alone leaves the agent it spawned running,
    reparented to init, still spending with no ceiling watching it. Verified:
    SIGTERM to the parent, and the child survives. So the group is the unit.
    """
    import signal

    from .core import lock

    root = Path.cwd()
    path = root / lock.LOCK_PATH
    pid, pgid = lock.read(root)

    if pid is None:
        print("no run in progress")
        return 0

    parent_alive = Path(f"/proc/{pid}").exists()
    group_alive = lock.group_is_alive(pgid)

    if not parent_alive and not group_alive:
        print(f"pid {pid} is not running and its group is empty — clearing a stale lock")
        path.unlink(missing_ok=True)
        return 0

    target = pgid if group_alive else None
    try:
        if target:
            os.killpg(target, signal.SIGTERM)
            print(f"sent SIGTERM to process group {target}")
        else:
            os.kill(pid, signal.SIGTERM)
            print(f"sent SIGTERM to {pid}")
    except ProcessLookupError:
        print("the run exited before the signal landed")
        path.unlink(missing_ok=True)
        return 0
    except PermissionError:
        print(f"not permitted to signal {'group ' + str(target) if target else pid}")
        return 1

    print("state on disk is the last completed step; re-run to resume from there")
    return 0


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
        if ts and ts.pr_url:
            print(f"        PR #{ts.pr_number}  {ts.pr_url}")
        if ts and ts.status in (FAILED, HALTED) and ts.last_error:
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
    r.add_argument("--no-push", action="store_true", help="commit locally, push nothing")
    r.set_defaults(func=cmd_run)

    st = sub.add_parser("status", help="show progress against the plan")
    st.set_defaults(func=cmd_status)

    k = sub.add_parser("kill", help="stop the run in progress")
    k.set_defaults(func=cmd_kill)

    rp = sub.add_parser("report", help="write a self-contained HTML report")
    rp.add_argument("--out", default="report.html", help="where to write it")
    rp.add_argument("--json", action="store_true", help="print the numbers instead")
    rp.set_defaults(func=cmd_report)

    i = sub.add_parser("init", help="prepare a repository for longhaul")
    i.add_argument("--target", default="target.md", help="the target file to create or keep")
    i.add_argument("--profile", default="flutter-android", help="project stack")
    i.add_argument(
        "--schedule", default="none", choices=["none", "cron", "systemd", "actions"],
        help="also write a scheduling file for you to read and install",
    )
    i.add_argument("--quick", action="store_true", help="skip the round-trip to Claude")
    i.set_defaults(func=cmd_init)

    planned = {
        "ui": "v0.2",
        "rollback": "v0.2",
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
