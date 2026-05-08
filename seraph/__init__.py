"""
Seraph — Python's guardian angel.
===================================
Fixes Python's 5 most painful developer experiences:

  1. threads  — Safe cross-thread context managers with guaranteed cleanup
  2. maybe    — Optional chaining (like JS ?.) for nested attributes/keys
  3. paths    — Smart OS-agnostic path handling with built-in read/write
  4. watchdog — Non-invasive hang/infinite-loop detector (1 line to add)
  5. dt       — Timezone-aware datetime that forces correctness

Quick start
-----------
    from seraph import maybe, here, watch, now, managed

    # Safe optional chaining
    email = maybe(api_response).data.user.contact.email.get("N/A")

    # Script-relative paths
    config = (here() / "config.json").read_json()

    # Hang detection
    with watch(timeout=5):
        for row in huge_dataset:
            process(row)

    # Datetime with timezones
    t = now("Africa/Cairo")
    print(t.human_diff())   # "just now"

    # Thread-safe resources
    with managed(open("data.csv"), label="data") as res:
        spawn_workers(res)  # each worker uses res.borrow()
"""

from .dt import (
    SmartTime,
    days,
    hours,
    minutes,
    now,
    parse_time,
    seconds,
    weeks,
)
from .maybe import Maybe, maybe
from .paths import SmartPath, here
from .threads import managed, thread_safe
from .watchdog import HangReport, Watchdog, watch

__version__ = "1.0.0"
__author__ = "Seraph"
__license__ = "MIT"

__all__ = [
    # Threads
    "managed",
    "thread_safe",
    # Maybe / safe chaining
    "Maybe",
    "maybe",
    # Smart paths
    "SmartPath",
    "here",
    # Watchdog
    "Watchdog",
    "HangReport",
    "watch",
    # Datetime
    "SmartTime",
    "now",
    "parse_time",
    "seconds",
    "minutes",
    "hours",
    "days",
    "weeks",
]
