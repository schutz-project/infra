# 경보 계산과 사건·알림 역할

분석 기준: 2026-10-24 코드 검토 및 2026-10-25 사용자 제공 서버 조회 결과.

## 실서버 연결 확인 결과

Worker 컨테이너에서 설정된 Prometheus의 `/api/v1/alertmanagers`를 조회했습니다.

- HTTP 조회 성공 및 응답 status=success
- activeAlertmanagers: 0
- droppedAlertmanagers: 0

현재 해당 Prometheus가 인식하는 연결 대상은 없습니다. 이 결과는 서버 전체에 Alertmanager가 설치돼 있지 않다는 증거가 아니며, 사용 여부가 확정됐다는 뜻도 아닙니다. 별도 Alertmanager 도입·제거는 수행하지 않았습니다.

녹취 56:44~57:26 및 59:22에서 Alertmanager와 Worker의 선택은 기능·관리 편의성의 판단 근거를 정한 후 결정할 사항으로 남았습니다. 현재 Worker 경로와 기존 Prometheus 규칙을 유지합니다.

## 현재 역할

| 구성 | 입력과 역할 | 외부 알림 |
|---|---|---|
| Prometheus | 메트릭 저장, alerts.yaml 규칙 평가, ALERTS 제공 | 확인한 저장소의 prometheus.ec2.yaml에는 alerting/Alertmanager 연결이 없음 |
| Management Worker | Blackbox 점검 메트릭 및 Loki 로그인 실패 이벤트를 읽어 사건·근거를 관리 DB에 기록 | 최초 Slack 작업과 AI 분석 작업 생성, AI 성공 후 후속 Slack 작업 생성 |
| Management Web | 상태·사건·근거·조치 이력·Prometheus 경보 표시 | 현재 경보 표는 조회 기능이며 Slack 전송을 의미하지 않음 |
| Grafana | 기존 보조 조회 화면 | 서버 DB 알림 규칙 0개·파일 알림 설정 없음 확인 후 중지 |

## 규칙 비교

| Prometheus 규칙 | 기준 | Worker 대응 |
|---|---|---|
| PortalProbeFailed | probe_success=0, 1분 지속 | 별도 규칙: HTTP 0/5xx 등의 실패가 서로 다른 샘플에서 3회. 판정·시간 기준이 완전히 같지는 않음 |
| MonitoringTargetDown | up=0, 1분 지속 | 모든 수집 대상 장애를 사건·Slack으로 변환하는 대응 규칙은 없음 |
| PortalTelemetryMissing | portal_http_requests 부재, 3분 지속 | 앱 메트릭 부재 전용 사건·Slack 규칙은 없음 |
| PortalHighServerErrorRate | 5xx 비율 5% 초과, 2분 지속 | 전체 트래픽 오류율 기반 사건·Slack 규칙은 없음 |
| 해당 없음 | 정상 응답이지만 2초 초과 3회 | Worker response_delay 사건 |
| 해당 없음 | 같은 계정·출처의 모의 로그인 실패 60초 내 5회 | Worker login_failures 사건 |

현재 로그인 실패 집계는 synthetic=true 이벤트만 대상으로 합니다. 일반 운영 로그인 실패 탐지까지 완료했다고 해석하지 않습니다.

Worker는 동일 점검 샘플의 반복 집계를 방지하고, 열린 사건 키로 동일 대상·규칙 사건을 묶습니다. Slack 전송은 최대 4회, AI 분석은 최대 2회 자동 시도하며 시도 이력을 저장합니다. 외부 전송 타임아웃은 전송 여부가 불명확할 수 있으므로 Slack의 정확히 한 번 전달을 보장하지 않습니다.

## 정리 방향

- 사건 생성·AI 분석·Slack 전달은 현재 Worker 경로를 유지합니다.
- Prometheus 4개 경보 규칙은 유지합니다. Worker가 전부 대체하지 않으므로 삭제하지 않습니다.
- 실서버 Prometheus 연결 현황 조회는 완료했습니다. 도입·제거·미설치 확정은 하지 않습니다.
- 수집기 장애·앱 메트릭 부재·5xx 비율 경보를 Slack까지 보낼지는 다음 설계 항목입니다. 사건과 경보의 중복 처리 기준을 정한 뒤 구현합니다.
- 이번 분석은 코드 검토입니다. 새로운 장애 주입이나 Slack·AI 호출을 실행하지 않았습니다.

## 참조 코드

- infra: monitoring/alerts.yaml, monitoring/prometheus.ec2.yaml
- management-worker: management/worker.py, management/domain.py, management/jobs.py
- management-web: management/observability.py
