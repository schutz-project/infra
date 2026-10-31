# 두 서버 관측 — 운영 경로 정합 후보

2026-10-31 21:05 KST SSM 작업자가 전달한 해시·선택 inspect 출력에 따라 운영 경로와 저장소를 맞추는 변경안입니다. 이번 저장소 보완은 서버 반영이나 PR 병합을 수행하지 않습니다. 기존 운영 rollout과 LOAD-01 실행은 사용자 제공 증거이며 현재 변경의 CI 결과와 구분합니다.

## 변경안

- `monitoring/alloy.monitoring-host.alloy`: 별도 Alloy에서 모니터링 호스트 CPU·메모리·루트 디스크 수집.
- `monitoring/compose.monitoring-host.yaml`: 정식 관리용 exporter 전용 overlay. 서버에서는 `/opt/schutz-monitoring/compose.monitoring-host.yaml`에 매핑하며, Prometheus 서비스나 마운트를 재정의하지 않음.
- `monitoring/compose.monitoring-host-candidate.yaml`: 기존 실험용 경로 호환 사본. Prometheus 후보 파일로 마운트를 바꾸므로 운영 정상화에 사용하지 않음.
- `monitoring/prometheus.ec2.yaml`: 실제 운영에서 사용 중인 두 서버 설정을 기존 파일 경로에 유지. 기존 `compose.prometheus-only.yaml` 마운트를 그대로 사용.
- `monitoring/prometheus.dual-host-candidate.yaml`: 기존 scrape job과 서비스 호스트 대상을 유지하고 모니터링 exporter를 같은 `ec2-node` job에 추가.
- `server_role`: `service` / `monitoring`. Web은 이 라벨로 역할을 구분하며 주소로 추측하지 않음.
- 호스트 수집기는 Docker 내부 네트워크에서만 접근. 호스트 포트 publish 및 보안 그룹 변경 없음.

별도 수집기로 시작해 기존 앱 지표 경로와 host namespace 변경이 얽히지 않게 합니다. 장기적으로 기존 Alloy에 통합할지는 실제 설정과 자원 사용량 확인 후 판단합니다. 이 후보는 새 컨테이너를 추가하므로 실제 적용은 배포 승인 대상입니다.

## 적용 전 크로스체크

1. 실제 서버에서 동일 호스트를 이미 수집하는 exporter가 있는지 확인. 중복 수집기가 있으면 후보를 그대로 추가하지 않음.
2. 기존 Prometheus 연결 네트워크가 `schutz-monitoring_default`인지, 후보 컨테이너와 통신 가능한지 확인.
3. `/host`가 실제 호스트 rootfs이고 root mountpoint의 파일시스템 지표가 나오는지 확인. read-only 호스트 마운트도 넓은 호스트 읽기 권한을 부여하므로 검토 필요.
4. Compose 경로는 infra 저장소 루트 기준. 실제 서버의 9개 Compose 파일 경로와 동일하다고 가정하지 않음. 기존 labels의 파일 목록·순서·project directory와 함께 배포 계획에 매핑.
5. 정식 기준은 `prometheus.ec2.yaml`. 후보 사본은 호환용으로 같은 바이트를 유지하고 CI에서 차이를 거부. 단일 호스트 이전 기준은 `tests/fixtures/prometheus.ec2.pre-dual-host.yaml`에 보존하며 배포 자산으로 사용하지 않음.
6. 기존 release script 실행 코드는 변경하지 않음. 정식 Prometheus 자산 변경에 맞춰 `scripts/blackbox-release.sha256`의 해당 자산 항목만 갱신. 기존 스크립트를 이번 exporter 경로 이관에 실행하지 않으며 별도 반영·복구 계획을 사용.

## 로컬·CI 검증

정적 회귀는 도입 전 단일 호스트 fixture와 두 서버 설정의 `ec2-node` 외 설정 동일성, 서비스 target 보존, 두 역할 유일성, 기존 Prometheus 마운트 경로 유지, 정식 overlay의 exporter 단독 소유를 검사한다. 호환 후보와 정식 설정의 바이트 일치도 검사한다. 전체 Python 회귀에는 기존 release manifest 자산 해시 검사도 포함된다.

후보 CI는 정식·호환 Compose config, Alloy v1.9.1 validate, 정식·호환 Prometheus v3.4.1 promtool을 수행한다. 이전 head의 CI 성공을 이번 보완 head의 성공으로 대신하지 않는다. 로컬 Docker 도구 실행과 GitHub CI 성공, 실제 운영 수집 성공은 각각 별도 근거로 기록한다.

## 실제 서버 읽기 전용 확인 자료

설정 적용 전에 수집 담당자가 다음만 공유하면 됩니다. 환경변수·전체 docker inspect·비밀 파일 원문은 공유하지 않습니다.

- 실행 중인 Alloy·Prometheus 컨테이너 이름과 이미지 버전
- 사용 중인 Compose 파일 목록·네트워크 이름
- Prometheus `up{job="ec2-node"}`의 instance·server_role·up 값
- `node_memory_MemTotal_bytes{job="ec2-node"}`의 instance·server_role·표본 시각

이번 저장소 정합 보완 중 서버 배포·재시작·수동 릴리스·LOAD-01 재실행은 수행하지 않습니다. 이전 승인된 운영 수집 반영과 LOAD-01 완료는 사용자 제공 실행·교차검토 결과로 구분합니다.

## v0.2 검토 후 게이트

별도 `docs/monitoring-host-rollout-rollback.md`에 최소 권한 대안, 운영 확인 항목, 적용·중단·복구 순서를 추가했습니다. 운영에서 확인한 경로·해시 및 기존 적용 결과는 해당 문서에 근거 수준과 함께 기록합니다. 저장소 보완과 정식 Compose 경로로의 서비스 재생성은 별도입니다. 현재 컨테이너의 Compose 라벨은 파일을 복사하는 것만으로 바뀌지 않으며, 승인 전 재생성하지 않습니다.
