"""
examples/demo.py
================
Complete walkthrough of all five Seraph features.
Run from the project root: python examples/demo.py
"""

import sys
import threading
import time
import io

sys.path.insert(0, "..")  # allow running from examples/ dir

# ─────────────────────────────────────────────────────────────────────────────
print("=" * 62)
print("  Seraph — Python's Guardian Angel")
print("=" * 62)


# ─────────────────────────────────────────────────────────────────────────────
# 1. maybe — Safe Optional Chaining
# ─────────────────────────────────────────────────────────────────────────────
from seraph import maybe

print("\n── Feature 1: maybe ── Safe Optional Chaining")

# Typical API response with deeply nested data
api_response = {
    "status": "ok",
    "data": {
        "user": {
            "name": "Mohammed",
            "profile": {
                "address": {"city": "Cairo", "zipcode": "11511"},
                "tier": "premium",
            },
        }
    },
}

# Deep access — no if-chains needed
city    = maybe(api_response)["data"]["user"]["profile"]["address"]["city"].get("N/A")
country = maybe(api_response)["data"]["user"]["profile"]["address"]["country"].get("N/A")
phone   = maybe(api_response)["data"]["user"]["contact"]["phone"].get("(no phone)")
tier    = maybe(api_response)["data"]["user"]["profile"]["tier"].apply(str.upper).get()

print(f"  city    = {city!r}")       # 'Cairo'      — found
print(f"  country = {country!r}")    # 'N/A'        — missing key, no crash
print(f"  phone   = {phone!r}")      # '(no phone)' — missing nested key
print(f"  tier    = {tier!r}")       # 'PREMIUM'    — apply() transform

# None at the root — entire chain returns default cleanly
result = maybe(None).x.y.z.get("default")
print(f"  None chain = {result!r}")  # 'default'

# Iterate safely over a list that might not exist
print("  iterating missing list:", end=" ")
for item in maybe(api_response)["data"]["items"].each():
    print(item)
print("(empty — no crash)")

# .filter() — keep only if condition holds
score = maybe({"score": 42})["score"].filter(lambda s: s > 100).get(0)
print(f"  filtered score = {score}")  # 0 — filtered out


# ─────────────────────────────────────────────────────────────────────────────
# 2. SmartPath — OS-Agnostic Paths
# ─────────────────────────────────────────────────────────────────────────────
from seraph import SmartPath

print("\n── Feature 2: SmartPath ── OS-Agnostic Paths")

base = SmartPath("/tmp/seraph_example")

# Write JSON — parent dirs auto-created, even if nested
config_path = base / "config" / "app.json"
config_path.write_json({
    "app": "seraph-demo",
    "version": "1.0",
    "database": {"host": "localhost", "port": 5432},
})
print(f"  Wrote:    {config_path}")

# Read back
cfg     = config_path.read_json()
db_host = maybe(cfg)["database"]["host"].get()
print(f"  db.host = {db_host!r}")

# .env file
env_file = base / ".env"
env_file.write("API_KEY=secret_abc123\nDEBUG=false\nPORT=8080\n")
env = env_file.read_env()
print(f"  .env API_KEY = {env.get('API_KEY')!r}")
print(f"  .env PORT    = {env.get('PORT')!r}")

# Append to a log file (auto-created)
log = base / "logs" / "run.log"
log.append("started\n")
log.append("processing\n")
log.append("done\n")
print(f"  log lines: {log.read_lines()}")

# List files
files = base.ls_recursive("**/*.json")
print(f"  json files: {[f.name for f in files]}")

# Path metadata
print(f"  config stem   = {config_path.stem!r}")
print(f"  config suffix = {config_path.suffix!r}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. managed — Thread-Safe Context Managers
# ─────────────────────────────────────────────────────────────────────────────
from seraph import managed

print("\n── Feature 3: managed ── Thread-Safe Context Managers")

results = []

log_path = str(base / "logs" / "run.log")

with managed(open(log_path), label="run-log") as res:
    print(f"  Opened: {res}")

    def worker(n: int, borrow):
        with borrow as f:
            time.sleep(0.03)          # simulate I/O
            content = f.read()
            results.append((n, len(content.splitlines())))

    threads = [
        threading.Thread(target=worker, args=(i, res.borrow()))
        for i in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

# File is guaranteed closed here — after all 4 borrows finish
print(f"  All 4 threads read the file: lines={[r[1] for r in sorted(results)]}")
print(f"  File closed exactly once, after the last thread finished.")


# ─────────────────────────────────────────────────────────────────────────────
# 4. watch — Non-Invasive Hang Detector
# ─────────────────────────────────────────────────────────────────────────────
from seraph import watch

print("\n── Feature 4: watch ── Hang Detector")
print("  Sleeping 3s with a 2s watchdog — should detect hang...")

captured = io.StringIO()
old_err  = sys.stderr
sys.stderr = captured

with watch(timeout=2, repeat_after=0):
    time.sleep(3)

sys.stderr = old_err
report = captured.getvalue()

if "Hang detected" in report:
    print("  ✓ Watchdog fired correctly!")
    for line in report.strip().splitlines()[:4]:
        if line.strip():
            print(f"    {line}")
else:
    print("  (no hang report captured)")


# ─────────────────────────────────────────────────────────────────────────────
# 5. SmartTime — Timezone-Aware Datetime
# ─────────────────────────────────────────────────────────────────────────────
from seraph import now, parse_time, days, hours, minutes, weeks

print("\n── Feature 5: SmartTime ── Timezone-Aware Datetime")

# Always aware — UTC internally
utc_now = now()
print(f"  UTC now:        {utc_now}")

# Instant timezone conversion
cairo  = utc_now.to("UTC+2")
riyadh = utc_now.to("UTC+3")
print(f"  Cairo  (UTC+2): {cairo}")
print(f"  Riyadh (UTC+3): {riyadh}")

# Parse multiple formats — always returns aware SmartTime
print(f"  ISO parse:   {parse_time('2025-06-15T09:30:00Z').date_str}")
print(f"  EU parse:    {parse_time('15/06/2025 09:30:00').date_str}")
print(f"  Date only:   {parse_time('2025-06-15').date_str}")

# Arithmetic
deadline  = now() + days(7)
overdue   = now() - days(30)
in_2h     = now() + hours(2)
print(f"  Deadline:    {deadline.date_str}")
print(f"  30 days ago: {overdue.human_diff()}")
print(f"  In 2 hours:  {in_2h.time_str}")

# Human-readable diff
print(f"  new year 2026: {parse_time('2026-01-01').human_diff()}")
print(f"  far future:    {(now() + weeks(52)).human_diff()}")

# Comparisons
assert parse_time("2020-01-01").is_past()
assert (now() + hours(1)).is_future()
assert now() < now() + days(1)
print(f"  Comparison assertions: all passed ✓")

# Output formats
t = now()
print(f"  .format():  {t.format()!r}")
print(f"  .iso:       {t.iso!r}")
print(f"  .date_str:  {t.date_str!r}")
print(f"  .timestamp: {t.timestamp:.0f}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
print("  All features demonstrated successfully.")
print("=" * 62)
