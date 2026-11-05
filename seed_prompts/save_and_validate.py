#!/usr/bin/env python3
"""
Save DeepSeek JSON output to the outputs directory and validate it.

Usage:
    python seed_prompts/save_and_validate.py 7 < batch_07_raw.json
    python seed_prompts/save_and_validate.py 7    # then paste JSON, press Ctrl+D

The first argument is the batch number (e.g. 7 → batch_07_output.json).
Reads JSON from stdin, saves it, then runs validate_batch.py on it.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "seed_prompts" / "outputs"

if len(sys.argv) < 2:
    print("Usage: python save_and_validate.py <batch_num> < input.json")
    sys.exit(1)

batch_num = int(sys.argv[1])
out_file = OUT / f"batch_{batch_num:02d}_output.json"

# Read JSON from stdin
try:
    data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"❌  Invalid JSON: {e}")
    sys.exit(1)

# Save
OUT.mkdir(parents=True, exist_ok=True)
out_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"✅  Saved {len(data)} dishes to {out_file}")

# Validate
result = subprocess.run(
    [sys.executable, str(ROOT / "seed_prompts" / "validate_batch.py"), str(out_file)],
    capture_output=True, text=True,
)
print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)
sys.exit(result.returncode)
