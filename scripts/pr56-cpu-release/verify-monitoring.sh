#!/usr/bin/env bash
# Read-only checks on monitoring EC2.
set -euo pipefail
WEB=schutz-monitoring-management-web-1
DB=schutz-monitoring-management-db-1
docker inspect "$WEB" --format 'Image={{.Config.Image}} Status={{.State.Status}}'
docker inspect "$DB" --format 'DB={{.Config.Image}} Status={{.State.Status}}'
docker exec "$WEB" python -c '
import ssl
from urllib.request import urlopen
ctx=ssl._create_unverified_context()
with urlopen("https://127.0.0.1:8000/health", context=ctx, timeout=10) as r:
 print("HTTPS health:",r.status, r.read(300).decode())
'
echo 'Check the real SCHUTZ dashboard login, incidents and A release/rollback CPU graph manually.'
