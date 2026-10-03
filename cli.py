#!/usr/bin/env python3
"""
StreamVault CLI — interact with the API from your terminal

Usage:
  python cli.py download <url> [options]
  python cli.py batch <file>
  python cli.py queue list
  python cli.py queue start | pause | clear
  python cli.py status [download_id]
  python cli.py settings get [key]
  python cli.py settings set <key> <value>
  python cli.py logs [--level ERROR]
"""

import argparse
import httpx
import json
import sys
import os
from datetime import datetime

# Force UTF-8 stdout so Unicode symbols (✓, →, █, ░, …) don't crash on
# Windows' default cp1252 console encoding.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE = os.environ.get("STREAMVAULT_URL", "http://localhost:8000/api/v1")
API_KEY = os.environ.get("STREAMVAULT_API_KEY", "")
client = httpx.Client(base_url=BASE, timeout=30, headers={"X-API-Key": API_KEY} if API_KEY else {})


# ─── helpers ────────────────────────────────────────────────────────────────

def _ok(r):
    r.raise_for_status()
    return r.json()

def _fmt_bytes(b):
    if not b: return "—"
    for unit in ("B","KB","MB","GB","TB"):
        if b < 1024: return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"

def _fmt_speed(bps):
    return "—" if not bps else _fmt_bytes(bps) + "/s"

def _color(text, code):
    return f"\033[{code}m{text}\033[0m"

STATUS_COLOR = {
    "downloading": "34", "completed": "32",
    "failed": "31", "paused": "33",
    "queued": "37", "pending": "35",
}


# ─── commands ───────────────────────────────────────────────────────────────

def cmd_download(args):
    payload = {
        "url":          args.url,
        "quality":      args.quality or "bestvideo+bestaudio/best",
        "download_type":args.type or "video",
        "audio_format": args.audio_format,
        "subtitles":    args.subtitles,
        "thumbnail_dl": args.thumbnail,
        "add_to_queue": args.queue,
    }
    if args.output:
        payload["output_folder"] = args.output

    print(f"  Fetching metadata for {args.url}…")
    r = _ok(client.post("/download", json=payload))
    status_char = "→" if args.queue else "↓"
    print(f"  {status_char} [{r['id'][:8]}] {r.get('title') or args.url}")
    print(f"     Status: {_color(r['status'], STATUS_COLOR.get(r['status'], '37'))}")
    if args.watch and not args.queue:
        _watch(r["id"])


def cmd_batch(args):
    if args.file == "-":
        lines = sys.stdin.read().splitlines()
    else:
        with open(args.file) as f:
            lines = f.read().splitlines()
    urls = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
    if not urls:
        print("No URLs found."); return
    print(f"  Submitting {len(urls)} URLs…")
    r = _ok(client.post("/download/batch", json={"urls": urls, "add_to_queue": True}))
    print(f"  ✓ {r['created']} downloads queued")


def cmd_status(args):
    if args.id:
        dl = _ok(client.get(f"/download/{args.id}"))
        _print_dl(dl, verbose=True)
    else:
        dls = _ok(client.get("/downloads?limit=20"))
        if not dls:
            print("  No downloads yet."); return
        print(f"\n  {'ID':8}  {'STATUS':12}  {'PROGRESS':8}  {'SPEED':12}  {'TITLE'}")
        print("  " + "─" * 70)
        for dl in dls:
            sid  = dl["id"][:8]
            stat = dl["status"]
            col  = STATUS_COLOR.get(stat, "37")
            pct  = f"{dl.get('progress',0):.0f}%"
            spd  = _fmt_speed(dl.get("speed"))
            title= (dl.get("title") or dl["url"])[:40]
            print(f"  {sid}  {_color(f'{stat:12}', col)}  {pct:8}  {spd:12}  {title}")
        print()


def _print_dl(dl, verbose=False):
    print(f"\n  Title:    {dl.get('title') or '—'}")
    print(f"  ID:       {dl['id']}")
    print(f"  Status:   {_color(dl['status'], STATUS_COLOR.get(dl['status'],'37'))}")
    print(f"  Progress: {dl.get('progress',0):.1f}%")
    print(f"  Speed:    {_fmt_speed(dl.get('speed'))}")
    if verbose:
        print(f"  Size:     {_fmt_bytes(dl.get('filesize'))}")
        print(f"  Source:   {dl.get('source_site') or '—'}")
        print(f"  Retries:  {dl.get('retry_count',0)}")
        if dl.get("error_msg"):
            print(f"  Error:    {_color(dl['error_msg'], '31')}")
    print()


def _watch(download_id):
    import time
    print(f"  Watching {download_id[:8]}…  (Ctrl+C to stop)")
    try:
        while True:
            dl = _ok(client.get(f"/download/{download_id}"))
            pct = dl.get("progress", 0)
            bar = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
            spd = _fmt_speed(dl.get("speed"))
            print(f"\r  [{bar}] {pct:5.1f}%  {spd:12}", end="", flush=True)
            if dl["status"] in ("completed","failed","cancelled","paused"):
                print(f"\n  → {dl['status'].upper()}")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print()


def cmd_queue(args):
    if args.action == "list":
        items = _ok(client.get("/queue"))
        if not items:
            print("  Queue is empty."); return
        print(f"\n  {'#':3}  {'TITLE':40}  {'STATUS':12}  PRIORITY")
        print("  " + "─" * 70)
        for i, it in enumerate(items, 1):
            title = (it.get("title") or it.get("url","?"))[:40]
            stat  = it.get("status","—")
            prio  = it.get("priority", 5)
            print(f"  {i:3}  {title:40}  {stat:12}  {prio}")
        print()
    elif args.action == "start":
        _ok(client.post("/queue/start"))
        print("  ▶ Queue started")
    elif args.action == "pause":
        _ok(client.post("/queue/pause"))
        print("  ⏸ Queue paused")
    elif args.action == "clear":
        confirm = input("  Clear entire queue? [y/N] ")
        if confirm.lower() == "y":
            _ok(client.post("/queue/clear"))
            print("  ✓ Queue cleared")


def cmd_settings(args):
    if args.action == "get":
        if args.key:
            r = _ok(client.get(f"/settings/{args.key}"))
            print(f"  {r['key']} = {r['value']}")
            if r.get("description"):
                print(f"  ({r['description']})")
        else:
            settings = _ok(client.get("/settings"))
            print(f"\n  {'KEY':25}  VALUE")
            print("  " + "─" * 55)
            for k, v in settings.items():
                print(f"  {k:25}  {v.get('value','')}")
            print()
    elif args.action == "set":
        _ok(client.post("/settings/update", json={"key": args.key, "value": args.value}))
        print(f"  ✓ {args.key} = {args.value}")


def cmd_logs(args):
    params = f"?level={args.level.upper()}&limit={args.limit}" if args.level else f"?limit={args.limit}"
    try:
        logs = _ok(client.get(f"/logs{params}"))
        LEVEL_COLOR = {"INFO":"34","OK":"32","ERROR":"31","WARN":"33"}
        for l in reversed(logs):
            ts  = l.get("created_at","")[:19].replace("T"," ")
            lvl = l.get("level","INFO")
            msg = l.get("message","")
            print(f"  {ts}  {_color(f'[{lvl}]', LEVEL_COLOR.get(lvl,'37'))}  {msg}")
    except Exception as e:
        print(f"  Error: {e}")


def cmd_cancel(args):
    _ok(client.post(f"/download/{args.id}/cancel"))
    print(f"  ✓ Cancelled {args.id[:8]}")


def cmd_retry(args):
    _ok(client.post(f"/download/{args.id}/retry"))
    print(f"  ↺ Retrying {args.id[:8]}")


# ─── arg parser ─────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(prog="streamvault", description="StreamVault CLI")
    sub = p.add_subparsers(dest="cmd")

    # download
    dl = sub.add_parser("download", help="Start a download")
    dl.add_argument("url")
    dl.add_argument("-q","--quality",     default=None)
    dl.add_argument("-t","--type",        default="video", choices=["video","audio","playlist","channel","subtitle"])  # REL-7: was missing channel/subtitle even though both the backend and README support them
    dl.add_argument("-a","--audio-format",default=None)
    dl.add_argument("-o","--output",      default=None)
    dl.add_argument("-s","--subtitles",   action="store_true")
    dl.add_argument("--thumbnail",        action="store_true")
    dl.add_argument("--queue",            action="store_true", help="Add to queue instead of starting immediately")
    dl.add_argument("-w","--watch",       action="store_true", help="Watch progress in terminal")

    # batch
    bt = sub.add_parser("batch", help="Batch download from file (- for stdin)")
    bt.add_argument("file")

    # status
    st = sub.add_parser("status", help="Show download status")
    st.add_argument("id", nargs="?", default=None)

    # queue
    qu = sub.add_parser("queue", help="Manage queue")
    qu.add_argument("action", choices=["list","start","pause","clear"])

    # settings
    se = sub.add_parser("settings", help="View/update settings")
    se.add_argument("action", choices=["get","set"])
    se.add_argument("key",   nargs="?", default=None)
    se.add_argument("value", nargs="?", default=None)

    # logs
    lg = sub.add_parser("logs", help="View logs")
    lg.add_argument("--level", default=None, choices=["INFO","OK","WARN","ERROR"])
    lg.add_argument("--limit", default=50, type=int)

    # cancel / retry
    ca = sub.add_parser("cancel", help="Cancel a download")
    ca.add_argument("id")
    rt = sub.add_parser("retry", help="Retry a failed download")
    rt.add_argument("id")

    args = p.parse_args()

    try:
        if   args.cmd == "download": cmd_download(args)
        elif args.cmd == "batch":    cmd_batch(args)
        elif args.cmd == "status":   cmd_status(args)
        elif args.cmd == "queue":    cmd_queue(args)
        elif args.cmd == "settings": cmd_settings(args)
        elif args.cmd == "logs":     cmd_logs(args)
        elif args.cmd == "cancel":   cmd_cancel(args)
        elif args.cmd == "retry":    cmd_retry(args)
        else:
            p.print_help()
    except httpx.ConnectError:
        print(f"\n  ✕ Cannot connect to StreamVault API at {BASE}")
        print("    Make sure the backend is running: python backend/main.py\n")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"\n  ✕ API error {e.response.status_code}: {e.response.text}\n")
        sys.exit(1)
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
