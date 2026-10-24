# OTel Collector의 Alloy 전환

## 범위와 배치 결정

infra만 변경한다. FastAPI 내부 OTel SDK와 앱 전송 주소 http://10.20.20.10:4318/v1/metrics는 유지한다.
서비스 서버의 기존 Alloy(로그·호스트 지표 담당)도 유지한다.

확인 결과 Prometheus는 모니터링 EC2의 loopback 9090에만 publish되어 있다. 서비스 서버 Alloy에 OTLP를 추가하면 앱 주소 변경뿐 아니라 Prometheus까지 서버 간 전달 경로 변경이 필요하다. 이번에는 모니터링 서버에 Alloy를 배치해 별도 Collector를 교체하고, Prometheus 수신은 Docker 내부 네트워크를 사용한다. 공개 포트·보안 그룹을 추가하지 않는다.

이번 단계는 Collector 구현·설정 도구를 Alloy로 통일하는 교체다. 서비스 Alloy와 모니터링 Alloy는 각각 남으므로 컨테이너 수 감소로 표현하지 않는다. 단일 Alloy 통합은 네트워크·가용성·권한을 따로 검토할 후속 선택이다.

## 전환 전후 흐름

기존:
SDK → OTLP HTTP 4318 → Collector memory_limiter(256MiB/64MiB, 1초) → batch → Prometheus exporter 8889 → Prometheus scrape.

전환 후:
SDK → 같은 OTLP HTTP 4318 → 모니터링 Alloy의 memory_limiter → batch → prometheus 변환 → relabel → remote_write → 같은 네트워크 Prometheus.

- Collector 0.128.0, Alloy 1.9.1, Prometheus 3.4.1을 기준으로 검증한다.
- add_metric_suffixes=false 유지. portal_http_requests와 앱/DB duration histogram을 비교한다.
- transform에서 메트릭 이름의 점 등을 밑줄로 변환하고 instrumentation scope 이름·버전 라벨을 보존한다. Prometheus 3 scrape와 같은 정수 histogram 경계(예: le=5.0)를 relabel로 유지한다.
- job=portal-otel, instance=otel-collector:8889를 유지한다.
- 기존 scrape에서 충돌한 리소스 job/instance가 exported_job/exported_instance로 보존되는 동작을 relabel로 재현한다.
- Prometheus에 --web.enable-remote-write-receiver를 추가해야 하며 컨테이너 재생성이 필요하다. TSDB 볼륨·보존 설정·loopback 바인딩은 유지한다.
- 기존 portal-otel scrape 대상은 Alloy의 8889 HTTP 인터페이스를 점검한다. DNS alias otel-collector를 호환 목적으로 유지한다. 앱 지표 자체는 remote_write로 들어온다. up=1만으로 앱 전송 정상이라고 보지 말고 portal_* timestamp와 값도 확인한다.
- Alloy 데이터 볼륨은 remote_write WAL을 보존한다. 장애 시 무제한 보관이나 영구 손실 방지를 보장하지 않는다.
- 메모리 제한은 프로세스 메모리를 확인하는 processor이며 컨테이너 cgroup 하드 메모리 제한을 새로 설정한 것은 아니다.

## 추가 파일

| 파일 | 역할 |
| --- | --- |
| monitoring/alloy-otel.alloy | OTLP 수신·메모리 제한·배치·지표 변환·라벨 보존·내부 전송 |
| monitoring/compose.alloy-otel.yaml | 최종 Alloy, 기존 schutz-monitoring_default 네트워크·4318 |
| monitoring/compose.prometheus-remote-write.yaml | 기존 Prometheus 명령을 유지한 receiver 플래그 추가 override |
| scripts/verify-otel-alloy.py | 기존 Collector와 후보에 동일 OTLP JSON을 보내 저장된 지표 비교 |
| .github/workflows/alloy-otel.yml | 버전 고정 문법 검사와 격리된 실제 호환성 시험 |

원래 Collector/Prometheus 설정의 저장소 파일은 복구 참고용으로 유지한다. monitoring/compose.alloy-otel.yaml은 서버에서 /opt/schutz-monitoring/compose.otel-only.yaml로 배치하며, 서비스 키 otel-collector와 기존 컨테이너 이름을 유지한다. config는 monitoring/alloy-otel.alloy를 참조한다. Prometheus receiver 플래그는 서버의 기존 compose.prometheus-only.yaml 명령에 추가했다. 별도 override 파일은 설정 검증용이며 서버의 실행 파일 목록에 추가하지 않았다. 현재 portal/host metrics 설정을 전체 덮어쓰지 않는다. 특히 앞서 적용한 Alloy 호스트 metrics_path는 유지해야 한다.

## CI 호환성 시험

격리 Docker network와 임시 저장소에서 다음을 검증한다.
1. 기존 Collector를 같은 otel.yaml로 실행.
2. 후보 Alloy와 remote_write receiver가 켜진 별도 Prometheus 실행.
3. 동일한 누적 요청 카운터·앱/DB 히스토그램·route/status/resource를 두 경로에 전송.
4. 기존 scrape와 후보 remote_write의 metric 이름·라벨(job 제외)·값을 비교.
5. 이름에 원치 않는 unit/type suffix가 붙거나 exported_job 등의 라벨이 달라지면 실패.
6. 종료 시 임시 컨테이너·네트워크 제거.

시험은 요청·DB 대표 메트릭 계약을 검증한다. 실제 앱의 모든 route/status 조합, 기타 resource/target_info 지표의 완전 동등성은 운영 전 추가 비교가 필요하다. push와 scrape의 표본 시각 차이도 있어 시계열 전환 중 rate 공백·counter reset 가능성을 점검한다.

## 실제 적용 결과 — 2026-10-24

사용자가 모니터링 EC2의 SSM 세션에서 실행하고 출력으로 확인한 결과다.

1. 전환 전 기존 앱 지표 7종을 조회했다. DB histogram bucket 16개, count/sum 각 1개, HTTP histogram bucket 32개, count/sum/request 각 2개 시계열을 확인했다.
2. 준비·백업 경로는 /opt/schutz-monitoring/.otel-alloy-migration/prepare-Pdcv0fqi 이다. 기존 Collector/Prometheus Compose 및 OTel/Prometheus 설정을 보존했다.
3. 서버에서 Alloy 1.9.1 validate와 Compose config 검사가 통과했다.
4. 기존 Prometheus 명령에 --web.enable-remote-write-receiver를 추가해 재생성했다. readiness와 /prometheus의 기존 저장 볼륨 경로 일치를 확인했다. PROMETHEUS_REMOTE_WRITE_ENABLED 출력으로 확인했다.
5. 기존 compose.otel-only.yaml 자리에 Alloy Compose를 배치했다. 서비스 키 otel-collector, 사설 IP의 4318 바인딩, 기존 Docker 네트워크를 유지해 같은 컨테이너를 Alloy 이미지로 재생성했다. 이전 Collector 컨테이너 자체가 별도로 보존되는 방식은 아니다. 복구는 원래 Compose와 기존 이미지로 재생성한다.
6. 연결 중단에 대비한 5분 자동 복구 타이머를 등록하고 전환했다. 전환 후 시각보다 새로운 앱 메트릭 7종을 확인한 뒤 타이머를 해제했다. OTEL_ALLOY_LIVE_METRICS_OK, OTEL_COLLECTOR_TO_ALLOY_SWITCH_OK 및 이미지 grafana/alloy:v1.9.1, running=true를 확인했다.
7. 복구 스크립트는 준비 경로의 rollback-collector.sh 이다. Collector 교체 실패 시 기존 Compose로 수집기를 복원한다. 이 스크립트는 Prometheus receiver 플래그까지 제거하는 전체 복구는 아니다.
8. 기존 배포 파일 8개의 경로를 유지하는 방식으로 적용했다. 관리 서비스 전체 Compose 병합 검사와 Blackbox·호스트 지표·Loki 로그·관리 화면의 최종 확인은 후속 점검에서 수행한다.

FastAPI 내부 SDK, 서비스 서버 Alloy, management-web 및 management-worker의 코드는 변경하지 않았다.

## CI 검증 결과

- 검증한 설정 커밋: 086eeec0de22cfc86307bab9a095271cd1c01de1.
- Alloy OTel compatibility: https://github.com/schutz-project/infra/actions/runs/40089762769 — 성공.
- OTLP HTTP 수신, 대표 지표 이름, 라벨, 누적 카운터와 histogram 값 일치를 확인했다.
- 같은 커밋의 Infrastructure CI 및 Alloy host metrics validation도 성공했다.
- 호환성 시험은 Alloy 시작 후 5초 기다린 다음 표본을 보낸다. 초기 즉시 전송 시험에서는 후보 앱 표본이 조회되지 않았으므로 시작 직후 첫 표본의 보존까지 검증한 것으로 해석하지 않는다. 운영 전환 후에는 신선한 앱 표본의 지속 수신을 별도로 확인한다.

관리 UI·Worker는 Prometheus 재생성 동안 잠시 수집 지연으로 표시될 수 있다. 데이터 수집 공백과 시험성 사건을 확인하며 자동으로 사건을 삭제하거나 알림을 재전송하지 않는다.

## 복구

- 준비 경로의 rollback-collector.sh를 실행하면 기존 compose.otel-only.yaml을 복원하고 otel-collector 서비스를 재생성해 4318과 alias를 복구한다. 원래 Collector 이미지가 로컬에 있어야 한다.
- Prometheus는 원본 Compose 명령·원본 config로 복원한다. 기존 TSDB 볼륨은 삭제하지 않는다.
- 새 Alloy의 remote_write WAL에 동일 앱의 미전송 데이터가 남을 수 있으므로, 복구 뒤 이를 무조건 재시작해 기존 시계열에 재전송하지 않는다.
- 원래 재시작 정책, 앱 주소 유지, portal-otel up·최신 앱 메트릭·host metrics·Loki·Worker 상태를 확인한다.

## 상태

모니터링 서버의 Collector를 Alloy로 교체했고, 기존 Prometheus 볼륨 및 전환 후 앱 지표 7종의 새 표본을 확인했다. 최종 통합 점검과 PR 병합은 아직 완료되지 않았다.
