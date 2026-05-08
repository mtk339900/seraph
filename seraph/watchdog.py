"""
seraph.watchdog — Non-invasive Hang Detector
==============================================
Detects infinite loops, frozen I/O, and silent hangs with zero overhead
when things are running normally. One line to activate.
"""

from __future__ import annotations

import sys
import threading
import time
import traceback
from typing import Callable, Optional


class Watchdog:
    """
    Monitors a thread for progress. If the call stack hasn't changed for
    `timeout` seconds, prints a live report directly to the terminal —
    WITHOUT stopping or interrupting the program.

    Usage — context manager:
    -------------------------
        with watch(timeout=5):
            for item in huge_list:
                process(item)          # if this hangs, you'll know exactly where

    Usage — decorator:
    ------------------
        @watch(timeout=10)
        def fetch_data():
            response = requests.get(url)   # if this hangs, stack is printed

    Usage — manual:
    ---------------
        dog = Watchdog(timeout=5)
        dog.start()
        do_stuff()
        dog.stop()

    Report format printed when a hang is detected:
    -----------------------------------------------
        ╔══════════════════════════════════════════════╗
        ║  [Seraph Watchdog] Hang detected — 5.2s idle ║
        ╠══════════════════════════════════════════════╣
        ║  Thread: MainThread (id=12345)               ║
        ╚══════════════════════════════════════════════╝
          File "script.py", line 42, in process
            result = db.query(sql)         ← stuck here
          ...full stack trace...
    """

    def __init__(
        self,
        timeout: float = 10.0,
        poll_interval: float = 0.5,
        on_hang: Optional[Callable[["HangReport"], None]] = None,
        repeat_after: float = 30.0,
    ) -> None:
        """
        Parameters
        ----------
        timeout       : Seconds of no stack change before reporting.
        poll_interval : How often to sample the stack (default 0.5s).
        on_hang       : Custom callback receiving a HangReport. If None, prints to stderr.
        repeat_after  : Re-report if still hanging after this many seconds (0 = report once).
        """
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.on_hang = on_hang or _default_report
        self.repeat_after = repeat_after

        self._watched_thread_id: Optional[int] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self, thread_id: Optional[int] = None) -> "Watchdog":
        """Start watching. Defaults to current thread."""
        self._watched_thread_id = thread_id or threading.current_thread().ident
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="SeraphWatchdog",
        )
        self._monitor_thread.start()
        return self

    def stop(self) -> None:
        """Stop the watchdog."""
        self._running = False

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "Watchdog":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()

    # ── Decorator ─────────────────────────────────────────────────────────────

    def __call__(self, fn: Callable) -> Callable:
        """Allow use as @Watchdog(timeout=5) decorator."""
        def wrapper(*args, **kwargs):
            with Watchdog(
                timeout=self.timeout,
                poll_interval=self.poll_interval,
                on_hang=self.on_hang,
                repeat_after=self.repeat_after,
            ):
                return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        return wrapper

    # ── Core monitoring loop ──────────────────────────────────────────────────

    def _loop(self) -> None:
        last_sig: Optional[tuple] = None
        last_change = time.monotonic()
        last_report = 0.0

        while self._running:
            time.sleep(self.poll_interval)
            if not self._running:
                break

            sig = _stack_signature(self._watched_thread_id)
            now = time.monotonic()

            if sig != last_sig:
                last_sig = sig
                last_change = now
            else:
                idle = now - last_change
                if idle >= self.timeout:
                    # Only report once, then re-report after repeat_after
                    if self.repeat_after == 0 and last_report > 0:
                        continue
                    if last_report > 0 and (now - last_report) < self.repeat_after:
                        continue

                    frame = sys._current_frames().get(self._watched_thread_id)
                    thread_name = _thread_name(self._watched_thread_id)
                    report = HangReport(
                        thread_id=self._watched_thread_id,
                        thread_name=thread_name,
                        idle_seconds=idle,
                        stack_frames=_extract_frames(frame),
                        timeout=self.timeout,
                    )
                    self.on_hang(report)
                    last_report = now


# ── HangReport dataclass ──────────────────────────────────────────────────────

class HangReport:
    """All information about a detected hang."""

    def __init__(
        self,
        thread_id: int,
        thread_name: str,
        idle_seconds: float,
        stack_frames: list,
        timeout: float,
    ) -> None:
        self.thread_id = thread_id
        self.thread_name = thread_name
        self.idle_seconds = idle_seconds
        self.stack_frames = stack_frames    # list of (filename, lineno, name, line)
        self.timeout = timeout

    def format(self) -> str:
        lines = []
        w = 62
        bar = "═" * w
        lines.append(f"\n╔{bar}╗")
        msg = f"  [Seraph Watchdog] ⚠  Hang detected — {self.idle_seconds:.1f}s idle"
        lines.append(f"║{msg:<{w}}║")
        sub = f"  Thread: {self.thread_name} (id={self.thread_id})"
        lines.append(f"║{sub:<{w}}║")
        lines.append(f"╚{bar}╝")
        lines.append("")

        if self.stack_frames:
            lines.append("  Call stack (most recent call last):")
            for filename, lineno, name, text in self.stack_frames:
                lines.append(f'    File "{filename}", line {lineno}, in {name}')
                if text:
                    lines.append(f"      {text.strip()}   ← likely stuck here")
        else:
            lines.append("  (no stack available)")

        lines.append("")
        return "\n".join(lines)


# ── Default report handler ────────────────────────────────────────────────────

def _default_report(report: HangReport) -> None:
    sys.stderr.write(report.format())
    sys.stderr.flush()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stack_signature(thread_id: int) -> Optional[tuple]:
    """Stable hashable snapshot of a thread's call stack."""
    frame = sys._current_frames().get(thread_id)
    if frame is None:
        return None
    stack = []
    f = frame
    while f is not None:
        stack.append((f.f_code.co_filename, f.f_lineno, f.f_code.co_name))
        f = f.f_back
    return tuple(stack)


def _extract_frames(frame) -> list:
    """Extract (filename, lineno, name, source_line) tuples."""
    if frame is None:
        return []
    result = []
    import linecache
    f = frame
    while f is not None:
        filename = f.f_code.co_filename
        lineno = f.f_lineno
        name = f.f_code.co_name
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno, f.f_globals)
        result.append((filename, lineno, name, line))
        f = f.f_back
    result.reverse()
    return result


def _thread_name(thread_id: int) -> str:
    for t in threading.enumerate():
        if t.ident == thread_id:
            return t.name
    return f"Thread-{thread_id}"


# ── Public factory ────────────────────────────────────────────────────────────

def watch(timeout: float = 10.0, repeat_after: float = 30.0) -> Watchdog:
    """
    Create a Watchdog. Use as context manager or decorator.

        with watch(timeout=5):
            slow_operation()

        @watch(timeout=10)
        def risky_loop():
            ...
    """
    return Watchdog(timeout=timeout, repeat_after=repeat_after)
