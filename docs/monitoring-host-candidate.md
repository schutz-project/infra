# 두 서버 관측 후보 — 운영 미적용

현재 main의 Prometheus 호스트 수집 대상은 서비스 서버 하나입니다. 이는 Git 설정 확인 결과이며 실제 서버의 최신 구성을 직접 확인한 결과는 아닙니다.

## 변경안

- `monitoring/alloy.monitoring-host.alloy`: 별도 Alloy에서 모니터링 호스트 CPU·메모리·루트 디스크 수집.
- `monitoring/compose.monitoring-host-candidate.yaml`: 모니터링 호스트 전용 Alloy와 Prometheus 후보 파일 마운트. 기존 OTLP·Blackbox Alloy를 변경하지 않음.
- `monitoring/prometheus.dual-host-candidate.yaml`: 기존 scrape job과 서비스 호스트 대상을 유지하고 모니터링 exporter를 같은 `ec2-node` job에 추가.
- `server_role`: `service` / `monitoring`. Web은 이 라벨로 역할을 구분하며 주소로 추측하지 않음.
- 호스트 수집기는 Docker 내부 네트워크에서만 접근. 호스트 포트 publish 및 보안 그룹 변경 없음.

별도 수집기로 시작해 기존 앱 지표 경로와 host namespace 변경이 얽히지 않게 합니다. 장기적으로 기존 Alloy에 통합할지는 실제 설정과 자원 사용량 확인 후 판단합니다. 이 후보는 새 컨테이너를 추가하므로 실제 적용은 배포 승인 대상입니다.

## 적용 전 크로스체크

1. 실제 서버에서 동일 호스트를 이미 수집하는 exporter가 있는지 확인. 중복 수집기가 있으면 후보를 그대로 추가하지 않음.
2. 기존 Prometheus 연결 네트워크가 `schutz-monitoring_default`인지, 후보 컨테이너와 통신 가능한지 확인.
3. `/host`가 실제 호스트 rootfs이고 root mountpoint의 파일시스템 지표가 나오는지 확인. read-only 호스트 마운트도 넓은 호스트 읽기 권한을 부여하므로 검토 필요.
4. Compose 경로는 infra 저장소 루트 기준. 실제 서버의 9개 Compose 파일 경로와 동일하다고 가정하지 않음. 기존 labels의 파일 목록·순서·project directory와 함께 배포 계획에 매핑.
5. Prometheus 후보 사본은 현재 main에서 생성됨. 이후 원본 설정 변경이 있으면 후보에 동기화하고 비교·검증을 다시 수행.
6. 기존 release script의 해시와 승인 기준은 변경하지 않음. 이 후보는 그 release script의 배포 자산이 아니므로 별도 반영·복구 계획 필요.

## 로컬·CI 검증

YAML 구조 검사에서 기존 scrape job 유지·역할 라벨·내부 접근·읽기 전용 마운트 확인. 기존 release 단위 테스트 18개 통과. 새 CI Workflow에 Compose config, Alloy v1.9.1 validate, Prometheus v3.4.1 promtool 검사를 추가했습니다. 로컬 Docker 미설치로 이 세 검사는 미실행이며 실제 PR CI 결과를 확인해야 합니다.

추가 정적 회귀 `tests/test_dual_host_candidate.py` 3개는 로컬에서 통과했습니다. 원본과 후보의 `ec2-node` 외 수집 작업·전역 설정 동일성, 서비스 대상 보존과 두 역할 유일성, 후보 오버레이의 외부 포트 미공개·마운트·네트워크를 검사합니다. 후보 CI에도 이 검사를 연결했습니다. 이는 설정 구조와 drift만 검사하며, Docker 실행·실제 scrape 성공을 입증하지 않습니다.

## 실제 서버 읽기 전용 확인 자료

설정 적용 전에 수집 담당자가 다음만 공유하면 됩니다. 환경변수·전체 docker inspect·비밀 파일 원문은 공유하지 않습니다.

- 실행 중인 Alloy·Prometheus 컨테이너 이름과 이미지 버전
- 사용 중인 Compose 파일 목록·네트워크 이름
- Prometheus `up{job="ec2-node"}`의 instance·server_role·up 값
- `node_memory_MemTotal_bytes{job="ec2-node"}`의 instance·server_role·표본 시각

서버 배포, 재시작, 수동 릴리스 및 LOAD-01은 이 변경안 준비 과정에서 실행하지 않았습니다.

## v0.2 검토 후 게이트

별도 `docs/monitoring-host-rollout-rollback.md`에 최소 권한 대안, 운영 확인 항목, 적용·중단·복구 순서를 추가했습니다. 아직 운영 정보가 비어 있으므로 운영 runbook 확정 또는 검증 완료를 의미하지 않습니다. Docker·Alloy·promtool 검증 로그와 실제 서버 근거 없이는 배포 NO-GO입니다.
