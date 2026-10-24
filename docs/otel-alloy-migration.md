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
8. 기존 배포 파일 8개의 경로를 유지하는 방식으로 적용했다. 후속 통합 점검에서 관리 서비스 전체 Compose 병합 검사, 관리 웹 /health, Blackbox·호스트 지표·앱 지표·Loki 로그를 확인했다. 관리자 화면 접속도 확인했다. 이후 별도 Management Web PR #8에서 로그인 확인 대기 화면과 새로고침 시 위치 복원을 수정했으며, 사용자가 새로고침 동작을 확인했다. 모든 차트의 표시 수치에 대한 별도 육안 검증을 완료한 것으로 해석하지 않는다.

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

모니터링 서버의 Collector를 Alloy로 교체했고, 기존 Prometheus 볼륨 및 전환 후 앱 지표 7종의 새 표본을 확인했다. 서버 통합 점검과 관리자 화면 접속·새로고침 동작 확인을 마쳤다. 이 문서를 포함한 PR 병합으로 저장소 반영을 마무리한다.

## 전환 후 통합 점검 결과

사용자가 모니터링 서버에서 실행한 읽기 전용 점검 결과다.

- 관리 서비스의 기존 배포 파일 8개 유지 및 전체 Compose 병합 검사 통과.
- 병합된 설정에서 otel-collector 이미지가 grafana/alloy:v1.9.1이고 Prometheus receiver 플래그가 유지됨을 확인.
- 관리 웹 /health 정상 응답.
- portal-otel, ec2-node, portal-health, portal-db-health의 수집 상태 up=1 확인.
- proxy, app, database의 probe_success=1 확인.
- portal_http_requests, portal_http_duration_bucket/sum/count, portal_db_duration_bucket/sum/count의 마지막 표본이 모두 약 30.7초 전으로, 점검 기준 90초 이내임을 확인.
- Loki에서 최근 5분의 portal-api 로그 존재 확인.
- 최종 출력: OTEL_ALLOY_INTEGRATION_VERIFIED.

초기 통합 점검의 여러 지표를 한 번에 처리하는 PromQL은 HTTP 422를 반환했다. 지표별 max(time() - timestamp(metric{job="portal-otel"})) 조회로 수정해 위 갱신 상태를 확인했다. 이 쿼리 오류 때문에 서버를 재배포하거나 수집기 설정을 되돌리지는 않았다.

이 결과는 관측 시점의 정상 수집을 확인한 것이다. 장시간 안정성과 실제 장애 시 복구 성공까지 검증한 것으로 표현하지 않는다. 이후 관리 웹의 자동 배포는 아래 실행에서 별도로 성공했다.

## 후속 관리 웹 수정과 배포

- 저장소: management-web. infra의 Alloy 전환과 별도 변경이다.
- PR: https://github.com/schutz-project/management-web/pull/8 — 병합 완료.
- 자동 배포: https://github.com/schutz-project/management-web/actions/runs/40094073032 — 테스트·이미지 게시·EC2 배포 성공.
- 인증 확인 전에 로그인 화면을 보여주던 동작을 대기 화면으로 수정하고, 처리 이력·페이지·사건 상세 위치를 URL에서 복원한다.
- 서버의 manage.html/manage.js bind mount 원본은 배포 이미지에서 파일을 추출해 갱신했다. 원본 백업은 /opt/schutz-monitoring/.release-backups/session-refresh-yprld4p9 에 보존했다.
- MANAGEMENT_SESSION_REFRESH_FIX_APPLIED 및 실제 HTTP 응답 파일 일치를 확인했다. 사용자가 새로고침 문제 해소를 보고했다. 주소창 Enter로 문서 전체를 다시 불러올 때 잠깐 보이는 로그인 상태 확인 문구는 의도한 동작이다.
- 서버에서 비공개 GitHub 저장소의 raw 파일에 인증 없이 접근하면 404가 발생하므로, 향후 동일 방식의 다운로드를 사용하지 않는다. GitHub CLI 인증이나 이미 배포된 이미지에서 추출하는 경로를 사용한다.
- bind mount가 이미지 파일보다 우선하므로 이후 해당 화면 파일 변경 시 마운트 원본도 함께 갱신해야 한다. 이를 자동화한 배포 수정까지 완료한 것은 아니다.
