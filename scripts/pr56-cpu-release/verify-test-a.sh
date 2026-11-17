#!/usr/bin/env bash
# Run on service EC2. Read-only: does not generate k6 load or redeploy.
set -euo pipefail
docker inspect schutz-release-test-a --format 'Name={{.Name}} Image={{.Config.Image}} Status={{.State.Status}}'
docker stats --no-stream --format 'Name={{.Name}} CPU={{.CPUPerc}} Mem={{.MemUsage}}' schutz-release-test-a
echo 'Normal image expected: schutz-fastapi-complex:20261113-v4'
