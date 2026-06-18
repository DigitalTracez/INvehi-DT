#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║          I N V e h i - D T   v2.0  ADVANCED                 ║
║       Indian Vehicle Registration OSINT Tool                 ║
║             Created by DigitalTracez                         ║
║                                                              ║
║  LEGAL DISCLAIMER:                                           ║
║  For educational and lawful use only.                        ║
║  Unauthorized queries may violate IT Act 2000 §43/66.        ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import os
import re
import json
import time
import hashlib
import argparse
import csv
import socket
import platform
import subprocess
from datetime import datetime, timedelta
from urllib.parse import urlencode
from typing import Optional

try:
    import requests
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.align import Align
    from rich.columns import Columns
    from rich.rule import Rule
    from rich.live import Live
    from rich.layout import Layout
    from rich import box
    from rich.prompt import Prompt, Confirm
    from rich.progress import (
        Progress, SpinnerColumn, TextColumn,
        TimeElapsedColumn, BarColumn, TaskProgressColumn
    )
    from rich.syntax import Syntax
    from rich.tree import Tree
    from rich.markdown import Markdown
    from rich.traceback import install as rich_tb
    rich_tb(show_locals=False)
except ImportError as e:
    print(f"[!] Missing dependency: {e}")
    print("[*] Run: pip install requests rich")
    sys.exit(1)

# ═══════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════
TOOL_NAME   = "INvehi-DT"
VERSION     = "2.0 Advanced"
AUTHOR      = "DigitalTracez"
BUILD_DATE  = "2025"

API_BASE    = "https://vehicleinfobyterabaap.vercel.app/lookup"
ALT_APIS    = [
    "https://vehicleinfobyterabaap.vercel.app/lookup",
]

BASE_DIR    = os.path.expanduser("~/.invehidt")
CACHE_DIR   = os.path.join(BASE_DIR, "cache")
LOG_DIR     = os.path.join(BASE_DIR, "logs")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
REPORT_DIR  = os.path.join(BASE_DIR, "reports")
WATCH_DIR   = os.path.join(BASE_DIR, "watchlist")

CACHE_TTL_H  = 24
MAX_HISTORY  = 200
REQUEST_DELAY = 0.6   # seconds between batch requests

RC_PATTERN  = re.compile(r'^[A-Z]{2}\d{2}[A-Z]{1,3}\d{1,4}$', re.IGNORECASE)

# Indian state codes mapping
STATE_CODES = {
    "AN": "Andaman & Nicobar", "AP": "Andhra Pradesh", "AR": "Arunachal Pradesh",
    "AS": "Assam", "BR": "Bihar", "CH": "Chandigarh", "CG": "Chhattisgarh",
    "DD": "Daman & Diu", "DL": "Delhi", "DN": "Dadra & Nagar Haveli",
    "GA": "Goa", "GJ": "Gujarat", "HR": "Haryana", "HP": "Himachal Pradesh",
    "JK": "Jammu & Kashmir", "JH": "Jharkhand", "KA": "Karnataka",
    "KL": "Kerala", "LA": "Ladakh", "LD": "Lakshadweep", "MP": "Madhya Pradesh",
    "MH": "Maharashtra", "MN": "Manipur", "ML": "Meghalaya", "MZ": "Mizoram",
    "NL": "Nagaland", "OD": "Odisha", "PY": "Puducherry", "PB": "Punjab",
    "RJ": "Rajasthan", "SK": "Sikkim", "TN": "Tamil Nadu", "TS": "Telangana",
    "TR": "Tripura", "UP": "Uttar Pradesh", "UK": "Uttarakhand", "WB": "West Bengal",
}

console = Console()

# ═══════════════════════════════════════════════
#  FILESYSTEM
# ═══════════════════════════════════════════════
def ensure_dirs():
    for d in (CACHE_DIR, LOG_DIR, RESULTS_DIR, REPORT_DIR, WATCH_DIR):
        os.makedirs(d, exist_ok=True)

def log(msg: str, level: str = "INFO"):
    path = os.path.join(LOG_DIR, f"invehidt_{datetime.now().strftime('%Y%m')}.log")
    with open(path, "a") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level:5}] {msg}\n")

def cache_key(rc: str) -> str:
    return hashlib.sha256(rc.upper().encode()).hexdigest()[:20]

def cache_path(rc: str) -> str:
    return os.path.join(CACHE_DIR, f"{cache_key(rc)}.json")

def save_cache(rc: str, data: dict):
    payload = {
        "ts": datetime.now().isoformat(),
        "rc": rc.upper(),
        "ttl_hours": CACHE_TTL_H,
        "data": data
    }
    with open(cache_path(rc), "w") as f:
        json.dump(payload, f, indent=2)

def load_cache(rc: str) -> Optional[dict]:
    path = cache_path(rc)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            payload = json.load(f)
        cached_at = datetime.fromisoformat(payload["ts"])
        if datetime.now() - cached_at < timedelta(hours=CACHE_TTL_H):
            return payload["data"]
        os.remove(path)   # expired — delete
    except Exception:
        pass
    return None

def export_json(rc: str, data: dict) -> str:
    fname = f"{rc.upper()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path  = os.path.join(RESULTS_DIR, fname)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path

def export_csv_append(rc: str, data: dict):
    path = os.path.join(RESULTS_DIR, "all_results.csv")
    flat = {k: str(v) for k, v in data.items()}
    flat["rc_queried"] = rc.upper()
    flat["query_time"] = datetime.now().isoformat()
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=flat.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(flat)

def save_history(rc: str, status: str = "OK"):
    path = os.path.join(LOG_DIR, "history.txt")
    lines = []
    if os.path.exists(path):
        with open(path) as f:
            lines = f.read().splitlines()
    entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {rc.upper():15}  {status}"
    lines.insert(0, entry)
    lines = lines[:MAX_HISTORY]
    with open(path, "w") as f:
        f.write("\n".join(lines))

def load_history() -> list:
    path = os.path.join(LOG_DIR, "history.txt")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return f.read().splitlines()

# watchlist
def watchlist_path() -> str:
    return os.path.join(WATCH_DIR, "watchlist.json")

def load_watchlist() -> dict:
    p = watchlist_path()
    if not os.path.exists(p):
        return {}
    with open(p) as f:
        return json.load(f)

def save_watchlist(wl: dict):
    with open(watchlist_path(), "w") as f:
        json.dump(wl, f, indent=2)

# ═══════════════════════════════════════════════
#  VALIDATION & PARSING
# ═══════════════════════════════════════════════
def validate_rc(rc: str) -> tuple:
    rc = rc.strip().upper().replace(" ", "").replace("-", "")
    if not rc:
        return False, "Empty input."
    if not RC_PATTERN.match(rc):
        return False, (
            f"[red]'{rc}'[/red] is not a valid Indian RC number.\n"
            "  Format: [STATE][RTO][SERIES][NUMBER]  e.g. [cyan]MH01AB1234[/cyan]"
        )
    return True, rc

def decode_rc(rc: str) -> dict:
    """Extract metadata from RC number itself."""
    rc = rc.upper()
    state_code = rc[:2]
    rto_code   = rc[2:4]
    series     = re.search(r'[A-Z]+', rc[4:])
    number     = re.search(r'\d+$', rc)
    return {
        "state_code":  state_code,
        "state_name":  STATE_CODES.get(state_code, "Unknown"),
        "rto_number":  rto_code,
        "series":      series.group() if series else "?",
        "number":      number.group() if number else "?",
        "full_rc":     rc,
    }

def check_insurance_status(validity_str: str) -> tuple:
    """Returns (status_label, style, days_remaining)."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            d = datetime.strptime(validity_str.strip(), fmt)
            delta = (d - datetime.now()).days
            if delta < 0:
                return "EXPIRED", "bold red", delta
            elif delta <= 30:
                return "EXPIRING SOON", "bold yellow", delta
            elif delta <= 90:
                return "VALID (< 3 months)", "yellow", delta
            else:
                return "VALID", "bold green", delta
        except ValueError:
            continue
    return "UNKNOWN", "dim", 0

# ═══════════════════════════════════════════════
#  NETWORK UTILS
# ═══════════════════════════════════════════════
def check_connectivity() -> bool:
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except Exception:
        return False

def get_public_ip() -> str:
    try:
        r = requests.get("https://api.ipify.org", timeout=5)
        return r.text.strip()
    except Exception:
        return "Unknown"

# ═══════════════════════════════════════════════
#  API
# ═══════════════════════════════════════════════
def fetch_vehicle_data(rc: str, skip_cache: bool = False) -> tuple:
    """Returns (data, from_cache, elapsed_ms)."""
    if not skip_cache:
        cached = load_cache(rc)
        if cached:
            return cached, True, 0.0

    url = f"{API_BASE}?{urlencode({'rc': rc})}"
    headers = {
        "User-Agent": f"{TOOL_NAME}/{VERSION} educational-osint",
        "Accept": "application/json",
        "X-Tool": "INvehi-DT",
    }

    t0 = time.perf_counter()
    try:
        resp = requests.get(url, headers=headers, timeout=15)
    except requests.exceptions.ConnectionError:
        return {"error": "No network. Check your internet connection."}, False, 0.0
    except requests.exceptions.Timeout:
        return {"error": "Request timed out (15s). API may be down."}, False, 0.0
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}, False, 0.0

    elapsed = round((time.perf_counter() - t0) * 1000, 1)

    if resp.status_code == 429:
        return {"error": "Rate limited by API. Wait a moment and retry."}, False, elapsed
    if resp.status_code == 404:
        return {"error": "Vehicle not found. Double-check the RC number."}, False, elapsed
    if resp.status_code != 200:
        return {"error": f"API error: HTTP {resp.status_code}"}, False, elapsed

    try:
        data = resp.json()
    except Exception:
        return {"error": "API returned invalid JSON."}, False, elapsed

    if not data or (isinstance(data, dict) and data.get("status") == "error"):
        msg = data.get("message", "No data returned.") if isinstance(data, dict) else "Empty response."
        return {"error": msg}, False, elapsed

    save_cache(rc, data)
    return data, False, elapsed

# ═══════════════════════════════════════════════
#  BANNER & UI
# ═══════════════════════════════════════════════
def clear():
    os.system("cls" if os.name == "nt" else "clear")

def print_banner():
    console.print()
    banner_lines = [
        ("  ██╗███╗   ██╗██╗   ██╗███████╗██╗  ██╗██╗      ██████╗ ████████╗", "bold cyan"),
        ("  ██║████╗  ██║██║   ██║██╔════╝██║  ██║██║      ██╔══██╗╚══██╔══╝", "bold cyan"),
        ("  ██║██╔██╗ ██║██║   ██║█████╗  ███████║██║█████╗██║  ██║   ██║   ", "bold cyan"),
        ("  ██║██║╚██╗██║╚██╗ ██╔╝██╔══╝  ██╔══██║██║╚════╝██║  ██║   ██║   ", "bold cyan"),
        ("  ██║██║ ╚████║ ╚████╔╝ ███████╗██║  ██║██║      ██████╔╝   ██║   ", "bold cyan"),
        ("  ╚═╝╚═╝  ╚═══╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚═╝      ╚═════╝    ╚═╝  ", "bold cyan"),
    ]
    for line, style in banner_lines:
        console.print(line, style=style)

    console.print()
    t = Text()
    t.append("  ▸ Indian Vehicle Registration OSINT  ", style="dim white")
    t.append(f"v{VERSION}", style="bold yellow")
    t.append("  ▸  Created by ", style="dim white")
    t.append(AUTHOR, style="bold green")
    t.append(f"  ▸  {datetime.now().strftime('%d %b %Y  %H:%M')}", style="dim")
    console.print(t)
    console.print()
    console.print(Rule(style="cyan dim"))

    warn = Text()
    warn.append(" ⚠ ", style="bold red on black")
    warn.append(" LEGAL NOTICE ", style="bold white")
    warn.append("For educational & ethical use only. ", style="dim white")
    warn.append("IT Act 2000 §43/66", style="bold yellow")
    warn.append(" applies to unauthorized queries.", style="dim white")
    console.print(Panel(warn, border_style="red dim", padding=(0,1)))
    console.print(Rule(style="cyan dim"))
    console.print()

def print_menu():
    grid = Table.grid(expand=False, padding=(0, 3))
    grid.add_column(style="bold cyan", min_width=4)
    grid.add_column(style="white", min_width=32)
    grid.add_column(style="bold cyan", min_width=4)
    grid.add_column(style="white")

    grid.add_row("[1]", "🔍  Single RC Lookup",       "[2]", "📋  Batch Lookup (file)")
    grid.add_row("[3]", "📡  Live Monitor (watchlist)","[4]", "📊  Generate HTML Report")
    grid.add_row("[5]", "🕑  Query History",           "[6]", "🗺   Decode RC Number")
    grid.add_row("[7]", "💾  Export All to CSV",       "[8]", "🛡   System & Tool Info")
    grid.add_row("[9]", "🗑   Manage Watchlist",        "[0]", "❌  Exit")

    console.print(Panel(
        grid,
        title="[bold cyan]◈  INvehi-DT MENU  ◈[/bold cyan]",
        border_style="cyan",
        expand=False,
        padding=(1, 2),
    ))

# ═══════════════════════════════════════════════
#  RESULT DISPLAY
# ═══════════════════════════════════════════════
def print_result(rc: str, data: dict, from_cache: bool, elapsed: float):
    console.print()

    # — status bar —
    cache_label = "[bold cyan]CACHE HIT[/bold cyan]" if from_cache else "[dim]LIVE[/dim]"
    time_label  = f"[yellow]{elapsed} ms[/yellow]" if elapsed else "[dim]—[/dim]"
    console.print(
        f"  [bold green]● FOUND[/bold green]   {cache_label}   ⏱  {time_label}\n"
    )

    # — RC decode panel —
    decoded = decode_rc(rc)
    dec_table = Table(box=box.SIMPLE, show_header=False, padding=(0,1))
    dec_table.add_column(style="dim cyan")
    dec_table.add_column(style="white")
    dec_table.add_row("State",  f"{decoded['state_name']} ({decoded['state_code']})")
    dec_table.add_row("RTO No", decoded['rto_number'])
    dec_table.add_row("Series", decoded['series'])
    dec_table.add_row("Number", decoded['number'])
    console.print(Panel(dec_table, title=f"[bold white]RC Decode  ·  {rc}[/bold white]",
                        border_style="blue", expand=False))

    # — main data table —
    table = Table(
        title="[bold cyan]Vehicle Record[/bold cyan]",
        box=box.ROUNDED,
        show_lines=True,
        border_style="cyan",
        header_style="bold magenta on black",
        min_width=65,
    )
    table.add_column("Field",  style="bold cyan",  no_wrap=True, min_width=30)
    table.add_column("Value",  style="white")
    table.add_column("Status", style="dim",        width=20)

    # priority display order
    PRIORITY = [
        "registrationNumber","regNo","ownerName","owner_name",
        "vehicleName","vehicle_name","makerModel","vehicleClass","vehicle_class",
        "fuelType","fuel_type","cubicCapacity","cubic_capacity",
        "seatCapacity","seat_capacity","colour","color",
        "registrationDate","registration_date",
        "insuranceValidity","insurance_validity","insuranceValidUpto","insurance_valid_upto",
        "fitnessValidUpto","fitness_valid_upto","puccValidUpto",
        "taxValidUpto","permit_valid_upto",
        "rtoCode","rto_code","registrationAuthority","registration_authority",
        "financer","financerName","blacklistStatus",
        "chassisNumber","chassis_number","engineNumber","engine_number",
        "nocDetails","rcStatus",
    ]

    shown = set()
    SENSITIVE = ("chassis", "engine", "financer")
    VALIDITY_KEYS = ("insurance", "fitness", "pucc", "tax", "permit")

    def add_row(k, v):
        label = k.replace("_", " ").title()
        val   = str(v)
        extra = ""

        if any(s in k.lower() for s in VALIDITY_KEYS):
            status, style, days = check_insurance_status(val)
            days_str = f"{abs(days)}d {'ago' if days < 0 else 'left'}" if days else ""
            extra = f"[{style}]{status}[/{style}] [dim]{days_str}[/dim]"
        elif any(s in k.lower() for s in SENSITIVE):
            val   = f"[dim yellow]{val}[/dim yellow]"
            extra = "[dim]sensitive[/dim]"
        elif "owner" in k.lower() or "name" in k.lower():
            val   = f"[bold white]{val}[/bold white]"
        elif "blacklist" in k.lower():
            if val.lower() in ("yes", "true", "blacklisted"):
                val   = f"[bold red]{val}[/bold red]"
                extra = "[bold red]⚠ BLACKLISTED[/bold red]"
            else:
                val   = f"[green]{val}[/green]"
                extra = "[green]✓ CLEAR[/green]"

        table.add_row(label, val, extra)
        shown.add(k)

    for k in PRIORITY:
        if k in data and k not in shown:
            add_row(k, data[k])

    for k, v in data.items():
        if k not in shown:
            add_row(k, v)

    console.print(table)
    console.print()

def print_error(msg: str):
    console.print(Panel(
        Text.assemble(("  ✗  ", "bold red"), (msg, "white")),
        border_style="red",
        title="[bold red]ERROR[/bold red]",
        padding=(0, 1),
    ))

def print_ok(msg: str):
    console.print(f"  [bold green]✓[/bold green]  {msg}")

# ═══════════════════════════════════════════════
#  FETCH WITH SPINNER
# ═══════════════════════════════════════════════
def fetch_with_spinner(rc: str, skip_cache: bool = False) -> tuple:
    with Progress(
        SpinnerColumn("dots2", style="cyan"),
        TextColumn("[cyan]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as prog:
        prog.add_task(f"Querying registry for [bold]{rc}[/bold] …", total=None)
        result = fetch_vehicle_data(rc, skip_cache)
    return result

# ═══════════════════════════════════════════════
#  FLOW: SINGLE LOOKUP
# ═══════════════════════════════════════════════
def flow_single_lookup():
    console.print()
    rc_raw = Prompt.ask("  [bold cyan]Enter RC number[/bold cyan]")
    ok, rc = validate_rc(rc_raw)
    if not ok:
        print_error(rc)
        return

    log(f"QUERY rc={rc}")
    data, from_cache, elapsed = fetch_with_spinner(rc)

    if "error" in data:
        print_error(data["error"])
        log(f"FAIL rc={rc} err={data['error']}", "ERROR")
        save_history(rc, "FAIL")
        return

    print_result(rc, data, from_cache, elapsed)
    path = export_json(rc, data)
    export_csv_append(rc, data)
    save_history(rc, "OK")
    log(f"OK rc={rc} cached={from_cache} ms={elapsed}")
    print_ok(f"JSON saved → [dim]{path}[/dim]")
    print_ok(f"CSV appended → [dim]{os.path.join(RESULTS_DIR, 'all_results.csv')}[/dim]")
    console.print()

# ═══════════════════════════════════════════════
#  FLOW: BATCH LOOKUP
# ═══════════════════════════════════════════════
def flow_batch_lookup():
    console.print()
    filepath = Prompt.ask("  [bold cyan]RC list file path[/bold cyan] (one RC per line)")
    if not os.path.exists(filepath):
        print_error(f"File not found: {filepath}")
        return

    with open(filepath) as f:
        raw_lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    if not raw_lines:
        print_error("File is empty.")
        return

    console.print(f"\n  [dim]Found [bold]{len(raw_lines)}[/bold] entries.[/dim]\n")

    ok_count = fail_count = skip_count = 0
    results = []

    with Progress(
        SpinnerColumn("dots", style="cyan"),
        TextColumn("[cyan]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as prog:
        task = prog.add_task("Processing …", total=len(raw_lines))

        for raw in raw_lines:
            valid, rc = validate_rc(raw)
            if not valid:
                skip_count += 1
                prog.advance(task)
                continue

            prog.update(task, description=f"[cyan]{rc}[/cyan]")
            data, from_cache, elapsed = fetch_vehicle_data(rc)

            if "error" in data:
                fail_count += 1
                save_history(rc, "FAIL")
                log(f"BATCH FAIL rc={rc}", "WARN")
            else:
                ok_count += 1
                export_json(rc, data)
                export_csv_append(rc, data)
                save_history(rc, "OK")
                results.append({"rc": rc, "data": data})
                log(f"BATCH OK rc={rc}")

            prog.advance(task)
            time.sleep(REQUEST_DELAY)

    console.print()
    summary = Table(box=box.SIMPLE, show_header=False, padding=(0,2))
    summary.add_column(style="bold")
    summary.add_column(style="white")
    summary.add_row("[green]Success[/green]", str(ok_count))
    summary.add_row("[red]Failed[/red]",   str(fail_count))
    summary.add_row("[yellow]Skipped[/yellow]", str(skip_count))
    summary.add_row("[cyan]Total[/cyan]",   str(len(raw_lines)))
    console.print(Panel(summary, title="[bold]Batch Summary[/bold]", border_style="cyan", expand=False))
    print_ok(f"Results in [dim]{RESULTS_DIR}[/dim]")
    console.print()

# ═══════════════════════════════════════════════
#  FLOW: DECODE RC
# ═══════════════════════════════════════════════
def flow_decode_rc():
    console.print()
    rc_raw = Prompt.ask("  [bold cyan]Enter RC number to decode[/bold cyan]")
    ok, rc = validate_rc(rc_raw)
    if not ok:
        print_error(rc)
        return

    decoded = decode_rc(rc)
    tree = Tree(f"[bold cyan]RC Breakdown: [white]{rc}[/white][/bold cyan]")
    tree.add(f"[dim]State Code:[/dim]  [bold]{decoded['state_code']}[/bold]  →  [green]{decoded['state_name']}[/green]")
    tree.add(f"[dim]RTO Number:[/dim]  [bold]{decoded['rto_number']}[/bold]")
    tree.add(f"[dim]Series:[/dim]      [bold]{decoded['series']}[/bold]")
    tree.add(f"[dim]Vehicle No:[/dim]  [bold]{decoded['number']}[/bold]")
    console.print()
    console.print(Panel(tree, border_style="blue", expand=False, padding=(1,2)))
    console.print()

# ═══════════════════════════════════════════════
#  FLOW: LIVE MONITOR (watchlist)
# ═══════════════════════════════════════════════
def flow_live_monitor():
    wl = load_watchlist()
    if not wl:
        console.print("\n  [dim]Watchlist is empty. Add RCs via Manage Watchlist.[/dim]\n")
        return

    console.print(f"\n  [cyan]Monitoring {len(wl)} vehicles.[/cyan]  [dim]Press Ctrl+C to stop.[/dim]\n")
    log(f"MONITOR started, {len(wl)} vehicles")

    try:
        while True:
            for rc, meta in wl.items():
                console.print(f"  [dim]{datetime.now().strftime('%H:%M:%S')}[/dim]  Checking [bold cyan]{rc}[/bold cyan] …", end="  ")
                data, from_cache, elapsed = fetch_vehicle_data(rc, skip_cache=True)
                if "error" in data:
                    console.print(f"[red]FAIL[/red]  {data['error']}")
                    continue

                # Check insurance
                for k in ("insuranceValidity", "insurance_validity", "insuranceValidUpto"):
                    if k in data:
                        status, style, days = check_insurance_status(str(data[k]))
                        console.print(f"[{style}]{status}[/{style}]  [dim]({abs(days)}d {'ago' if days<0 else 'left'})[/dim]")
                        if days < 30:
                            log(f"ALERT rc={rc} insurance={status} days={days}", "ALERT")
                        break
                else:
                    console.print("[green]OK[/green]")

                time.sleep(REQUEST_DELAY)

            interval = int(meta.get("interval_min", 60)) if wl else 60
            console.print(f"\n  [dim]Next check in {interval} min. Ctrl+C to exit.[/dim]\n")
            time.sleep(interval * 60)

    except KeyboardInterrupt:
        console.print("\n  [dim]Monitor stopped.[/dim]\n")
        log("MONITOR stopped by user")

# ═══════════════════════════════════════════════
#  FLOW: MANAGE WATCHLIST
# ═══════════════════════════════════════════════
def flow_manage_watchlist():
    while True:
        wl = load_watchlist()
        console.print()
        console.print(Panel(
            f"  [bold cyan][A][/bold cyan] Add RC    [bold red][R][/bold red] Remove RC    [bold yellow][L][/bold yellow] List    [bold white][B][/bold white] Back",
            title="[bold]Watchlist Manager[/bold]",
            border_style="cyan",
            expand=False,
        ))

        choice = Prompt.ask("  Choice", choices=["a","r","l","b","A","R","L","B"]).lower()

        if choice == "b":
            break
        elif choice == "l":
            if not wl:
                console.print("  [dim]Watchlist empty.[/dim]")
            else:
                t = Table(box=box.SIMPLE_HEAD, header_style="bold magenta")
                t.add_column("#");  t.add_column("RC"); t.add_column("Label"); t.add_column("Interval")
                for i, (rc, meta) in enumerate(wl.items(), 1):
                    t.add_row(str(i), rc, meta.get("label","—"), f"{meta.get('interval_min',60)} min")
                console.print(t)
        elif choice == "a":
            rc_raw = Prompt.ask("  RC number")
            ok, rc = validate_rc(rc_raw)
            if not ok:
                print_error(rc)
                continue
            label = Prompt.ask("  Label (optional)", default=rc)
            interval = Prompt.ask("  Check interval (minutes)", default="60")
            wl[rc] = {"label": label, "interval_min": interval, "added": datetime.now().isoformat()}
            save_watchlist(wl)
            print_ok(f"[cyan]{rc}[/cyan] added to watchlist.")
        elif choice == "r":
            rc_raw = Prompt.ask("  RC to remove")
            _, rc = validate_rc(rc_raw)
            if rc in wl:
                del wl[rc]
                save_watchlist(wl)
                print_ok(f"[cyan]{rc}[/cyan] removed.")
            else:
                print_error(f"{rc} not in watchlist.")

# ═══════════════════════════════════════════════
#  FLOW: HTML REPORT
# ═══════════════════════════════════════════════
def flow_generate_report():
    result_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith(".json")]
    if not result_files:
        print_error("No results found. Run some lookups first.")
        return

    records = []
    for fname in sorted(result_files, reverse=True):
        try:
            with open(os.path.join(RESULTS_DIR, fname)) as f:
                d = json.load(f)
            records.append(d)
        except Exception:
            continue

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(REPORT_DIR, f"report_{timestamp}.html")

    rows_html = ""
    for rec in records:
        cells = "".join(
            f"<td>{k.replace('_',' ').title()}</td><td><b>{v}</b></td>"
            for k, v in rec.items()
        )
        rows_html += f"<tr>{cells}</tr>\n"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>INvehi-DT Report — {timestamp}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0d1117;color:#c9d1d9;font-family:'Segoe UI',monospace;padding:2rem}}
  h1{{color:#58a6ff;font-size:1.6rem;margin-bottom:.3rem}}
  .meta{{color:#8b949e;font-size:.85rem;margin-bottom:2rem}}
  .badge{{background:#21262d;border:1px solid #30363d;padding:.2rem .6rem;
          border-radius:4px;font-size:.75rem;color:#58a6ff;margin-right:.5rem}}
  table{{width:100%;border-collapse:collapse;margin-bottom:2rem;
         background:#161b22;border:1px solid #30363d;border-radius:8px;overflow:hidden}}
  th{{background:#1f6feb;color:#fff;padding:.6rem 1rem;text-align:left;font-size:.8rem;text-transform:uppercase}}
  td{{padding:.55rem 1rem;border-bottom:1px solid #21262d;font-size:.85rem}}
  tr:hover td{{background:#1c2128}}
  td:first-child{{color:#8b949e;font-size:.8rem}}
  td b{{color:#e6edf3}}
  .footer{{color:#484f58;font-size:.75rem;text-align:center;margin-top:2rem}}
</style>
</head>
<body>
<h1>◈ INvehi-DT Report</h1>
<p class="meta">
  <span class="badge">v{VERSION}</span>
  <span class="badge">by {AUTHOR}</span>
  <span class="badge">{len(records)} records</span>
  <span class="badge">{timestamp}</span>
</p>
{"".join(f'<table><thead><tr><th colspan="2">Record {i+1}</th></tr></thead><tbody>{r}</tbody></table>' for i, r in enumerate(rows_html.split("</tr>\n")[:-1]))}
<p class="footer">Generated by INvehi-DT {VERSION} · {AUTHOR} · For educational use only</p>
</body>
</html>"""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print_ok(f"HTML report saved → [dim]{report_path}[/dim]")
    console.print(f"  Open with: [bold]xdg-open {report_path}[/bold]\n")
    log(f"REPORT generated path={report_path}")

# ═══════════════════════════════════════════════
#  FLOW: HISTORY
# ═══════════════════════════════════════════════
def flow_history():
    history = load_history()
    if not history:
        console.print("\n  [dim]No query history yet.[/dim]\n")
        return

    table = Table(
        title="[bold cyan]Query History[/bold cyan]  [dim](last 20)[/dim]",
        box=box.SIMPLE_HEAD,
        border_style="cyan",
        header_style="bold magenta",
    )
    table.add_column("#",       style="dim",         width=4)
    table.add_column("Time",    style="dim white",    width=20)
    table.add_column("RC",      style="bold cyan",    width=16)
    table.add_column("Status",  style="bold")

    for i, line in enumerate(history[:20], 1):
        parts = line.split("  ")
        ts     = parts[0] if len(parts) > 0 else "—"
        rc     = parts[1].strip() if len(parts) > 1 else "—"
        status = parts[2].strip() if len(parts) > 2 else "—"
        style  = "green" if status == "OK" else "red"
        table.add_row(str(i), ts, rc, f"[{style}]{status}[/{style}]")

    console.print()
    console.print(table)

    total = len(history)
    ok    = sum(1 for l in history if "OK" in l)
    console.print(f"\n  [dim]Total queries: [bold]{total}[/bold]   Success: [bold green]{ok}[/bold green]   Failed: [bold red]{total-ok}[/bold red][/dim]\n")

# ═══════════════════════════════════════════════
#  FLOW: EXPORT ALL CSV
# ═══════════════════════════════════════════════
def flow_export_csv():
    csv_path = os.path.join(RESULTS_DIR, "all_results.csv")
    if not os.path.exists(csv_path):
        print_error("No CSV data yet. Run some lookups first.")
        return
    print_ok(f"CSV location → [dim]{csv_path}[/dim]")
    lines = open(csv_path).read().count("\n")
    console.print(f"  [dim]{lines-1} records in file.[/dim]\n")

# ═══════════════════════════════════════════════
#  FLOW: SYSTEM INFO
# ═══════════════════════════════════════════════
def flow_system_info():
    console.print()
    net_ok = check_connectivity()
    pub_ip = get_public_ip() if net_ok else "Offline"

    cache_files  = len([f for f in os.listdir(CACHE_DIR)   if f.endswith(".json")])
    result_files = len([f for f in os.listdir(RESULTS_DIR) if f.endswith(".json")])

    info = Table(box=box.SIMPLE, show_header=False, padding=(0,2))
    info.add_column(style="dim cyan", min_width=22)
    info.add_column(style="white")

    info.add_row("Tool",        f"[bold]{TOOL_NAME} {VERSION}[/bold]")
    info.add_row("Author",      f"[bold green]{AUTHOR}[/bold green]")
    info.add_row("Python",      platform.python_version())
    info.add_row("OS",          f"{platform.system()} {platform.release()}")
    info.add_row("Network",     "[bold green]Online[/bold green]" if net_ok else "[bold red]Offline[/bold red]")
    info.add_row("Public IP",   pub_ip)
    info.add_row("Cache files", str(cache_files))
    info.add_row("Result files",str(result_files))
    info.add_row("Data dir",    BASE_DIR)
    info.add_row("Log dir",     LOG_DIR)

    console.print(Panel(info, title="[bold cyan]System & Tool Info[/bold cyan]",
                        border_style="cyan", expand=False))
    console.print()

# ═══════════════════════════════════════════════
#  ARGPARSE
# ═══════════════════════════════════════════════
def parse_args():
    p = argparse.ArgumentParser(
        prog="invehidt",
        description="INvehi-DT v2.0 — Indian Vehicle OSINT Tool by DigitalTracez",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 invehidt.py
  python3 invehidt.py --rc MH01AB1234
  python3 invehidt.py --rc MH01AB1234 --json
  python3 invehidt.py --batch rc_list.txt
  python3 invehidt.py --decode MH01AB1234
  python3 invehidt.py --rc MH01AB1234 --no-cache
        """
    )
    p.add_argument("--rc",       metavar="RC",    help="Lookup single RC and exit")
    p.add_argument("--batch",    metavar="FILE",  help="Batch lookup from file")
    p.add_argument("--decode",   metavar="RC",    help="Decode RC number (no API call)")
    p.add_argument("--json",     action="store_true", help="Raw JSON output (with --rc)")
    p.add_argument("--no-cache", action="store_true", help="Force fresh API call")
    p.add_argument("--version",  action="store_true", help="Show version and exit")
    return p.parse_args()

# ═══════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════
def main():
    ensure_dirs()
    args = parse_args()

    if args.version:
        print(f"{TOOL_NAME} {VERSION} by {AUTHOR}")
        sys.exit(0)

    if args.decode:
        ok, rc = validate_rc(args.decode)
        if not ok:
            console.print(f"[red]Invalid RC[/red]")
            sys.exit(1)
        decoded = decode_rc(rc)
        print(json.dumps(decoded, indent=2))
        sys.exit(0)

    if args.rc:
        ok, rc = validate_rc(args.rc)
        if not ok:
            console.print(f"[red]Invalid RC:[/red] {rc}")
            sys.exit(1)
        data, from_cache, elapsed = fetch_vehicle_data(rc, skip_cache=args.no_cache)
        if "error" in data:
            console.print(f"[red]Error:[/red] {data['error']}")
            sys.exit(1)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            clear(); print_banner()
            print_result(rc, data, from_cache, elapsed)
            path = export_json(rc, data)
            print_ok(f"Saved → {path}")
        sys.exit(0)

    if args.batch:
        clear(); print_banner()
        # reuse interactive batch but from file path directly
        import types
        orig = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
        flow_batch_lookup_file(args.batch)
        sys.exit(0)

    # interactive
    clear()
    print_banner()

    while True:
        print_menu()
        choice = Prompt.ask(
            "  [bold cyan]Select[/bold cyan]",
            choices=[str(i) for i in range(10)],
            show_choices=False,
        )
        if   choice == "0": console.print("\n  [dim]Goodbye.[/dim]\n"); break
        elif choice == "1": flow_single_lookup()
        elif choice == "2": flow_batch_lookup()
        elif choice == "3": flow_live_monitor()
        elif choice == "4": flow_generate_report()
        elif choice == "5": flow_history()
        elif choice == "6": flow_decode_rc()
        elif choice == "7": flow_export_csv()
        elif choice == "8": flow_system_info()
        elif choice == "9": flow_manage_watchlist()


def flow_batch_lookup_file(filepath: str):
    if not os.path.exists(filepath):
        print_error(f"File not found: {filepath}"); return
    with open(filepath) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    console.print(f"\n  [dim]{len(lines)} entries.[/dim]\n")
    for raw in lines:
        ok, rc = validate_rc(raw)
        if not ok:
            console.print(f"  [yellow]SKIP[/yellow] {raw}"); continue
        console.print(f"  [cyan]>[/cyan] {rc} … ", end="")
        data, _, _ = fetch_vehicle_data(rc)
        if "error" in data:
            console.print(f"[red]FAIL[/red] {data['error']}")
        else:
            export_json(rc, data); export_csv_append(rc, data)
            console.print("[green]OK[/green]")
        time.sleep(REQUEST_DELAY)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n  [dim]Interrupted. Exiting.[/dim]\n")
        sys.exit(0)
