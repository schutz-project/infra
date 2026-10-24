# OTel Collector의 Alloy 전환 준비

## 범위와 배치 결정

infra만 변경한다. FastAPI 내부 OTel SDK와 앱 전송 주소 http://10.20.20.10:4318/v1/metrics는 유지한다.
서비스 서버의 기존 Alloy(로그·호스트 지표 담당)도 유지한다.

확인 결과 Prometheus는 모니터링 EC2의 loopback 9090에만 publish되어 있다. 서비스 서버 Alloy에 OTLP를 추가하면 앱 주소 변경뿐 아니라 Prometheus까지 서버 간 전달 경로 변경이 필요하다. 이번에는 모니터링 서버에 Alloy를 배치해 별도 Collector를 교체하고, Prometheus 수신은 Docker 내부 네트워크를 사용한다. 공개 포트·보안 그룹을 추가하지 않는다.

이번 단계는 Collector 구현·설정 도구를 Alloy로 통일하는 교체다. 서비스 Alloy와 모니터링 Alloy는 각각 남으므로 컨테이너 수 감소로 표현하지 않는다. 단일 Alloy 통합은 네트워크·가용성·권한을 따로 검토할 후속 선택이다.

## 현재 실행과 후보 흐름

기존:
SDK → OTLP HTTP 4318 → Collector memory_limiter(256MiB/64MiB, 1초) → batch → Prometheus exporter 8889 → Prometheus scrape.

후보:
SDK → 같은 OTLP HTTP 4318 → 모니터링 Alloy의 memory_limiter → batch → prometheus 변환 → relabel → remote_write → 같은 네트워크 Prometheus.

- Collector 0.128.0, Alloy 1.9.1, Prometheus 3.4.1을 기준으로 검증한다.
- add_metric_suffixes=false 유지. portal_http_requests와 앱/DB duration histogram을 비교한다.
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

원래 Collector/Prometheus 설정은 수정하지 않았다. Compose 파일은 최종적으로 /opt/schutz-monitoring에 배치하고 monitoring 하위 디렉터리의 config를 참조한다. 현재 portal/host metrics 설정을 전체 덮어쓰지 않는다. 특히 앞서 적용한 Alloy 호스트 metrics_path는 유지해야 한다.

## CI 호환성 시험

격리 Docker network와 임시 저장소에서 다음을 검증한다.
1. 기존 Collector를 같은 otel.yaml로 실행.
2. 후보 Alloy와 remote_write receiver가 켜진 별도 Prometheus 실행.
3. 동일한 누적 요청 카운터·앱/DB 히스토그램·route/status/resource를 두 경로에 전송.
4. 기존 scrape와 후보 remote_write의 metric 이름·라벨(job 제외)·값을 비교.
5. 이름에 원치 않는 unit/type suffix가 붙거나 exported_job 등의 라벨이 달라지면 실패.
6. 종료 시 임시 컨테이너·네트워크 제거.

시험은 요청·DB 대표 메트릭 계약을 검증한다. 실제 앱의 모든 route/status 조합, 기타 resource/target_info 지표의 완전 동등성은 운영 전 추가 비교가 필요하다. push와 scrape의 표본 시각 차이도 있어 시계열 전환 중 rate 공백·counter reset 가능성을 점검한다.

## 실제 적용 순서 — 아직 실행하지 않음

1. 현재 Collector 원본 설정·실행 인자·재시작 정책, Prometheus Compose/config 및 TSDB 볼륨 식별자를 백업한다. 서버 호스트명을 각 단계에서 확인한다.
2. 현재 portal_* 지표명·라벨·샘플·대시보드, host metrics·Loki 로그·Blackbox·Worker 정상 상태를 확보한다.
3. CI 통과 후 모니터링 서버에서 production 4318/Prometheus를 건드리지 않는 별도 임시 네트워크·포트로 후보를 시험한다.
4. Prometheus 실제 Compose 원본 뒤에 receiver override를 적용하고 config 검사·재생성 후 볼륨 동일성·readiness·기존 scrape 복귀를 확인한다. HTTP lifecycle 설정은 변경하지 않는다.
5. 기존 Collector를 중지하고 Alloy를 동일 4318에 연결한다. alias가 중복되지 않도록 기존 Collector가 정지됐는지 확인한다. 기존 Collector는 삭제하지 않는다.
6. SDK 30초 export 주기와 batch/remote_write 전송을 기다린다. 실제 portal_* timestamp의 신선도, 오류 없이 지속 증가하는 요청 수·histogram, up 상태·UI·Loki·host metrics를 확인한다.
7. 실제 앱 데이터 확인 후 기존 Collector restart=no로 변경하고 원래 정책을 기록한다. 기존 여덟 Compose 파일을 모두 사용하는 관리 배포와 충돌하지 않는지 실행 파일 목록을 별도로 정리한다. 기존 otel-only 파일로 up 전체를 수행하면 Collector가 재기동될 수 있으므로 자동화도 함께 점검한다.
8. 서버 경로/라벨과 최종 결과를 기록한 뒤 PR 병합·운영 지침을 마무리한다.

관리 UI·Worker는 Prometheus 재생성 동안 잠시 수집 지연으로 표시될 수 있다. 데이터 수집 공백과 시험성 사건을 확인하며 자동으로 사건을 삭제하거나 알림을 재전송하지 않는다.

## 복구

- 새 Alloy 중지 후 기존 Collector를 원본 Compose로 시작해 4318과 alias를 복구한다.
- Prometheus는 원본 Compose 명령·원본 config로 복원한다. 기존 TSDB 볼륨은 삭제하지 않는다.
- 새 Alloy의 remote_write WAL에 동일 앱의 미전송 데이터가 남을 수 있으므로, 복구 뒤 이를 무조건 재시작해 기존 시계열에 재전송하지 않는다.
- 원래 재시작 정책, 앱 주소 유지, portal-otel up·최신 앱 메트릭·host metrics·Loki·Worker 상태를 확인한다.

## 상태

이 PR은 후보 설정과 검증 준비다. 운영 Collector/Prometheus·FastAPI는 아직 변경하지 않았다. CI 결과와 실제 서버 후보 비교가 통과하기 전 기존 Collector를 중지하지 않는다.
