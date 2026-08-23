"""Command line interface.

    jobseeker discover            pull open roles from every configured board
    jobseeker score               score everything against the profile
    jobseeker list                show the shortlist
    jobseeker show <job_id>       full detail, score breakdown and draft
    jobseeker draft               write letters and CVs for the best matches
    jobseeker approve <id...>     the human gate before anything is sent
    jobseeker send                send approved applications (dry run unless --live)
    jobseeker followup            send scheduled follow ups
    jobseeker replies             read the inbox and update statuses
    jobseeker prospect "<query>"  cold outreach to companies with no public board
    jobseeker daily               one full cycle, for cron
    jobseeker stats               the funnel
    jobseeker serve               the dashboard API
    jobseeker respond             draft and send answers to people who replied
    jobseeker digest              email yourself a summary of the day
    jobseeker set-password        set the dashboard sign in password
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from typing import Any

from .config import Settings
from .models import ApplicationStatus, JobStatus
from .pipeline import Pipeline
from .util import log

BANNER = "JobSeeker"


def _print_result(result: Any, as_json: bool) -> None:
    if as_json:
        payload = result.to_dict() if hasattr(result, "to_dict") else result
        print(json.dumps(payload, indent=2, default=str))
        return
    if hasattr(result, "summary"):
        log.ok(result.summary())
        for message in result.messages:
            log.warn(message)
        for item in result.items[:25]:
            status = item.get("status", "")
            label = item.get("company") or item.get("email") or ""
            detail = item.get("title") or item.get("reason") or ""
            log.dim(f"  {status:<9} {label}  {detail}")
    else:
        print(json.dumps(result, indent=2, default=str))


def _table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))
    line = "  ".join(h.upper().ljust(widths[i]) for i, h in enumerate(headers))
    out = [line, "  ".join("-" * widths[i] for i in range(len(headers)))]
    for row in rows:
        out.append("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(out)


def cmd_discover(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    names = args.sources.split(",") if args.sources else None
    return pipeline.discover(names)


def cmd_score(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    return pipeline.score_all(rescore=args.all)


def cmd_list(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    jobs = pipeline.db.list_jobs(
        status=args.status,
        min_score=args.min_score,
        search=args.search,
        limit=args.limit,
    )
    if args.json:
        return [job.to_dict() for job in jobs]
    rows = [
        [
            job.id,
            f"{job.score:.0f}",
            job.status,
            job.company_name[:24],
            job.title[:42],
            (job.location or "")[:20],
            job.source,
        ]
        for job in jobs
    ]
    print(_table(rows, ["id", "score", "status", "company", "title", "location", "source"]))
    return None


def cmd_show(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    job = pipeline.db.get_job(args.job_id)
    if not job:
        log.error(f"job {args.job_id} not found")
        return None
    application = pipeline.db.get_application_for_job(int(job.id or 0))
    if args.json:
        return {
            "job": job.to_dict(),
            "application": application.to_dict() if application else None,
        }

    log.header(f"{job.title}  ({job.company_name})")
    print(f"  score      {job.score}")
    print(f"  status     {job.status}")
    print(f"  location   {job.location or 'not stated'}{'  remote' if job.remote else ''}")
    print(f"  source     {job.source}")
    print(f"  url        {job.url}")
    breakdown = job.score_breakdown or {}
    if breakdown.get("signals"):
        print("\n  score breakdown")
        for name, value in breakdown["signals"].items():
            print(f"    {name:<10} {value}")
    if breakdown.get("reasons"):
        print("\n  why")
        for reason in breakdown["reasons"]:
            print(f"    - {reason}")
    if breakdown.get("blockers"):
        print("\n  blockers")
        for blocker in breakdown["blockers"]:
            print(f"    ! {blocker}")
    if breakdown.get("matched_skills"):
        print("\n  matched skills: " + ", ".join(breakdown["matched_skills"]))
    if breakdown.get("missing_skills"):
        print("  asks for, not on profile: " + ", ".join(breakdown["missing_skills"]))

    if application:
        log.header("Draft")
        print(f"  application {application.id}  status {application.status}  "
              f"channel {application.channel}  via {application.generator}")
        print(f"  to         {application.recipient_email or 'no contact yet'}")
        print(f"  subject    {application.subject}")
        print(f"  letter     {application.cover_letter_path}")
        print(f"  cv         {application.cv_path}\n")
        print(textwrap.indent(application.body, "  "))
    elif job.description:
        log.header("Description")
        print(textwrap.indent(textwrap.fill(job.description[:1200], 92), "  "))
    return None


def cmd_draft(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    if args.job_id:
        job = pipeline.db.get_job(args.job_id)
        if not job:
            log.error(f"job {args.job_id} not found")
            return None
        application = pipeline.draft_one(job, writer_name=args.writer)
        log.ok(f"drafted application {application.id} for {job.company_name}")
        print(f"\n{application.body}\n")
        return None
    return pipeline.draft(limit=args.limit, min_score=args.min_score)


def cmd_approve(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    if args.all_drafts:
        drafts = pipeline.db.list_applications(status=ApplicationStatus.DRAFT, limit=500)
        ids = [int(a.id or 0) for a in drafts]
    else:
        ids = args.application_ids
    return pipeline.approve(ids)


def cmd_send(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    dry_run = not args.live
    if args.live:
        if not pipeline.mailer.send_enabled():
            log.error(
                "Live sending is refused: SEND_ENABLED is not true in your .env. "
                "This is the master switch and it is off by default on purpose."
            )
            return None
        ok, why = pipeline.mailer.ready()
        if not ok:
            log.error(f"Live sending is refused: {why}")
            return None
        if not args.yes:
            queued = len(
                pipeline.db.list_applications(status=ApplicationStatus.APPROVED, limit=500)
            )
            log.warn(
                f"About to send real email to up to {min(queued, args.limit or pipeline.settings.daily_send_cap)} "
                f"recipients as {pipeline.mailer.sender_email}. This cannot be undone."
            )
            answer = input("Type SEND to continue: ").strip()
            if answer != "SEND":
                log.info("cancelled")
                return None
    return pipeline.send(limit=args.limit, dry_run=dry_run)


def cmd_followup(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    return pipeline.run_followups(limit=args.limit, dry_run=not args.live)


def cmd_replies(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    return pipeline.sync_replies(days=args.days)


def cmd_respond(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    return pipeline.respond(limit=args.limit, dry_run=not args.live)


def cmd_digest(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    return pipeline.send_digest(dry_run=not args.live)


def cmd_auto_approve(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    del args
    return pipeline.auto_approve()


def cmd_prospect(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    return pipeline.prospect(args.query, limit=args.limit, enrich=not args.no_enrich)


def cmd_prospect_local(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    return pipeline.prospect_local(limit=args.limit, group=args.group or "")


def cmd_enrich(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    return pipeline.enrich_company(args.company_id)


def cmd_add(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    job = pipeline.add_job_from_url(args.url, company=args.company, title=args.title)
    if not job:
        log.error("could not read that URL")
        return None
    log.ok(f"added job {job.id}: {job.title} at {job.company_name} (score {job.score})")
    return None


def cmd_daily(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    results = pipeline.run_daily(dry_run=not args.live)
    for result in results:
        log.ok(result.summary())
    return None


def cmd_stats(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    stats = pipeline.stats()
    if args.json:
        return stats
    log.header("Funnel")
    print(f"  jobs        {stats['jobs_total']}   companies {stats['companies_total']}   "
          f"contacts {stats['contacts_total']}")
    print(f"  sent        {stats['sent']}   replied {stats['replied']}   "
          f"positive {stats['positive']}")
    print(f"  reply rate  {stats['reply_rate'] * 100:.1f}%   "
          f"interview rate {stats['interview_rate'] * 100:.1f}%")
    print(f"  today       {stats['sent_today']} of {stats['daily_cap']} sent")
    print(f"  writer      {stats['writer']}   live sending "
          f"{'ON' if stats['send_enabled'] else 'OFF'}")
    if stats["jobs_by_status"]:
        log.header("Jobs by status")
        for status, count in sorted(stats["jobs_by_status"].items()):
            print(f"  {status:<16} {count}")
    if stats["applications_by_status"]:
        log.header("Applications by status")
        for status, count in sorted(stats["applications_by_status"].items()):
            print(f"  {status:<16} {count}")
    return None


def cmd_serve(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    from .server.app import serve

    serve(pipeline, host=args.host, port=args.port)
    return None


def cmd_set_password(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    """Set, change or clear the dashboard sign in password.

    Three storage choices, because a laptop and a container need different things:

    * `--env` (default) writes the hash into the env file. Right for local use.
    * `--db` writes it into the database. Right inside a deployed container,
      where it takes effect immediately with no restart and survives redeploys
      because the database sits on the mounted volume.
    * `--clear-db` removes the database value so the deployed AUTH_PASSWORD_HASH
      applies again. This is the way out of a lockout.

    The plain password is never stored, never logged, and never leaves this
    process. Only a scrypt hash is written.
    """
    import getpass
    import re as regex
    from pathlib import Path

    from .server.auth import hash_password

    if args.clear_db:
        pipeline.db.conn.execute("DELETE FROM settings WHERE key = 'auth_password_hash'")
        log.ok("cleared the password stored in the database")
        log.info(
            "AUTH_PASSWORD_HASH from the environment now applies again. "
            "If that is not set either, the dashboard has no password."
        )
        return None

    if args.stdin:
        # Non interactive path, for `az containerapp exec` and scripts:
        #   echo 'the-new-password' | python3 -m jobseeker set-password --db --stdin
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("New dashboard password: ")
        if password != getpass.getpass("Type it again: "):
            log.error("Those did not match.")
            return None

    if len(password) < 10:
        log.error("Use at least 10 characters. This is the only thing guarding your inbox.")
        return None

    encoded = hash_password(password)
    del password

    if args.db:
        pipeline.db.set_setting("auth_password_hash", encoded)
        # Any session issued under the old password must stop working.
        pipeline.db.set_setting("session_secret", __import__("secrets").token_urlsafe(48))
        log.ok("password stored in the database and every existing session ended")
        log.info("It applies immediately. No restart needed.")
        return None

    env_path = Path(args.env)
    # Single quoted: a scrypt hash is full of $ signs, and an unquoted value is
    # mangled by any shell that sources this file.
    line = f"AUTH_PASSWORD_HASH='{encoded}'"
    if env_path.exists():
        text = env_path.read_text(encoding="utf-8")
        if regex.search(r"^AUTH_PASSWORD_HASH=.*$", text, regex.M):
            text = regex.sub(r"^AUTH_PASSWORD_HASH=.*$", line, text, flags=regex.M)
        else:
            text = (
                text.rstrip("\n")
                + f"\n\n# Dashboard sign in. Change it in the UI under Profile.\n{line}\n"
            )
        env_path.write_text(text, encoding="utf-8")
        log.ok(f"password hash written to {env_path}")
    else:
        env_path.write_text(f"{line}\n", encoding="utf-8")
        log.ok(f"created {env_path} with the password hash")

    existing_db_value = pipeline.db.get_setting("auth_password_hash")
    if existing_db_value:
        log.warn(
            "A password set from the dashboard is stored in the database and takes "
            "precedence over this one. Run with --clear-db to remove it."
        )

    log.info("Restart the server for it to take effect.")
    print(
        "\nFor a deployed instance, either change it in the dashboard under Profile,\n"
        "or run it inside the container:\n"
        "  az containerapp exec --name jobseeker --resource-group jobseeker-rg \\\n"
        "    --command \"python3 -m jobseeker set-password --db\"\n"
    )
    return None


def cmd_boards(pipeline: Pipeline, args: argparse.Namespace) -> Any:
    import json as json_module
    from pathlib import Path

    from .sources.base import get as get_source

    path = Path(pipeline.settings.boards_path)
    boards = json_module.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    if args.board_action == "list":
        for provider, handles in boards.items():
            if isinstance(handles, list):
                print(f"{provider} ({len(handles)}): {', '.join(handles)}")
        return None

    provider, handle = args.provider, args.handle
    fetch = get_source(provider)
    key = {"greenhouse": "board", "ashby": "board", "lever": "company", "workable": "account"}[provider]
    found = fetch(**{key: handle})
    if not found:
        log.error(f"{provider}:{handle} returned no postings. Check the handle and try again.")
        return None
    boards.setdefault(provider, [])
    if handle in boards[provider]:
        log.info(f"{handle} is already in the {provider} list")
        return None
    boards[provider].append(handle)
    path.write_text(json_module.dumps(boards, indent=2), encoding="utf-8")
    log.ok(f"added {provider}:{handle} ({len(found)} open roles right now)")
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jobseeker",
        description=BANNER,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--env", default=".env", help="path to the env file")
    parser.add_argument("--json", action="store_true", help="machine readable output")
    parser.add_argument("--quiet", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("discover", help="pull open roles from configured boards")
    p.add_argument("--sources", help="comma separated source names")
    p.set_defaults(func=cmd_discover)

    p = sub.add_parser("score", help="score jobs against the profile")
    p.add_argument("--all", action="store_true", help="rescore everything, not just new jobs")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("list", help="list jobs")
    p.add_argument("--status", choices=[s.value for s in JobStatus])
    p.add_argument("--min-score", type=float)
    p.add_argument("--search")
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="show one job in full")
    p.add_argument("job_id", type=int)
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("draft", help="write letters and CVs")
    p.add_argument("--job-id", type=int)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--min-score", type=float)
    p.add_argument("--writer", choices=["auto", "claude", "template"])
    p.set_defaults(func=cmd_draft)

    p = sub.add_parser("approve", help="approve drafts for sending")
    p.add_argument("application_ids", nargs="*", type=int)
    p.add_argument("--all-drafts", action="store_true")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("send", help="send approved applications")
    p.add_argument("--live", action="store_true", help="actually send (default is a dry run)")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p.add_argument("--limit", type=int)
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("followup", help="send scheduled follow ups")
    p.add_argument("--live", action="store_true")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_followup)

    p = sub.add_parser("replies", help="read the inbox and update statuses")
    p.add_argument("--days", type=int, default=14)
    p.set_defaults(func=cmd_replies)

    p = sub.add_parser("respond", help="answer the people who replied")
    p.add_argument("--live", action="store_true")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_respond)

    p = sub.add_parser("digest", help="email yourself a summary")
    p.add_argument("--live", action="store_true")
    p.set_defaults(func=cmd_digest)

    p = sub.add_parser("auto-approve", help="approve high scoring drafts automatically")
    p.set_defaults(func=cmd_auto_approve)

    p = sub.add_parser("prospect", help="cold outreach discovery through Exa")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--no-enrich", action="store_true")
    p.set_defaults(func=cmd_prospect)

    p = sub.add_parser("prospect-local", help="speculative outreach from the seed list, no API key")
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--group", help="ghana or africa_remote")
    p.set_defaults(func=cmd_prospect_local)

    p = sub.add_parser("enrich", help="find contacts for one company")
    p.add_argument("company_id", type=int)
    p.set_defaults(func=cmd_enrich)

    p = sub.add_parser("add-job", help="add a job from a URL")
    p.add_argument("url")
    p.add_argument("--company", default="")
    p.add_argument("--title", default="")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("daily", help="one full cycle, for cron")
    p.add_argument("--live", action="store_true")
    p.set_defaults(func=cmd_daily)

    p = sub.add_parser("stats", help="funnel statistics")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("serve", help="run the dashboard API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8787)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("set-password", help="set the dashboard sign in password")
    p.add_argument(
        "--db",
        action="store_true",
        help="store the hash in the database instead of the env file, which is "
        "what a deployed container needs",
    )
    p.add_argument(
        "--clear-db",
        action="store_true",
        help="remove the password stored in the database so the deployed "
        "AUTH_PASSWORD_HASH applies again. Use this if you are locked out.",
    )
    p.add_argument(
        "--stdin",
        action="store_true",
        help="read the password from standard input rather than prompting",
    )
    p.set_defaults(func=cmd_set_password)

    p = sub.add_parser("boards", help="manage job board handles")
    board_sub = p.add_subparsers(dest="board_action", required=True)
    board_sub.add_parser("list")
    add_board = board_sub.add_parser("add")
    add_board.add_argument("provider", choices=["greenhouse", "lever", "ashby", "workable"])
    add_board.add_argument("handle")
    p.set_defaults(func=cmd_boards)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log.configure(quiet=args.quiet)

    settings = Settings.load(args.env)
    try:
        pipeline = Pipeline(settings)
    except FileNotFoundError as exc:
        log.error(str(exc))
        return 2

    try:
        result = args.func(pipeline, args)
    except KeyboardInterrupt:
        log.warn("interrupted")
        return 130
    except Exception as exc:  # noqa: BLE001
        log.error(f"{type(exc).__name__}: {exc}")
        return 1

    if result is not None:
        _print_result(result, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
