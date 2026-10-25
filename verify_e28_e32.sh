#!/bin/bash
# E28-E32 verification commands
# Run from: /home/m/Documents/GitHub/ff-engine

DC="docker compose -f docker/docker-compose.yml exec -T \
  -e DJANGO_SETTINGS_MODULE=config.settings.test \
  -e DATABASE_URL=postgres://ff_engine:ff_engine_pass@db:5432/ff_engine_test \
  -e REDIS_URL=redis://redis:6379/0 \
  web"

echo "=== 1. System check ==="
$DC python manage.py check

echo ""
echo "=== 2. Migrate test DB ==="
$DC python manage.py migrate --run-syncdb 2>&1 | grep -E "Applying|OK|Error" | head -10

echo ""
echo "=== 3. E28-E32 tests only (fast) ==="
$DC python -m pytest apps/dishes/tests/test_e28_e32.py --tb=short -q 2>&1 | tail -20

echo ""
echo "=== 4. Full test suite ==="
$DC python -m pytest --tb=short -q 2>&1 | tail -10

echo ""
echo "=== 5. Golden set ==="
$DC python manage.py run_golden_set --json 2>&1 | python3 -c "
import sys, json
lines = sys.stdin.read()
start = lines.index('{')
d = json.loads(lines[start:])
print(f'Total: {d[\"total\"]} Passed: {d[\"passed\"]} Failed: {d[\"failed\"]}')
[print(f'  FAIL {c[\"id\"]}: {c[\"failures\"]}') for c in d['cases'] if not c['passed']]
"
