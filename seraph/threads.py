"""
seraph.threads — Safe Threaded Context Managers
================================================
Guarantees resource cleanup across thread boundaries.
No resource stays open even if the owning thread crashes or exits early.
"""

from __future__ import annotations

import atexit
import threading
import traceback
from contextlib import contextmanager
from typing import Any, Callable, Generic, Optional, TypeVar

T = TypeVar("T")

# Global registry: id(handle) -> _ResourceHandle
_registry: dict[int, "_ResourceHandle"] = {}
_registry_lock = threading.Lock()


def _atexit_cleanup() -> None:
    with _registry_lock:
        handles = list(_registry.values())
    for h in handles:
        h._force_close()


atexit.register(_atexit_cleanup)


class _ResourceHandle:
    """Internal tracker for a single context manager."""

    def __init__(self, cm: Any, label: str) -> None:
        self._cm = cm
        self._label = label
        self._ref_count = 0
        self._closed = False
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError(
                    f"[Seraph] Resource '{self._label}' is already closed."
                )
            self._ref_count += 1

    def release(self, exc_type=None, exc_val=None, exc_tb=None) -> None:
        should_close = False
        with self._lock:
            self._ref_count -= 1
            if self._ref_count <= 0 and not self._closed:
                should_close = True
        if should_close:
            self._do_close(exc_type, exc_val, exc_tb)

    def _do_close(self, exc_type=None, exc_val=None, exc_tb=None) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            self._cm.__exit__(exc_type, exc_val, exc_tb)
        except Exception:
            pass
        finally:
            _id = id(self)
            with _registry_lock:
                _registry.pop(_id, None)

    def _force_close(self) -> None:
        self._do_close()


class managed(Generic[T]):
    """
    Thread-safe context manager with reference counting.

    Wraps any context manager and defers cleanup until ALL borrowers
    (across any number of threads) have finished — then cleans up exactly once.

    Usage
    -----
    # Main thread opens the resource
    with managed(open("data.txt"), label="data-file") as res:
        file_obj = res.value

        def worker():
            with res.borrow() as f:          # thread gets a borrow
                for line in f:
                    process(line)

        t = threading.Thread(target=worker)
        t.start()
    # ← main thread exits 'with' block; file stays open while worker runs
    # ← file closes automatically when the last borrow exits

    Also works as a standalone guard (no with-block needed):

        res = managed(open("log.txt")).open()
        spawn_threads(res)
        res.close()                          # explicit close when done
    """

    def __init__(self, context_manager: Any, label: str = "") -> None:
        self._cm = context_manager
        self._label = label or repr(context_manager)
        self._handle: Optional[_ResourceHandle] = None
        self._value: Optional[T] = None

    # ── context manager protocol ──────────────────────────────────────────────

    def __enter__(self) -> "managed[T]":
        self._value = self._cm.__enter__()
        self._handle = _ResourceHandle(self._cm, self._label)
        self._handle.acquire()          # count the "owner" reference
        with _registry_lock:
            _registry[id(self._handle)] = self._handle
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._handle:
            self._handle.release(exc_type, exc_val, exc_tb)
        return False

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def value(self) -> T:
        """The raw resource (file handle, connection, …)."""
        if self._value is None:
            raise RuntimeError(
                "[Seraph] Resource not opened yet. Use as context manager or call .open() first."
            )
        return self._value

    def borrow(self) -> "_Borrow[T]":
        """
        Get a borrow-handle for use in another thread.

            with res.borrow() as f:
                f.read()
        """
        if self._handle is None:
            raise RuntimeError("[Seraph] Cannot borrow from an unopened managed resource.")
        return _Borrow(self._handle, self._value)

    def open(self) -> "managed[T]":
        """Explicit open (alternative to `with` statement)."""
        return self.__enter__()

    def close(self) -> None:
        """Explicit close (alternative to `with` statement exit)."""
        self.__exit__(None, None, None)

    def __repr__(self) -> str:
        status = "open" if (self._handle and not self._handle._closed) else "closed"
        refs = self._handle._ref_count if self._handle else 0
        return f"managed({self._label!r}, status={status}, refs={refs})"


class _Borrow(Generic[T]):
    """A single borrow of a managed resource for use in one thread."""

    def __init__(self, handle: _ResourceHandle, value: T) -> None:
        self._handle = handle
        self._value = value

    def __enter__(self) -> T:
        self._handle.acquire()
        return self._value

    def __exit__(self, *args):
        self._handle.release(*args)
        return False


# ── Convenience decorator ─────────────────────────────────────────────────────

def thread_safe(context_manager_factory: Callable[[], Any], label: str = ""):
    """
    Decorator that opens a managed resource before the function runs
    and injects it as the first argument.

        @thread_safe(lambda: open("log.txt"), label="log")
        def my_function(log_file, ...):
            ...
    """
    def decorator(fn: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            with managed(context_manager_factory(), label=label) as res:
                return fn(res.value, *args, **kwargs)
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        return wrapper
    return decorator
