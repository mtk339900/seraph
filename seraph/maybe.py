"""
seraph.maybe — Safe Optional Chaining
======================================
Access deeply nested attributes and keys without if-chains or AttributeErrors.
Inspired by JavaScript's ?. operator and Swift's Optional chaining.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator, TypeVar, Union

_MISSING = object()  # sentinel for "no default given"

T = TypeVar("T")


class Maybe:
    """
    A wrapper that makes any value safely navigable.

    Access attributes, keys, indices, and call methods freely.
    Nothing raises — if any step is missing or None, the whole chain
    becomes Maybe(None), and .get() returns your default.

    Examples
    --------
    Basic attribute chain:
        user = {"profile": {"address": {"zipcode": "12345"}}}
        maybe(user)["profile"]["address"]["zipcode"].get()
        # → "12345"

        maybe(user)["profile"]["address"]["country"].get("N/A")
        # → "N/A"  (key missing, no exception)

    Object attribute chain:
        maybe(user).profile.address.zipcode.get()

    Mixed: dict + attribute + index:
        maybe(response).data["results"][0].name.get("Unknown")

    Conditional transform:
        maybe(user).profile.email.apply(str.upper).get()

    Check presence:
        if maybe(user).profile.premium:        # truthy if not None/False/0/""
            ...

        maybe(user).profile.tier.exists()      # True if not None
    """

    __slots__ = ("_value",)

    def __init__(self, value: Any) -> None:
        object.__setattr__(self, "_value", value)

    # ── Attribute access ──────────────────────────────────────────────────────

    def __getattr__(self, name: str) -> "Maybe":
        # Guard internal names
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        val = object.__getattribute__(self, "_value")
        if val is None:
            return _NONE
        try:
            return Maybe(getattr(val, name))
        except AttributeError:
            return _NONE

    # ── Item access (dict keys, list indices, etc.) ───────────────────────────

    def __getitem__(self, key: Any) -> "Maybe":
        val = object.__getattribute__(self, "_value")
        if val is None:
            return _NONE
        try:
            return Maybe(val[key])
        except (KeyError, IndexError, TypeError):
            return _NONE

    # ── Callable support ──────────────────────────────────────────────────────

    def __call__(self, *args: Any, **kwargs: Any) -> "Maybe":
        val = object.__getattribute__(self, "_value")
        if val is None:
            return _NONE
        if not callable(val):
            return _NONE
        try:
            return Maybe(val(*args, **kwargs))
        except Exception:
            return _NONE

    # ── Unwrapping ────────────────────────────────────────────────────────────

    def get(self, default: Any = None) -> Any:
        """
        Unwrap the value. Returns `default` if value is None.

            maybe(user).profile.address.city.get("Unknown City")
        """
        val = object.__getattribute__(self, "_value")
        return val if val is not None else default

    def get_or_raise(self, exc: Exception = None) -> Any:
        """
        Unwrap or raise if None.

            uid = maybe(user).profile.id.get_or_raise(ValueError("No user ID"))
        """
        val = object.__getattribute__(self, "_value")
        if val is None:
            raise exc or ValueError("[Seraph] Maybe chain resolved to None")
        return val

    def exists(self) -> bool:
        """True if the wrapped value is not None."""
        return object.__getattribute__(self, "_value") is not None

    # ── Transformation ────────────────────────────────────────────────────────

    def apply(self, fn: Callable[[Any], Any]) -> "Maybe":
        """
        Apply a function to the value if it's not None.

            maybe(user).name.apply(str.upper).get()
        """
        val = object.__getattribute__(self, "_value")
        if val is None:
            return _NONE
        try:
            return Maybe(fn(val))
        except Exception:
            return _NONE

    def filter(self, predicate: Callable[[Any], bool]) -> "Maybe":
        """
        Keep value only if predicate returns True; otherwise None.

            maybe(score).filter(lambda s: s >= 0).get(0)
        """
        val = object.__getattribute__(self, "_value")
        if val is None:
            return _NONE
        try:
            return self if predicate(val) else _NONE
        except Exception:
            return _NONE

    def or_else(self, fallback: Any) -> "Maybe":
        """
        Return this Maybe if not None, otherwise wrap `fallback`.

            display = maybe(user).nickname.or_else(maybe(user).full_name).get("Guest")
        """
        val = object.__getattribute__(self, "_value")
        if val is not None:
            return self
        if isinstance(fallback, Maybe):
            return fallback
        return Maybe(fallback)

    # ── Iteration support ─────────────────────────────────────────────────────

    def each(self) -> Iterator["Maybe"]:
        """
        Iterate over a list/tuple/set value, wrapping each item in Maybe.

            for item in maybe(response).results.each():
                print(item.name.get("—"))
        """
        val = object.__getattribute__(self, "_value")
        if val is None:
            return
        try:
            for item in val:
                yield Maybe(item)
        except TypeError:
            yield Maybe(val)  # treat scalar as single-item

    # ── Boolean / truthiness ─────────────────────────────────────────────────

    def __bool__(self) -> bool:
        val = object.__getattribute__(self, "_value")
        return bool(val) if val is not None else False

    # ── Repr ─────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        val = object.__getattribute__(self, "_value")
        return f"Maybe({val!r})"

    def __str__(self) -> str:
        val = object.__getattribute__(self, "_value")
        return str(val) if val is not None else ""

    # ── Comparison helpers ────────────────────────────────────────────────────

    def __eq__(self, other: Any) -> bool:
        val = object.__getattribute__(self, "_value")
        if isinstance(other, Maybe):
            return val == object.__getattribute__(other, "_value")
        return val == other


# Singleton for None cases (avoids repeated Maybe(None) allocations)
_NONE = Maybe(None)


def maybe(value: Any) -> Maybe:
    """
    Entry point: wrap any value in a Maybe for safe chaining.

        result = maybe(api_response).data.users[0].profile.email.get("no-email@example.com")
    """
    return Maybe(value)
