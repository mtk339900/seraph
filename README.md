# Seraph 🪽

**Python's guardian angel.** Seraph quietly fixes the five most painful recurring problems in everyday Python development — thread-unsafe resource cleanup, deep attribute access explosions, OS path fragility, silent hangs, and timezone hell — with a clean, zero-dependency API.

```python
from seraph import maybe, here, watch, now, managed
```

---

## Table of Contents

- [Installation](#installation)
- [Features](#features)
  - [1. `maybe` — Safe Optional Chaining](#1-maybe--safe-optional-chaining)
  - [2. `SmartPath` — OS-Agnostic Paths](#2-smartpath--os-agnostic-paths)
  - [3. `managed` — Thread-Safe Context Managers](#3-managed--thread-safe-context-managers)
  - [4. `watch` — Non-Invasive Hang Detector](#4-watch--non-invasive-hang-detector)
  - [5. `SmartTime` — Timezone-Aware Datetime](#5-smarttime--timezone-aware-datetime)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Requirements](#requirements)
- [License](#license)

---

## Installation

### From source (recommended for now)

```bash
git clone https://github.com/mtk339900/seraph.git
cd seraph
pip install -e .
```

### Direct copy

Drop the `seraph/` folder next to your script and import directly — no build step needed.

```
your_project/
├── seraph/          ← copy here
│   ├── __init__.py
│   ├── maybe.py
│   ├── threads.py
│   ├── paths.py
│   ├── watchdog.py
│   └── dt.py
└── your_script.py
```

---

## Features

---

### 1. `maybe` — Safe Optional Chaining

**The problem:** Accessing nested data from APIs or JSON requires defensive chains like:

```python
# Before — fragile and exhausting
if user and user.get("profile") and user["profile"].get("address"):
    city = user["profile"]["address"].get("city", "N/A")
else:
    city = "N/A"
```

**The solution:** `maybe()` wraps any value and lets you chain freely. Missing keys, `None` values, and missing attributes all silently return `None` — never raise.

```python
from seraph import maybe

city = maybe(user)["profile"]["address"]["city"].get("N/A")
```

#### Basic usage

```python
from seraph import maybe

api_response = {
    "data": {
        "user": {
            "name": "Mohammed",
            "profile": {
                "address": {"city": "Cairo", "zipcode": "11511"},
                "tier": "premium",
            }
        }
    }
}

# Deeply nested dict access
city    = maybe(api_response)["data"]["user"]["profile"]["address"]["city"].get("N/A")
country = maybe(api_response)["data"]["user"]["profile"]["address"]["country"].get("N/A")
# → "Cairo", "N/A"

# Works on None without crashing
result = maybe(None).anything.you.want.get("default")
# → "default"

# Object attribute chaining
email = maybe(user_obj).profile.contact.email.get("no-email@example.com")

# Transform with .apply()
tier = maybe(api_response)["data"]["user"]["profile"]["tier"].apply(str.upper).get()
# → "PREMIUM"

# Check existence
if maybe(response)["data"]["user"]["premium"].exists():
    unlock_features()

# Iterate safely over a list that might not exist
for item in maybe(response)["data"]["items"].each():
    print(item["name"].get("Unknown"))

# Chain with fallback
display_name = maybe(user).nickname.or_else(maybe(user).full_name).get("Guest")
```

#### `Maybe` API

| Method | Description |
|--------|-------------|
| `.get(default=None)` | Unwrap the value; return `default` if `None` |
| `.get_or_raise(exc)` | Unwrap or raise the given exception |
| `.exists()` | `True` if value is not `None` |
| `.apply(fn)` | Apply a function if value is not `None` |
| `.filter(predicate)` | Keep value only if predicate passes |
| `.or_else(fallback)` | Return self if not `None`, otherwise wrap fallback |
| `.each()` | Iterate over a list/iterable, each item wrapped in `Maybe` |
| `["key"]` | Safe dict/list access |
| `.attr` | Safe attribute access |
| `(args)` | Safe callable invocation |

---

### 2. `SmartPath` — OS-Agnostic Paths

**The problem:** `os.path.join`, wrong slashes on Windows, and paths relative to the terminal's `cwd` instead of the script's location.

```python
# Before — fragile
import os
base = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base, "config", "app.json")
with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)
```

**The solution:** `here()` always points to the calling script's directory. `/` joins paths on all OSes. Built-in read/write methods eliminate boilerplate.

```python
from seraph import here, SmartPath

config = (here() / "config" / "app.json").read_json()
```

#### Basic usage

```python
from seraph import here, SmartPath

# here() = directory of the current script (not the terminal)
base = here()

# Join paths with / (works on Windows and Linux)
config = base / "config" / "settings.json"
output = base / "output" / "results.txt"

# Read operations
text   = config.read()                      # str
data   = config.read_json()                 # dict/list
lines  = config.read_lines()                # list[str]
ini    = (base / "app.ini").read_config()   # ConfigParser
env    = (base / ".env").read_env()         # dict

# Write operations — parent dirs created automatically
output.write("Hello, world!")
output.write_json({"status": "ok", "count": 42})
(base / "logs" / "run.log").append("started\n")

# Directory listing
for f in here().ls("*.py"):
    print(f.name, f.size)

for f in here().ls_recursive("**/*.json"):
    print(f)

# Path metadata
p = base / "data.csv"
print(p.name)      # "data.csv"
print(p.stem)      # "data"
print(p.suffix)    # ".csv"
print(p.parent)    # SmartPath of parent dir
print(p.exists())  # bool
print(p.is_file()) # bool
print(p.size)      # int (bytes)

# Rename / retype
backup = p.with_suffix(".bak")
renamed = p.with_name("archive.csv")

# Class helpers
home = SmartPath.home()    # ~/
cwd  = SmartPath.cwd()     # current terminal directory
tmp  = SmartPath.temp()    # /tmp or C:\Users\...\AppData\Local\Temp
```

#### Works seamlessly with stdlib

`SmartPath` implements `__fspath__`, so it works anywhere Python expects a path:

```python
import pandas as pd
df = pd.read_csv(here() / "data" / "sales.csv")

import shutil
shutil.copy(here() / "template.docx", here() / "output" / "report.docx")
```

---

### 3. `managed` — Thread-Safe Context Managers

**The problem:** Opening a file or DB connection in the main thread, passing it to worker threads, and having it close before workers are done — or workers crashing and leaking the resource.

```python
# Before — resource can close while threads are still using it
with open("data.csv") as f:
    thread = threading.Thread(target=worker, args=(f,))
    thread.start()
# ← file closes HERE, thread may still be reading
```

**The solution:** `managed` uses reference counting. The resource stays open until every borrower (across all threads) has finished — then closes exactly once. `atexit` ensures cleanup even on crash.

```python
from seraph import managed

with managed(open("data.csv"), label="data") as res:
    for i in range(10):
        t = threading.Thread(target=worker, args=(res.borrow(),))
        t.start()
# ← resource closes after the last thread exits its borrow(), not here
```

#### Basic usage

```python
import threading
from seraph import managed

def process_chunk(borrow):
    with borrow as f:              # acquires a reference
        for line in f:
            handle(line)
    # ← reference released here

# Main thread opens the resource
with managed(open("huge_file.csv"), label="csv-reader") as res:

    threads = [
        threading.Thread(target=process_chunk, args=(res.borrow(),))
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

# File closes here, guaranteed, after all 4 threads have finished
```

#### With database connections

```python
import sqlite3
from seraph import managed

def run_query(borrow, sql):
    with borrow as conn:
        return conn.execute(sql).fetchall()

with managed(sqlite3.connect("app.db"), label="db") as res:
    threads = [
        threading.Thread(target=run_query, args=(res.borrow(), q))
        for q in queries
    ]
    # ... run threads
```

#### Explicit open/close (without `with`)

```python
res = managed(open("log.txt"), label="log").open()
spawn_workers(res)
res.close()   # closes after all borrows finish
```

#### As a decorator

```python
from seraph import thread_safe

@thread_safe(lambda: open("config.json"), label="config")
def load_config(file_handle):
    return json.load(file_handle)
```

#### `managed` API

| Method / Property | Description |
|-------------------|-------------|
| `with managed(cm) as res` | Open resource, get handle |
| `res.value` | The raw underlying resource |
| `res.borrow()` | Get a borrow-context for use in another thread |
| `res.open()` | Explicit open (alternative to `with`) |
| `res.close()` | Explicit close |
| `thread_safe(factory)` | Decorator that injects a managed resource |

---

### 4. `watch` — Non-Invasive Hang Detector

**The problem:** A script freezes silently. You don't know if it's in an infinite loop, waiting on a network call, or just slow.

```python
# Before — you have no idea what's happening
for record in million_records:
    result = maybe_hangs(record)   # ← frozen? where?
```

**The solution:** `watch()` starts a background monitor thread. It samples the call stack every 500ms. If the stack hasn't changed for `timeout` seconds, it prints a full hang report — **without stopping or interrupting your program**.

```python
from seraph import watch

with watch(timeout=5):
    for record in million_records:
        result = maybe_hangs(record)
# If stuck for 5s, you'll see exactly which line is frozen
```

#### Basic usage

```python
from seraph import watch

# Context manager
with watch(timeout=10):
    response = requests.get(url)    # if this hangs > 10s → report printed
    process(response)

# Decorator
@watch(timeout=15)
def sync_database():
    for table in tables:
        fetch_and_write(table)      # hang here? you'll see it

# Manual control
dog = watch(timeout=5)
dog.start()
do_work()
dog.stop()
```

#### Sample hang report

```
╔══════════════════════════════════════════════════════════════╗
║  [Seraph Watchdog] ⚠  Hang detected — 10.2s idle             ║
║  Thread: MainThread (id=140234)                              ║
╚══════════════════════════════════════════════════════════════╝

  Call stack (most recent call last):
    File "sync.py", line 18, in <module>
    File "sync.py", line 12, in sync_database
      result = db.execute(heavy_query)   ← likely stuck here
    File "db.py", line 47, in execute
      return self._conn.fetchall()
```

#### Custom hang handler

```python
from seraph import Watchdog, HangReport

def alert_slack(report: HangReport):
    send_slack_message(f"Script hung for {report.idle_seconds:.0f}s!")
    print(report.format())

with Watchdog(timeout=30, on_hang=alert_slack, repeat_after=60):
    run_etl_pipeline()
```

#### `watch` / `Watchdog` API

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout` | `float` | `10.0` | Seconds of no stack change before reporting |
| `poll_interval` | `float` | `0.5` | Stack sampling interval in seconds |
| `on_hang` | `Callable` | prints to stderr | Custom handler receiving a `HangReport` |
| `repeat_after` | `float` | `30.0` | Re-report if still hanging after N seconds; `0` = report once |

---

### 5. `SmartTime` — Timezone-Aware Datetime

**The problem:** Naive vs aware datetimes, `pytz` inconsistencies, silent UTC bugs when deploying to servers in different timezones.

```python
# Before — easy to get wrong silently
from datetime import datetime
import pytz

tz = pytz.timezone("Africa/Cairo")
now = datetime.now(tz)                          # ok
naive = datetime(2024, 3, 15, 12, 0)           # naive — time bomb
localized = tz.localize(naive)                  # ok but verbose
utc = localized.astimezone(pytz.utc)            # more boilerplate
```

**The solution:** `SmartTime` is always UTC internally. You never create a naive datetime by accident. Conversion, parsing, and arithmetic are one call each.

```python
from seraph import now, parse_time, days, hours

t = now("Africa/Cairo")         # always aware, always correct
```

#### Basic usage

```python
from seraph import now, parse_time, days, hours, minutes, weeks, SmartTime

# Current time
utc   = now()                       # UTC
cairo = now("Africa/Cairo")         # local display, UTC internally
riyadh = now("UTC+3")

# Parse — many formats supported, always returns aware SmartTime
t1 = parse_time("2025-06-15T09:30:00Z")
t2 = parse_time("15/06/2025 09:30:00")
t3 = parse_time("2025-06-15")
t4 = parse_time("2025-06-15 09:30", assume_tz="Africa/Cairo")

# Convert between timezones
cairo_time  = now().to("Africa/Cairo")
berlin_time = now().to("Europe/Berlin")
offset_time = now().to("UTC-5")

# Formatting
print(now().format())                   # "2025-06-15 18:30:00 UTC"
print(now().format("%d %B %Y"))         # "15 June 2025"
print(now().iso)                        # "2025-06-15T18:30:00+00:00"
print(now().date_str)                   # "2025-06-15"
print(now().time_str)                   # "18:30:00"
print(now().timestamp)                  # 1718472600.0

# Arithmetic
tomorrow   = now() + days(1)
next_week  = now() + weeks(1)
two_hours  = now() + hours(2)
yesterday  = now() - days(1)
in_30_min  = now() + minutes(30)

# Difference
delta = now() - parse_time("2025-01-01")
print(delta.days)   # int

# Human-readable diff
print(parse_time("2020-01-01").human_diff())   # "5 years ago"
print((now() + days(3)).human_diff())          # "in 3 days"
print((now() + hours(1)).human_diff())         # "in 1 hour"

# Comparisons
print(parse_time("2020-01-01").is_past())      # True
print((now() + days(1)).is_future())           # True
print(now() < now() + hours(1))               # True

# From UNIX timestamp
t = SmartTime.from_timestamp(1710000000)

# From components
t = SmartTime.from_date(2025, 6, 15, 9, 30, 0, tz="Africa/Cairo")
```

#### Supported timezone formats

```python
now().to("Africa/Cairo")      # IANA timezone name
now().to("Europe/London")
now().to("America/New_York")
now().to("UTC+3")             # offset shorthand
now().to("UTC-5")
now().to("UTC+5:30")          # with minutes
now().to("EST")               # common abbreviation
now().to("GMT")
```

#### `SmartTime` API

| Method / Property | Description |
|-------------------|-------------|
| `SmartTime.now(tz?)` | Current UTC time, optionally displayed in `tz` |
| `SmartTime.parse(s, assume_tz?)` | Parse datetime string |
| `SmartTime.from_timestamp(ts)` | From UNIX timestamp |
| `SmartTime.from_date(y,m,d,...)` | From explicit components |
| `.to(tz)` | Convert to timezone |
| `.format(fmt?)` | strftime string |
| `.iso` | ISO 8601 string |
| `.date_str` | `"YYYY-MM-DD"` |
| `.time_str` | `"HH:MM:SS"` |
| `.timestamp` | UNIX timestamp float |
| `.raw` | Underlying `datetime` object |
| `.is_past()` | `True` if before now |
| `.is_future()` | `True` if after now |
| `.age()` | `timedelta` since this time |
| `.human_diff(other?)` | Human-readable diff string |

---

## API Reference

### Quick import guide

```python
# All public symbols
from seraph import (
    # Optional chaining
    maybe, Maybe,

    # Paths
    here, SmartPath,

    # Threads
    managed, thread_safe,

    # Hang detection
    watch, Watchdog, HangReport,

    # Datetime
    now, parse_time, SmartTime,
    seconds, minutes, hours, days, weeks,
)
```

---

## Examples

See the [`examples/`](examples/) directory:

- [`examples/demo.py`](examples/demo.py) — Complete walkthrough of all five features

---

## Requirements

- **Python 3.8+**
- **Zero required dependencies** — uses only the standard library

Optional (for named timezone support in `SmartTime`):
- `zoneinfo` — built into Python 3.9+ (recommended)
- `pytz` — fallback for Python 3.8

```bash
# Only if you need named timezones on Python 3.8:
pip install pytz
```

---

## Project Structure

```
seraph/
├── README.md
├── setup.py
├── LICENSE
├── .gitignore
├── seraph/
│   ├── __init__.py     ← public API surface
│   ├── maybe.py        ← optional chaining
│   ├── threads.py      ← thread-safe context managers
│   ├── paths.py        ← smart path handling
│   ├── watchdog.py     ← hang detection
│   └── dt.py           ← timezone-aware datetime
├── examples/
│   └── demo.py
└── tests/
    └── test_seraph.py
```

---

## License

MIT — see [LICENSE](LICENSE).
