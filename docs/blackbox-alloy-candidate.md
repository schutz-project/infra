# Blackbox Alloy 통합 후보와 검증 상태

기준일: 2026-10-26 KST. 운영 전환 미실행.

## 완료한 사전 검증

사용자가 모니터링 서버에서 Alloy v1.9.1 validate를 실행해 단독 Blackbox 컴포넌트 문법 검사를 통과했다. 기존 Blackbox 설정·secret 마운트를 읽기 전용으로 공유한 임시 Alloy에서 프록시·앱·직원 조회를 각 1회 검사했다. 기존 Blackbox에서도 같은 세 대상을 각 1회 검사했다.

세 대상 모두 probe_success=1, probe_http_status_code=200으로 일치했다. employee_read 모듈의 Bearer 인증·본문 정규식은 기존 설정을 재사용했다. 인증 파일 내용은 출력하지 않았다. 임시 Alloy는 삭제됐고 기존 Blackbox·Alloy·Worker·DB 컨테이너 ID와 실행 상태 유지가 확인됐다. Prometheus에 시험 지표를 저장하지 않았고 기존 스택을 재시작하지 않았다.

이 결과는 기능 점검 비교이며, 전체 통합 구성·운영 지표 라벨·Worker 탐지·실패/복구 동작까지 검증한 결과는 아니다.

## 후보 파일

- monitoring/alloy-otel-blackbox.alloy: 기존 OTLP 처리·remote_write 구성을 보존하고 Blackbox 컴포넌트만 추가
- monitoring/compose.alloy-otel-blackbox.yaml: 기존 Alloy 데이터 볼륨·4318 포트·서비스 별칭 유지, 기존 Blackbox YAML·secret 마운트 추가
- monitoring/prometheus.alloy-blackbox.yaml: 기존 점검 대상·모듈·주기·job/instance/check를 유지하고 scrape 경로·주소만 통합 Alloy로 전환

기존 운영 기본 파일·배포 스크립트는 변경하지 않는다. 후보 파일을 PR 병합만으로 서버에 적용하지 않는다.

## 라벨·점검 경로 계약

| job | instance | check | module |
|---|---|---|---|
| portal-health | http://10.20.10.62:8080/proxy-health | proxy | http_2xx |
| portal-health | http://10.20.10.62:8080/health | app | http_2xx |
| portal-db-health | http://10.20.10.62:8081/internal/check/employee | database | employee_read |

scrape 주소는 otel-collector:8889이고 metrics_path는 /api/v0/component/prometheus.exporter.blackbox.portal_check/metrics이다. __param_target과 __param_module 전달 구조를 유지한다. 별도의 Alloy prometheus.scrape/remote_write를 추가하지 않아 probe 시계열의 중복 기록을 피한다. 주기는 기존 Prometheus 15초를 따른다.

blackbox-exporter job은 호환용 이름과 instance=blackbox:9115를 유지하지만 실제 /metrics 조회 대상은 통합 Alloy다. 이 up 지표는 Alloy HTTP metrics 수집 가능 여부이며 기존 독립 Blackbox 프로세스 상태를 의미하지 않는다. 개별 기능 점검은 probe_success로 판단한다. 이 의미 변경을 수집 상태 화면·알림 설명에서 확인해야 한다.

## 적용 전 남은 검증

1. CI에서 고정 Alloy v1.9.1 전체 구성, Compose, Prometheus v3.4.1 설정·기존 규칙을 검증한다. CI 인증 파일은 더미이며 기능 인증 성공 검증으로 취급하지 않는다.
2. 전체 통합 Alloy 후보를 격리 실행하고 실제 exported probe 시계열의 job/instance/check 및 세 지표 종류를 대조한다. 운영 Prometheus에 동시에 동일 라벨을 쓰지 않는다.
3. 기존 앱 메트릭 7종 이름·라벨·갱신 유지와 지표 중복 부재, Worker 기능 점검·로그 수집을 확인한다.
4. 운영 전환 파일·해시·전체 Compose 순서·신호 재로드 방식·자동 복구 타이머를 확정하고 승인받는다.

## 운영 전환 및 롤백 원칙

아직 실행 명령을 확정하거나 적용하지 않았다. 기존 9개 Compose 파일 수·순서 검증과 HTTPS 마지막 파일을 유지하도록 기존 서버 경로의 내용 교체를 검토한다. 후보 파일을 10번째 파일로 무조건 추가하지 않는다.

전환 전 실제 활성 Compose·Alloy·Prometheus 파일과 이미지 ID·컨테이너 ID·볼륨을 별도 백업한다. 기존 Blackbox는 통합 Alloy를 실제로 운영 검증할 때까지 유지한다. 성공 후에만 별도 승인된 실행안으로 중지·재시작 제외를 적용하며 삭제하지 않는다. 실패 시 백업 Alloy/Compose와 Prometheus 설정을 복원하고 기존 Blackbox 점검 경로로 되돌린다. 구체 명령·백업 경로는 적용 계획에 고정한다.

Terraform·네트워크·Web·Worker·DB·이전 발표 시연 환경은 이번 PR에서 변경하지 않는다. Alloy 장애 시 OTLP 수신과 기능 점검이 함께 영향을 받는 결합은 남는다.

## 참고

- Grafana Alloy Blackbox 컴포넌트: https://grafana.com/docs/alloy/latest/reference/components/prometheus/prometheus.exporter.blackbox/
- v1.9.1 소스: https://github.com/grafana/alloy/blob/v1.9.1/internal/component/prometheus/exporter/blackbox/blackbox.go
