"""
seraph.dt — Smart Datetime Handling
=====================================
Always timezone-aware. No naive datetimes. No pytz confusion.
Understands your intent so you stop fighting UTC offsets.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

# Try modern zoneinfo (Python 3.9+), fall back to pytz, then UTC-only mode
try:
    from zoneinfo import ZoneInfo, available_timezones
    _HAS_ZONEINFO = True
except ImportError:
    _HAS_ZONEINFO = False

try:
    import pytz as _pytz
    _HAS_PYTZ = True
except ImportError:
    _HAS_PYTZ = False


_TZ_FORMATS = [
    # ISO 8601 with timezone
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    # ISO 8601 UTC suffix
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    # ISO without timezone (assumed UTC)
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    # Human-readable
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    # Arabic/European format
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    # US format
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y",
]

_UTC = timezone.utc


class SmartTime:
    """
    A timezone-aware datetime that just works.

    Rules
    -----
    - Internally ALWAYS stored as UTC.
    - Input naive datetimes are assumed UTC (no silent surprises).
    - .to("Africa/Cairo"), .to("UTC+3"), .to("EST") for conversion.
    - Arithmetic with timedelta works naturally.
    - Comparison between SmartTimes always correct (both in UTC).

    Examples
    --------
        t = now()                           # current UTC time
        t = now("Africa/Cairo")             # current Cairo time
        t = parse_time("2024-03-15 14:30")  # parsed, stored as UTC
        t = SmartTime.from_timestamp(1710000000)

        cairo = t.to("Africa/Cairo")
        print(cairo.format())               # "2024-03-10 22:00:00 EET"
        print(cairo.format("%d %b %Y"))     # "10 Mar 2024"

        diff = now() - parse_time("2024-01-01")
        print(diff.days)                    # days since new year

        tomorrow = now() + hours(24)
        yesterday = now() - days(1)

        print(now().iso)                    # "2024-03-10T19:00:00+00:00"
        print(now().date_str)               # "2024-03-10"
        print(now().time_str)               # "19:00:00"
    """

    __slots__ = ("_dt",)

    def __init__(self, dt: datetime) -> None:
        if not isinstance(dt, datetime):
            raise TypeError(f"[Seraph] SmartTime requires a datetime, got {type(dt).__name__}")
        if dt.tzinfo is None:
            # Naive → assume UTC, never silently wrong
            object.__setattr__(self, "_dt", dt.replace(tzinfo=_UTC))
        else:
            object.__setattr__(self, "_dt", dt.astimezone(_UTC))

    # ── Constructors ──────────────────────────────────────────────────────────

    @classmethod
    def now(cls, tz: Optional[str] = None) -> "SmartTime":
        """
        Current time. Optionally in a specific timezone for display only
        (still stored as UTC internally).

            now_utc   = SmartTime.now()
            now_cairo = SmartTime.now("Africa/Cairo")
        """
        t = cls(datetime.now(_UTC))
        return t.to(tz) if tz else t

    @classmethod
    def parse(cls, s: str, assume_tz: Optional[str] = None) -> "SmartTime":
        """
        Parse a datetime string in many common formats.

            SmartTime.parse("2024-03-15")
            SmartTime.parse("15/03/2024 14:30:00")
            SmartTime.parse("2024-03-15T10:00:00Z")
            SmartTime.parse("2024-03-15 10:00", assume_tz="Africa/Cairo")
        """
        s = s.strip()

        # Handle "Z" suffix as UTC before strptime
        normalized = s.replace("Z", "+00:00")

        for fmt in _TZ_FORMATS:
            try:
                dt = datetime.strptime(s, fmt)
                result = cls(dt)
                # If parsed as naive and caller specified a tz, use it
                if dt.tzinfo is None and assume_tz:
                    tz_obj = _resolve_tz(assume_tz)
                    dt_aware = dt.replace(tzinfo=tz_obj)
                    return cls(dt_aware)
                return result
            except ValueError:
                continue

        # Try fromisoformat as last resort (Python 3.7+)
        try:
            return cls(datetime.fromisoformat(normalized))
        except ValueError:
            pass

        raise ValueError(
            f"[Seraph] Cannot parse datetime string: {s!r}\n"
            f"Supported formats include: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SSZ, DD/MM/YYYY HH:MM:SS, ..."
        )

    @classmethod
    def from_timestamp(cls, ts: Union[int, float]) -> "SmartTime":
        """Create from a UNIX timestamp."""
        return cls(datetime.fromtimestamp(ts, tz=_UTC))

    @classmethod
    def from_date(cls, year: int, month: int, day: int,
                  hour: int = 0, minute: int = 0, second: int = 0,
                  tz: Optional[str] = None) -> "SmartTime":
        """Create from explicit date/time components."""
        tz_obj = _resolve_tz(tz) if tz else _UTC
        dt = datetime(year, month, day, hour, minute, second, tzinfo=tz_obj)
        return cls(dt)

    # ── Conversion ────────────────────────────────────────────────────────────

    def to(self, tz: str) -> "SmartTime":
        """
        Convert to a different timezone.

            t.to("Africa/Cairo")     # named IANA timezone
            t.to("UTC+3")            # offset shorthand
            t.to("UTC-5")
            t.to("EST")              # common abbreviations

        Returns a new SmartTime (still stored as UTC internally,
        but display/format methods will use the given timezone).
        """
        tz_obj = _resolve_tz(tz)
        new_dt = self._dt.astimezone(tz_obj)
        return _SmartTimeInTz(new_dt)

    def as_utc(self) -> "SmartTime":
        """Return a copy explicitly in UTC."""
        return SmartTime(self._dt)

    # ── Output ────────────────────────────────────────────────────────────────

    def format(self, fmt: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
        """Format as string using strftime format codes."""
        return self._dt.strftime(fmt)

    @property
    def iso(self) -> str:
        """ISO 8601 string. e.g. '2024-03-10T19:00:00+00:00'"""
        return self._dt.isoformat()

    @property
    def date_str(self) -> str:
        """Date only. e.g. '2024-03-10'"""
        return self._dt.strftime("%Y-%m-%d")

    @property
    def time_str(self) -> str:
        """Time only. e.g. '19:00:00'"""
        return self._dt.strftime("%H:%M:%S")

    @property
    def timestamp(self) -> float:
        """UNIX timestamp (seconds since epoch)."""
        return self._dt.timestamp()

    @property
    def raw(self) -> datetime:
        """The underlying timezone-aware datetime object (UTC)."""
        return self._dt

    # ── Arithmetic ────────────────────────────────────────────────────────────

    def __add__(self, delta: timedelta) -> "SmartTime":
        return SmartTime(self._dt + delta)

    def __radd__(self, delta: timedelta) -> "SmartTime":
        return self.__add__(delta)

    def __sub__(self, other: Union["SmartTime", timedelta]):
        if isinstance(other, SmartTime):
            return self._dt - other._dt   # returns timedelta
        if isinstance(other, timedelta):
            return SmartTime(self._dt - other)
        return NotImplemented

    # ── Comparison ────────────────────────────────────────────────────────────

    def __eq__(self, other) -> bool:
        if isinstance(other, SmartTime):
            return self._dt == other._dt
        return NotImplemented

    def __lt__(self, other: "SmartTime") -> bool:
        return self._dt < other._dt

    def __le__(self, other: "SmartTime") -> bool:
        return self._dt <= other._dt

    def __gt__(self, other: "SmartTime") -> bool:
        return self._dt > other._dt

    def __ge__(self, other: "SmartTime") -> bool:
        return self._dt >= other._dt

    def __hash__(self) -> int:
        return hash(self._dt)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def is_past(self) -> bool:
        return self._dt < datetime.now(_UTC)

    def is_future(self) -> bool:
        return self._dt > datetime.now(_UTC)

    def age(self) -> timedelta:
        """How long ago this time was. Negative if in the future."""
        return datetime.now(_UTC) - self._dt

    def human_diff(self, other: Optional["SmartTime"] = None) -> str:
        """
        Human-readable time difference.
            '3 seconds ago', 'in 2 hours', 'yesterday', '3 months ago'
        """
        ref = other._dt if other else datetime.now(_UTC)
        delta = ref - self._dt
        total_seconds = delta.total_seconds()
        future = total_seconds < 0
        total_seconds = abs(total_seconds)

        def fmt(value: float, unit: str) -> str:
            n = round(value)
            label = f"{n} {unit}{'s' if n != 1 else ''}"
            return f"in {label}" if future else f"{label} ago"

        if total_seconds < 60:
            return fmt(total_seconds, "second")
        if total_seconds < 3600:
            return fmt(total_seconds / 60, "minute")
        if total_seconds < 86400:
            return fmt(total_seconds / 3600, "hour")
        if total_seconds < 86400 * 2:
            return "tomorrow" if future else "yesterday"
        if total_seconds < 86400 * 30:
            return fmt(total_seconds / 86400, "day")
        if total_seconds < 86400 * 365:
            return fmt(total_seconds / (86400 * 30), "month")
        return fmt(total_seconds / (86400 * 365), "year")

    def __str__(self) -> str:
        return self.format()

    def __repr__(self) -> str:
        return f"SmartTime({self.iso!r})"


class _SmartTimeInTz(SmartTime):
    """SmartTime variant that remembers a display timezone."""

    def __init__(self, dt_in_tz) -> None:
        object.__setattr__(self, "_dt", dt_in_tz)

    def format(self, fmt: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
        return self._dt.strftime(fmt)

    @property
    def iso(self) -> str:
        return self._dt.isoformat()

    def as_utc(self) -> "SmartTime":
        return SmartTime(self._dt.astimezone(_UTC))

# ── Timezone resolver ─────────────────────────────────────────────────────────

_TZ_ALIASES = {
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "GMT": "UTC",
    "EET": "Europe/Helsinki",
    "CET": "Europe/Paris",
    "IST": "Asia/Kolkata",
    "JST": "Asia/Tokyo",
    "AEST": "Australia/Sydney",
    "CAT": "Africa/Cairo",
    "EAT": "Africa/Nairobi",
    "WAT": "Africa/Lagos",
}

_UTC_OFFSET_RE = re.compile(r"UTC([+-])(\d{1,2})(?::(\d{2}))?$", re.IGNORECASE)


def _resolve_tz(tz_str: str):
    """Resolve a timezone string to a tzinfo object."""
    if tz_str.upper() == "UTC":
        return _UTC

    # Handle UTC+N / UTC-N
    m = _UTC_OFFSET_RE.match(tz_str)
    if m:
        sign = 1 if m.group(1) == "+" else -1
        h = int(m.group(2))
        mins = int(m.group(3) or 0)
        return timezone(timedelta(hours=h * sign, minutes=mins * sign))

    # Normalize aliases
    canonical = _TZ_ALIASES.get(tz_str.upper(), tz_str)

    if _HAS_ZONEINFO:
        try:
            return ZoneInfo(canonical)
        except Exception:
            pass

    if _HAS_PYTZ:
        try:
            return _pytz.timezone(canonical)
        except Exception:
            pass

    raise ValueError(
        f"[Seraph] Unknown timezone: {tz_str!r}. "
        f"Install 'zoneinfo' (Python 3.9+) or 'pytz' for named timezone support."
    )


# ── Timedelta convenience constructors ────────────────────────────────────────

def seconds(n: float) -> timedelta:
    return timedelta(seconds=n)

def minutes(n: float) -> timedelta:
    return timedelta(minutes=n)

def hours(n: float) -> timedelta:
    return timedelta(hours=n)

def days(n: float) -> timedelta:
    return timedelta(days=n)

def weeks(n: float) -> timedelta:
    return timedelta(weeks=n)


# ── Public API ────────────────────────────────────────────────────────────────

def now(tz: Optional[str] = None) -> SmartTime:
    """Current time. Optionally in a specific timezone."""
    return SmartTime.now(tz)

def parse_time(s: str, assume_tz: Optional[str] = None) -> SmartTime:
    """Parse a datetime string. Optional `assume_tz` for naive strings."""
    return SmartTime.parse(s, assume_tz=assume_tz)
