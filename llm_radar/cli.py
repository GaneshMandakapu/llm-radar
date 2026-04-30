"""
llm-radar CLI

Commands:
  llm-radar stats              Show aggregated stats
  llm-radar calls              List recent LLM calls
  llm-radar replay <id>        Show full detail for a call
  llm-radar ab-tests           List A/B test results
  llm-radar export             Export call history to JSON or CSV
  llm-radar serve              Start standalone dashboard server
"""

import argparse
import sys
import os
import json


def _get_storage(db_path=None):
    from .storage.db import LLMStorage
    return LLMStorage(db_path=db_path)


def _color(text, code):
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text


def _green(t): return _color(t, "32")
def _yellow(t): return _color(t, "33")
def _red(t): return _color(t, "31")
def _cyan(t): return _color(t, "36")
def _bold(t): return _color(t, "1")
def _dim(t): return _color(t, "2")


def _fmt_cost(v):
    if not v:
        return "$0.0000"
    return f"${v:.4f}"


def _fmt_num(n):
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(int(n))


def cmd_stats(args):
    s = _get_storage(args.db)
    stats = s.get_stats()
    t = stats["totals"]

    print(_bold("\n📡 LLM Radar — Stats\n"))
    print(f"  Total calls   : {_cyan(_fmt_num(t['calls']))}")
    print(f"  Total tokens  : {_cyan(_fmt_num(t['tokens']))}")
    print(f"  Total cost    : {_green(_fmt_cost(t['cost_usd']))}")
    print(f"  Avg latency   : {_yellow(str(round(t['avg_latency_ms'])) + 'ms')}")
    print(f"  Errors        : {_red(str(t['errors']))}")

    if stats["by_model"]:
        print(_bold("\n  By Model:\n"))
        print(f"  {'Model':<35} {'Provider':<12} {'Calls':>6} {'Tokens':>8} {'Cost':>10} {'Avg ms':>8}")
        print("  " + "-" * 83)
        for m in stats["by_model"]:
            print(
                f"  {m['model']:<35} {m['provider']:<12} {_fmt_num(m['calls']):>6}"
                f" {_fmt_num(m['tokens']):>8} {_fmt_cost(m['cost_usd']):>10} {round(m['avg_latency_ms']):>7}ms"
            )
    print()


def cmd_calls(args):
    s = _get_storage(args.db)
    calls = s.get_calls(
        limit=args.limit,
        provider=args.provider or None,
        model=args.model or None,
        status=args.status or None,
    )

    if not calls:
        print(_dim("  No calls recorded yet."))
        return

    print(_bold(f"\n📡 Recent Calls ({len(calls)} shown)\n"))
    print(f"  {'Time':<10} {'Provider':<12} {'Model':<28} {'In':>6} {'Out':>6} {'Cost':>9} {'ms':>6} {'Status':<8} Prompt")
    print("  " + "-" * 110)

    for c in calls:
        ts = str(c.get("created_at", ""))[-8:] if c.get("created_at") else "—"
        status = c.get("status", "")
        status_fmt = _green("✓ ok") if status == "success" else _red("✗ err")
        prompt = (c.get("prompt_preview") or "")[:40].replace("\n", " ")
        latency = c.get("latency_ms") or 0
        lat_fmt = _yellow(f"{int(latency)}") if latency > 3000 else str(int(latency))

        print(
            f"  {ts:<10} {(c.get('provider') or '?'):<12} {(c.get('model') or '?'):<28}"
            f" {_fmt_num(c.get('input_tokens')):>6} {_fmt_num(c.get('output_tokens')):>6}"
            f" {_fmt_cost(c.get('cost_usd')):>9} {lat_fmt:>6} {status_fmt:<8} {_dim(prompt)}"
        )
    print()


def cmd_replay(args):
    s = _get_storage(args.db)
    calls = s.get_calls(limit=10000)
    match = next((c for c in calls if c.get("id", "").startswith(args.id)), None)

    if not match:
        print(_red(f"  No call found with id starting: {args.id}"))
        sys.exit(1)

    for k, v in match.items():
        if v is None:
            continue
        label = f"{k:<22}"
        if k == "prompt_preview":
            print(f"\n  {_bold(label)}\n    {v}\n")
        elif k == "response_preview":
            print(f"  {_bold(label)}\n    {v}\n")
        elif k == "cost_usd":
            print(f"  {_bold(label)} {_green(_fmt_cost(v))}")
        elif k == "status":
            print(f"  {_bold(label)} {_green(v) if v == 'success' else _red(v)}")
        else:
            print(f"  {_bold(label)} {v}")
    print()


def cmd_ab_tests(args):
    s = _get_storage(args.db)
    tests = s.get_ab_tests(limit=args.limit)

    if not tests:
        print(_dim("  No A/B tests recorded yet."))
        return

    print(_bold(f"\n📡 A/B Tests ({len(tests)} shown)\n"))
    for t in tests:
        import json as _json
        variants = _json.loads(t["variants"]) if isinstance(t["variants"], str) else t["variants"]
        print(f"  {_bold(t['name'])}  [{_dim(t['id'])}]  {_dim(str(t.get('created_at','')))}")
        print(f"    Winner by cost: {_green(t['winner_cost'] or '—')}  |  Winner by latency: {_cyan(t['winner_latency'] or '—')}\n")
        for v in variants:
            status = _green("✓") if v["status"] == "success" else _red("✗")
            print(
                f"    [{status}] {_bold(v['label'])}: {v['model']} ({v['provider']})"
                f"  {_fmt_cost(v['cost_usd'])}  {v['latency_ms']}ms"
                f"  in={v['input_tokens']} out={v['output_tokens']}"
            )
            if v.get("response_preview"):
                print(f"         {_dim((v['response_preview'] or '')[:80])}")
        print()


def cmd_export(args):
    s = _get_storage(args.db)
    data = s.export_calls(fmt=args.format)

    if args.output:
        with open(args.output, "w") as f:
            f.write(data)
        print(_green(f"  Exported to {args.output}"))
    else:
        print(data)


def cmd_serve(args):
    try:
        import uvicorn
        from fastapi import FastAPI
        from .core import LLMRadar
    except ImportError:
        print(_red("  uvicorn required: pip install uvicorn"))
        sys.exit(1)

    app = FastAPI(title="LLM Radar")
    radar = LLMRadar(app, db_path=args.db, dashboard_path="/__llm_radar")
    print(_bold(f"\n📡 LLM Radar server starting"))
    print(f"  Dashboard → http://localhost:{args.port}/__llm_radar\n")
    uvicorn.run(app, host=args.host, port=args.port)


def main():
    parser = argparse.ArgumentParser(
        prog="llm-radar",
        description="LLM Radar — observability for LLM apps",
    )
    parser.add_argument("--db", default=None, help="Path to llm_radar.duckdb file")

    sub = parser.add_subparsers(dest="command")

    # stats
    sub.add_parser("stats", help="Show aggregated stats")

    # calls
    p_calls = sub.add_parser("calls", help="List recent calls")
    p_calls.add_argument("--limit", type=int, default=20)
    p_calls.add_argument("--provider", default="")
    p_calls.add_argument("--model", default="")
    p_calls.add_argument("--status", default="")

    # replay
    p_replay = sub.add_parser("replay", help="Show full details of a call")
    p_replay.add_argument("id", help="Call ID (or prefix)")

    # ab-tests
    p_ab = sub.add_parser("ab-tests", help="List A/B test results")
    p_ab.add_argument("--limit", type=int, default=10)

    # export
    p_export = sub.add_parser("export", help="Export call history")
    p_export.add_argument("--format", choices=["json", "csv"], default="json")
    p_export.add_argument("--output", default=None, help="Output file path")

    # serve
    p_serve = sub.add_parser("serve", help="Start standalone dashboard server")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)

    args = parser.parse_args()

    dispatch = {
        "stats": cmd_stats,
        "calls": cmd_calls,
        "replay": cmd_replay,
        "ab-tests": cmd_ab_tests,
        "export": cmd_export,
        "serve": cmd_serve,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
