# 아키텍처 간소화 마무리 점검

기록일: 2026-10-25 (한국 시간)

## 완료한 범위

| 저장소/영역 | 결과 |
|---|---|
| infra / 서비스 호스트 수집 | 별도 Node Exporter 대신 기존 Alloy에서 호스트 지표 수집, 기존 수집기 중지·restart=no |
| infra / OTLP 수신 | 별도 Collector 실행을 Alloy로 대체, 앱 OTel SDK 유지 |
| infra / Grafana | 대시보드 3개 DB 백업 무결성 확인, 중지 시험 3회 통과, 수동 프로필 적용, 현재 컨테이너 restart=no |
| management-web | 경보·수집 대상 및 경로별 앱/프록시 지표 추가, Grafana 링크 제거, HTTPS 배포 성공 |
| management-worker | 기존 수집·사건·AI·Slack 작업 유지, HTTPS 구성에 맞춘 배포 검사 통과 |
| fast-api | 이번 마무리 작업에서 코드·배포 변경 없음 |
| 알림 현황 | Prometheus 연결 Alertmanager 0개 확인, 채택 여부는 미결정 |

기존 Grafana 기능 전체를 동일하게 구현한 것은 아닙니다. 현재 Web은 15분 고정 조회와 결과 개수 제한을 사용하며, Prometheus 자체 진단 대시보드 전체·임의 시간 범위 조회는 이전하지 않았습니다.

## 남아 있는 범위

- Alertmanager/Worker 선택: 녹취 기준 미결정. 현황 확인과 역할 분석만 완료했으며 선택 결정은 수행하지 않음.
- 서버 엔지니어: 외부 접속·인증서·Terraform 및 변경된 서버 설정의 재현 가능한 인계.
- 저장소: 서버 전체 Grafana·HTTPS Compose 원문 미수집. 운영 상태 기록과 실제 서버 전체 설정의 버전 관리는 구분.
- 최종 구성 전체 장애 주입→AI→Slack→복구 재검증: 아직 수행하지 않음. 기존 개별 시나리오 시험을 최종 구성 전체 재시험으로 간주하지 않음.

## 고도화 전 확인한 현재 기능

Web은 사건별 탐지 근거·AI 결과/시도 이력·접수/조치/종료 기록을 제공합니다. Worker AI 입력은 해당 사건에 연결된 최근 근거를 사용하며, 과거 유사 사건·조치 이력을 검색해 분석 입력에 포함하는 기능은 확인되지 않았습니다.

후속 고도화 후보는 조회 시간 범위 선택, 장애 전후 비교, 통합 타임라인, 과거 대응 이력 활용입니다. 본 점검에서는 고도화 코드를 변경하지 않았습니다.

## 근거

- docs/alloy-host-metrics-migration.md
- docs/otel-alloy-migration.md
- docs/grafana-retirement.md
- docs/alerting-responsibilities.md
