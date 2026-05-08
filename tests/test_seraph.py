"""
tests/test_seraph.py
====================
Unit tests for all five Seraph modules.
Run with: python -m pytest tests/ -v
"""

import sys
import os
import threading
import time
import io
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# maybe
# ─────────────────────────────────────────────────────────────────────────────

from seraph import maybe, Maybe


class TestMaybe:

    def test_basic_dict_access(self):
        d = {"a": {"b": {"c": 42}}}
        assert maybe(d)["a"]["b"]["c"].get() == 42

    def test_missing_key_returns_default(self):
        assert maybe({"a": 1})["b"].get("default") == "default"

    def test_none_root_returns_default(self):
        assert maybe(None).x.y.z.get("fallback") == "fallback"

    def test_attribute_chain(self):
        class Inner:
            city = "Cairo"
        class Outer:
            address = Inner()

        result = maybe(Outer()).address.city.get()
        assert result == "Cairo"

    def test_missing_attribute_returns_default(self):
        class Obj:
            x = 1
        assert maybe(Obj()).y.get("N/A") == "N/A"

    def test_apply_transform(self):
        result = maybe("hello").apply(str.upper).get()
        assert result == "HELLO"

    def test_apply_on_none(self):
        result = maybe(None).apply(str.upper).get("default")
        assert result == "default"

    def test_filter_passes(self):
        result = maybe(10).filter(lambda x: x > 5).get(0)
        assert result == 10

    def test_filter_fails(self):
        result = maybe(3).filter(lambda x: x > 5).get(0)
        assert result == 0

    def test_or_else(self):
        result = maybe(None).or_else("fallback").get()
        assert result == "fallback"

    def test_or_else_prefers_original(self):
        result = maybe("original").or_else("fallback").get()
        assert result == "original"

    def test_exists_true(self):
        assert maybe(42).exists() is True

    def test_exists_false(self):
        assert maybe(None).exists() is False

    def test_each_over_list(self):
        items = maybe([1, 2, 3]).each()
        values = [i.get() for i in items]
        assert values == [1, 2, 3]

    def test_each_over_none(self):
        result = list(maybe(None).each())
        assert result == []

    def test_callable(self):
        fn = lambda x: x * 2
        result = maybe(fn)(5).get()
        assert result == 10

    def test_get_or_raise(self):
        with pytest.raises(ValueError):
            maybe(None).get_or_raise(ValueError("missing"))

    def test_bool_truthy(self):
        assert bool(maybe(1)) is True
        assert bool(maybe("x")) is True

    def test_bool_falsy(self):
        assert bool(maybe(None)) is False

    def test_mixed_dict_attr(self):
        class Profile:
            city = "Cairo"
        d = {"profile": Profile()}
        result = maybe(d)["profile"].city.get()
        assert result == "Cairo"


# ─────────────────────────────────────────────────────────────────────────────
# SmartPath
# ─────────────────────────────────────────────────────────────────────────────

from seraph import SmartPath
import tempfile
import json


class TestSmartPath:

    def setup_method(self):
        self.tmp = SmartPath(tempfile.mkdtemp())

    def test_truediv_join(self):
        p = self.tmp / "sub" / "file.txt"
        assert str(p).endswith("file.txt")

    def test_write_read_text(self):
        p = self.tmp / "hello.txt"
        p.write("Hello, Seraph!")
        assert p.read() == "Hello, Seraph!"

    def test_write_creates_parents(self):
        p = self.tmp / "a" / "b" / "c" / "deep.txt"
        p.write("deep")
        assert p.exists()

    def test_write_read_json(self):
        p = self.tmp / "data.json"
        obj = {"key": "value", "nums": [1, 2, 3]}
        p.write_json(obj)
        loaded = p.read_json()
        assert loaded == obj

    def test_read_lines(self):
        p = self.tmp / "lines.txt"
        p.write("line1\nline2\nline3\n")
        lines = p.read_lines()
        assert lines == ["line1", "line2", "line3"]

    def test_append(self):
        p = self.tmp / "log.txt"
        p.append("first\n")
        p.append("second\n")
        assert p.read_lines() == ["first", "second"]

    def test_read_env(self):
        p = self.tmp / ".env"
        p.write('KEY=value\nSECRET="abc"\n# comment\nFLAG=true\n')
        env = p.read_env()
        assert env["KEY"] == "value"
        assert env["SECRET"] == "abc"
        assert env["FLAG"] == "true"
        assert "comment" not in env

    def test_ls(self):
        (self.tmp / "a.txt").write("a")
        (self.tmp / "b.txt").write("b")
        (self.tmp / "c.json").write("{}")
        txt_files = self.tmp.ls("*.txt")
        assert len(txt_files) == 2
        assert all(f.suffix == ".txt" for f in txt_files)

    def test_name_stem_suffix(self):
        p = self.tmp / "report.json"
        assert p.name == "report.json"
        assert p.stem == "report"
        assert p.suffix == ".json"

    def test_with_suffix(self):
        p = self.tmp / "file.txt"
        assert p.with_suffix(".md").suffix == ".md"

    def test_fspath(self):
        import os
        p = self.tmp / "x.txt"
        p.write("x")
        assert os.path.exists(os.fspath(p))

    def test_mkdir(self):
        p = self.tmp / "newdir"
        p.mkdir()
        assert p.is_dir()

    def test_delete(self):
        p = self.tmp / "todelete.txt"
        p.write("bye")
        assert p.exists()
        p.delete()
        assert not p.exists()

    def test_invalid_json_raises_clear_error(self):
        p = self.tmp / "bad.json"
        p.write("{not valid json}")
        with pytest.raises(ValueError, match="Seraph"):
            p.read_json()


# ─────────────────────────────────────────────────────────────────────────────
# managed
# ─────────────────────────────────────────────────────────────────────────────

from seraph import managed
import tempfile


class TestManaged:

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                               delete=False)
        self.tmp.write("line1\nline2\nline3\n")
        self.tmp.close()
        self.path = self.tmp.name

    def test_basic_open_close(self):
        with managed(open(self.path), label="test") as res:
            content = res.value.read()
        assert "line1" in content

    def test_borrow_in_thread(self):
        results = []

        with managed(open(self.path), label="test") as res:
            def worker():
                with res.borrow() as f:
                    results.append(len(f.read().splitlines()))

            t = threading.Thread(target=worker)
            t.start()
            t.join()

        assert results == [3]

    def test_multiple_borrows(self):
        results = []

        with managed(open(self.path), label="test") as res:
            def worker(n):
                with res.borrow() as f:
                    time.sleep(0.02)
                    results.append(n)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert sorted(results) == [0, 1, 2, 3, 4]

    def test_repr_shows_status(self):
        with managed(open(self.path), label="my-file") as res:
            r = repr(res)
            assert "open" in r
            assert "my-file" in r

    def teardown_method(self):
        import os
        try:
            os.unlink(self.path)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Watchdog
# ─────────────────────────────────────────────────────────────────────────────

from seraph import watch, Watchdog, HangReport


class TestWatchdog:

    def test_no_report_when_fast(self):
        reports = []
        with Watchdog(timeout=5, on_hang=reports.append):
            time.sleep(0.1)
        assert reports == []

    def test_reports_when_hung(self):
        reports = []
        with Watchdog(timeout=0.5, poll_interval=0.1, on_hang=reports.append, repeat_after=0):
            time.sleep(1.5)
        assert len(reports) == 1
        assert isinstance(reports[0], HangReport)
        assert reports[0].idle_seconds >= 0.5

    def test_hang_report_has_thread_name(self):
        reports = []
        with Watchdog(timeout=0.5, poll_interval=0.1, on_hang=reports.append, repeat_after=0):
            time.sleep(1.2)
        assert reports[0].thread_name == "MainThread"

    def test_hang_report_format(self):
        report = HangReport(
            thread_id=12345,
            thread_name="MainThread",
            idle_seconds=10.5,
            stack_frames=[("script.py", 42, "main", "    result = slow()\n")],
            timeout=10.0,
        )
        text = report.format()
        assert "Hang detected" in text
        assert "10.5" in text
        assert "script.py" in text
        assert "line 42" in text

    def test_decorator(self):
        reports = []
        dog = Watchdog(timeout=0.5, poll_interval=0.1, on_hang=reports.append, repeat_after=0)

        @dog
        def slow_fn():
            time.sleep(1.2)

        slow_fn()
        assert len(reports) == 1

    def test_watch_factory(self):
        dog = watch(timeout=5)
        assert isinstance(dog, Watchdog)
        assert dog.timeout == 5


# ─────────────────────────────────────────────────────────────────────────────
# SmartTime
# ─────────────────────────────────────────────────────────────────────────────

from seraph import now, parse_time, SmartTime, days, hours, minutes, weeks


class TestSmartTime:

    def test_now_is_aware(self):
        t = now()
        assert t.raw.tzinfo is not None

    def test_naive_input_becomes_utc(self):
        naive = datetime(2025, 6, 15, 12, 0, 0)
        t = SmartTime(naive)
        assert t.raw.tzinfo == timezone.utc

    def test_aware_input_converted_to_utc(self):
        tz_plus2 = timezone(timedelta(hours=2))
        aware = datetime(2025, 6, 15, 14, 0, 0, tzinfo=tz_plus2)
        t = SmartTime(aware)
        assert t.raw.hour == 12    # 14:00+02 = 12:00 UTC

    def test_parse_iso(self):
        t = parse_time("2025-06-15T09:30:00Z")
        assert t.date_str == "2025-06-15"
        assert t.raw.hour == 9

    def test_parse_date_only(self):
        t = parse_time("2025-06-15")
        assert t.date_str == "2025-06-15"

    def test_parse_eu_format(self):
        t = parse_time("15/06/2025 09:30:00")
        assert t.date_str == "2025-06-15"

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_time("not-a-date")

    def test_to_utc_offset(self):
        base = SmartTime(datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc))
        cairo = base.to("UTC+2")
        assert "14" in cairo.time_str   # 12 UTC → 14 Cairo

    def test_arithmetic_add_days(self):
        t = parse_time("2025-06-15")
        result = t + days(7)
        assert result.date_str == "2025-06-22"

    def test_arithmetic_sub_hours(self):
        t = parse_time("2025-06-15T10:00:00Z")
        result = t - hours(3)
        assert result.raw.hour == 7

    def test_subtraction_returns_timedelta(self):
        t1 = parse_time("2025-06-15")
        t2 = parse_time("2025-06-08")
        diff = t1 - t2
        assert diff.days == 7

    def test_comparison(self):
        t1 = parse_time("2025-01-01")
        t2 = parse_time("2025-12-31")
        assert t1 < t2
        assert t2 > t1
        assert t1 <= t1
        assert t1 == parse_time("2025-01-01")

    def test_is_past(self):
        assert parse_time("2020-01-01").is_past() is True

    def test_is_future(self):
        assert (now() + days(1)).is_future() is True

    def test_from_timestamp(self):
        ts = 1710000000
        t = SmartTime.from_timestamp(ts)
        assert t.timestamp == pytest.approx(ts, abs=1)

    def test_human_diff_past(self):
        t = now() - days(2)
        assert "day" in t.human_diff()

    def test_human_diff_future(self):
        t = now() + hours(2)
        text = t.human_diff()
        assert "in" in text
        assert "hour" in text

    def test_date_str_time_str(self):
        t = parse_time("2025-06-15T14:30:00Z")
        assert t.date_str == "2025-06-15"
        assert t.time_str == "14:30:00"

    def test_iso_property(self):
        t = parse_time("2025-06-15T00:00:00Z")
        assert "2025-06-15" in t.iso

    def test_from_date(self):
        t = SmartTime.from_date(2025, 6, 15, 12, 0, 0)
        assert t.date_str == "2025-06-15"
        assert t.raw.hour == 12


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
