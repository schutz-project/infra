# SCHUTZ PR56 CPU deployment/rollback scripts

These scripts reconstruct the **commands used in the 2026-11-17 session**, rather than claiming to be byte-for-byte copies of files residing on EC2. No secret material, database backup, IAM credential, or certificate is included.

## What happened

- CPU load test on isolated employee portal A; 719 searches succeeded, 0 failed.
- PR56 preview dashboard showed new employee portal A release/rollback CPU metrics.
- Production management-web was moved from PR55 to PR56.
- PostgreSQL backup was created and its contents listing was checked (full restore was not tested).
- Running Compose config hash matched reconstructed config; only the management-web image changed.
- Production HTTPS /health returned 200; CPU gauge and detailed time series were visible.
- **Final rollback during continuing k6 load is not yet validated.**

## Files

- `management_web.py`: inspect current Compose files and safely prepare PR56 deploy or PR55 rollback; **default does not deploy**. Execute on monitoring EC2.
- `compose.pr56-web-only.yaml`: additional override to use after the existing Compose file stack.
- `compose.pr55-rollback.yaml`: rollback image override.
- `verify-monitoring.sh`: non-mutating HTTPS and container check, monitoring EC2.
- `verify-test-a.sh`: non-mutating isolated A container check, service EC2.

## Safety

The production deployment workflow requires **all original Compose files**. Do not execute a standalone `docker compose up` using only either override. The `management_web.py` file expects the exact override paths shown in its code, so transfer approved overrides into those paths before using apply/rollback. Run `sudo python3 management_web.py` to validate settings only. Run `--apply` or `--rollback` **only with explicit operations authorization and an available maintenance/rollback window**. This workflow does not guarantee zero downtime.

The GitHub organization currently has public repositories. Never commit `.env`, keys, certs, private IP inventories, real database dumps, or production config dumps.

## Historical test commands

Test A bug image deploy (service EC2, controlled isolated test only):

```bash
cd /home/ubuntu/schutz-release-rollback/deploy
sudo docker compose -p schutz-release-rollback -f compose.bug.yaml up -d --no-deps --force-recreate employee-a
```

Rollback test A (service EC2):

```bash
cd /home/ubuntu/schutz-release-rollback/deploy
sudo ./rollback.sh
```

These source Compose files and rollback.sh were on the service EC2; they have **not been copied into this GitHub change**. Verify those files separately before running the commands.
