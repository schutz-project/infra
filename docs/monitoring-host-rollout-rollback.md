# 두 서버 관측 운영 경로·재기동·복구 계약

상태: 저장소 정합 보완안. 이 변경으로 PR 병합·서버 파일 변경·컨테이너 재생성을 수행하지 않는다.

## 확인 근거와 현재 상태

2026-10-31 21:05 KST SSM 작업자가 전달한 해시 및 선택 inspect 출력 기준이다. 작성 환경에서 AWS를 직접 조회한 결과는 아니다.

| 대상 | 확인값 |
|---|---|
| project / workdir / network | `schutz-monitoring` / `/opt/schutz-monitoring` / `schutz-monitoring_default` |
| Prometheus 호스트 설정 | `/opt/schutz-monitoring/monitoring/prometheus.ec2.yaml` → `/etc/prometheus/prometheus.yaml`, 읽기 전용 |
| Prometheus 설정 SHA-256 | `80ca705d653c95f10fc69b14dfe16120e24483dcac6dfa3d7c40fc3c3ce7c922` |
| alerts.yaml SHA-256 | `4791e9b5ad5e0959b9330ed64e08cfb0d8c6c4200eafc0a436e69fb4213d5008` |
| alloy-otel.alloy SHA-256 | `7f80abca93a08de5c9868633c2ec5347ec086d76e242acbe6877ee230c056f99` |
| 새 Alloy | `monitoring-host-metrics`, `grafana/alloy:v1.9.1`, running=true |
| exporter 마운트 | `/` → `/host` 읽기 전용, `monitoring/alloy.monitoring-host.alloy` → `/etc/alloy/config.alloy` 읽기 전용, 기존 named data volume 유지 |

호스트 root 읽기와 host PID 접근은 넓은 권한이며 최소 권한 확정안으로 보지 않는다. 기존 OTLP·Blackbox Alloy의 권한이나 재기동 조건을 변경하지 않는다. Docker socket, 공개 포트, 쓰기 가능한 host root mount는 추가하지 않는다.

현재 exporter의 Compose 생성 라벨 순서:

1. `/opt/schutz-monitoring/compose.prometheus-only.yaml`
2. `/opt/schutz-monitoring/.release-backups/dual-host-precheck-20261031T060818Z-g2jh7pds/alloy-start-a8q1e9sf/compose.monitoring-host-candidate.yaml`

Prometheus 자체는 이전 선택 inspect에서 `compose.prometheus-only.yaml`만 사용했다. 최신 출력에서 생략된 Prometheus image·running은 이번 재확인값으로 취급하지 않는다.

Web·worker·기존 Alloy의 9개 파일 생성 이력은 다음 순서이며, exporter 전용 재기동에 대신 사용하지 않는다. 모두 `/opt/schutz-monitoring` 기준이다.

1. `compose.otel-only.yaml`
2. `compose.prometheus-only.yaml`
3. `compose.management-ec2.yaml`
4. `updates/incident-drafts/compose.incident-drafts.yaml`
5. `compose.loki-only.yaml`
6. `compose.blackbox-only.yaml`
7. `compose.grafana-only.yaml`
8. `compose.ecr.yaml`
9. `compose.management-https.yaml`

## 정식 관리 경로와 적용 범위

- 저장소 `monitoring/prometheus.ec2.yaml`을 실제 동명 운영 파일에 대응시킨다. 내용은 위 운영 해시와 동일하다. 후보 파일로 마운트를 바꾸거나 Prometheus를 재생성할 필요가 없다.
- 저장소 `monitoring/compose.monitoring-host.yaml`의 승인된 내용을 향후 `/opt/schutz-monitoring/compose.monitoring-host.yaml`에 배치한다. exporter만 정의하며 Prometheus 서비스나 설정 마운트를 재정의하지 않는다.
- `--project-directory /opt/schutz-monitoring -p schutz-monitoring`을 고정하고 `-f /opt/schutz-monitoring/compose.prometheus-only.yaml -f /opt/schutz-monitoring/compose.monitoring-host.yaml` 순서를 사용한다. 상대 경로를 overlay 위치 기준으로 해석하지 않는다.
- `compose.monitoring-host-candidate.yaml`은 실험용 호환 자산이며 운영 정상화에는 사용하지 않는다.
- 공통 네트워크와 기존 `schutz-monitoring_monitoring-host-data`를 유지한다. 전체 `compose up/down`, volume 삭제, 기존 Alloy·Web·worker·DB 재생성은 하지 않는다.

파일을 배치해도 실행 중 컨테이너의 Compose 생성 라벨은 바뀌지 않는다. 정식 파일 배치와 라벨 갱신을 위한 재생성은 별도로 취급한다. 현재 정상 컨테이너를 유지하고, 실제 기존 exporter 정의와 차이를 검토한 뒤 별도 승인된 보수 시간에만 위 두 `-f`와 `up -d --no-deps --force-recreate monitoring-host-metrics`로 exporter만 재생성한다. 단순 `docker restart`는 원래 마운트·생성 라벨을 유지하므로 정식 경로 이관 완료로 표시하지 않는다.

새 서버에서는 exporter를 준비하기 전에 두 서버 Prometheus 설정을 활성화하지 않는다. 신규 도입은 기존 서버의 정식 경로 이관과 다른 실행 계획이며 별도 승인을 받는다.

기존 `scripts/blackbox-release.sha256`에서 참조하는 Prometheus 자산 해시도 같은 내용으로 갱신한다. 스크립트 실행 경로·승인 조건은 변경하지 않는다. 기존 Blackbox 릴리스 스크립트로 이번 경로 이관을 대신 실행하지 않는다.

## 변경 전 검증과 반영 후 확인

1. 현재 설정과 두 Compose의 해시·소유권·권한, Prometheus bind mount의 device/inode, 모든 기존 컨테이너 ID, exporter의 원래 Compose 순서를 접근 제한된 백업에 기록한다. 복구 담당자와 보존기간을 확정하기 전 실행하지 않는다. 백업 폴더의 현 overlay는 이관 검증 완료 전 삭제하지 않는다.
2. 정식 overlay와 실행 exporter 설정을 대조하고 Alloy v1.9.1 validate, Compose config, Prometheus v3.4.1 promtool을 검증한다. 전체 렌더링·환경변수·비밀값을 공유하지 않고 대상 서비스·mount·network·port만 선택 확인한다.
3. 현 Prometheus 해시가 위 값과 같으면 파일 쓰기나 SIGHUP을 추가하지 않는다. 향후 설정 변경은 현재 파일 대비 차이를 검증하고, 같은 열린 파일에 쓰기·fsync하여 inode·소유자·권한을 유지한다. rename/atomic replace는 bind mount가 이전 inode를 참조할 수 있으므로 사용하지 않는다.
4. 필요한 SIGHUP 이후 reload 성공뿐 아니라 실제 로드된 설정 일치와 기존 target 유지를 확인한다. 두 역할 up=1과 각 CPU 코어·메모리 total/available·루트 disk size/available의 실제 원본 표본 시각이 역할별로 3회 전진하는지 확인한다. CPU rate의 과거 무라벨 시계열과 현재 시계열을 구분한다.
5. exporter 재생성 시 readiness, host CPU 2코어, 메모리 8195911680 bytes, 루트 disk 50884108288 bytes, `device=/dev/root,fstype=ext4,mountpoint=/`, 새 생성 라벨 및 기존 컨테이너 ID 불변을 확인한다. 수치는 직전 증거 기준이며 향후 리사이즈 시 실제 호스트와 재대조한다.

## 중단·복구

- 기존 target의 신규 장애, 예상하지 못한 다른 서비스 재생성, 루트 디스크 불일치, 연속 scrape 실패 시 중단한다. LOAD-01과 Web 배포는 이 작업에 포함하지 않는다.
- 정식 overlay 이관만 실패하면 직전 exporter 정의와 원래 Compose 순서로 해당 exporter만 복구한다. 정상인 두 역할 Prometheus 설정을 단일 호스트로 되돌리지 않는다.
- Prometheus 자체를 변경해서 실패한 경우에만 직전 백업을 동일 inode에 복원·재로드하고 실제 설정과 기존 target 회복을 확인한다.
- 두 서버 수집 도입 전체를 철회하는 별도 승인일 때만 도입 전 설정 복원·재로드 확인 후 새 exporter를 중지한다. data volume과 증거는 보존한다.

기존 도입 전 백업은 `/opt/schutz-monitoring/.release-backups/dual-host-precheck-20261031T060818Z-g2jh7pds`이다. 향후 변경 직전 백업의 대용으로 사용하지 않는다. 기존 두 서버 수집과 LOAD-01의 사용자 제공 완료 증거, 이번 저장소 검증, 향후 정식 경로 이관은 각각 구분한다.
