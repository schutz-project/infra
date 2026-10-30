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


## 2026-10-26 추가 격리 라벨 검증 완료

전체 OTLP 설정의 remote_write 목적지를 임시 Prometheus로만 바꾼 Alloy와 별도 임시 Prometheus를 실행했다. 운영 Prometheus의 probe 지표와 후보 지표를 20초 간격으로 두 차례 비교했다.

- proxy/app/database 세 대상의 probe_success, probe_http_status_code, probe_duration_seconds에서 이름을 제외한 전체 라벨 집합이 기존과 일치했다.
- 각 라벨 집합은 중복 없이 세 개였으며, 성공값 1·HTTP 200·유한한 응답시간을 확인했다.
- 후보의 기능 점검 3개와 자체 수집 1개 모두 up=1이 된 뒤 비교를 시작했다.
- 호환용 blackbox-exporter job의 instance=blackbox:9115 및 up=1을 확인했다.
- 두 차례 비교 모두 통과: ALLOY_BLACKBOX_LABEL_PARITY_OK.
- 임시 Alloy·Prometheus 삭제와 기존 Blackbox·Alloy·Worker·DB 컨테이너 ID·실행 상태 유지 확인.
- 운영 설정 변경·운영 Prometheus 시험 지표 저장 없음.

첫 시험은 준비 조건에 자체 수집 up 준비를 포함하지 않았고 상세 진단 없이 AssertionError로 중단됐다. 원인은 출력만으로 확정할 수 없었다. 준비 대기·진단 출력을 보완한 재시험 결과가 위 기록이다. 최초 실패를 운영 장애나 완료 증거로 취급하지 않는다.

이 시험의 임시 Prometheus는 실제 운영 Prometheus가 아니다. 운영 OTLP 갱신·Worker 수집 지속·배포 실패 자동 롤백은 실제 전환 후 별도 확인해야 한다.

## 운영 전환 범위 초안 — 아직 승인·실행하지 않음

전환 대상은 모니터링 Alloy와 Prometheus의 기능 점검 경로다. Web·Worker·DB 이미지 및 컨테이너, Terraform·네트워크·이전 시연 환경은 변경하지 않는다.

기존 9개 Compose 파일의 이름·순서를 유지한다. 아래 서버 파일의 기존 내용 전체를 전환 전에 백업하고, 후보 적용 시 Alloy 설정 마운트 경로는 기존 경로를 유지한다.

| 서버 파일 | 계획한 내용 |
|---|---|
| compose.otel-only.yaml | 통합 Alloy 정의, 기존 config 경로·데이터 볼륨·4318 유지, Blackbox 모듈·인증 마운트 추가 |
| monitoring/alloy-otel.alloy | 기존 OTLP 처리와 운영 remote_write 유지, 검증한 Blackbox 컴포넌트 추가 |
| monitoring/prometheus.ec2.yaml | 기존 job/instance/check 유지, probe 경로·주소를 통합 Alloy로 변경 |
| compose.blackbox-only.yaml | 성공 검증 후 수동 실행 프로필로 기본 실행 제외 |

실행안에서 고정할 백업 루트 후보는 /opt/schutz-monitoring/.release-backups/blackbox-alloy-20261026/ 이다. 아직 생성하지 않았다. 이미 존재하면 덮어쓰지 않는다. 현재 이미지 ID·컨테이너 ID·재시작 정책·활성 Compose 목록도 함께 저장한다.

순서:
1. 공통 배포 잠금, 현재 파일·이미지·컨테이너 기준 대조, 원본 백업.
2. 실제 합친 Compose와 Prometheus 후보를 validate/promtool로 확인. 비밀정보·인증서·secret 원문을 출력하지 않는다.
3. Alloy만 재생성하고 준비 상태 확인. 이 구간에는 OTLP 수신이 일시 중단될 수 있으므로 무중단을 보장하지 않는다.
4. Prometheus 설정을 같은 경로에 반영하고 HUP 재로드. 프로세스·데이터 볼륨은 유지한다.
5. 세 probe의 신규 표본·라벨·성공값, 앱 지표 7종 지속 갱신, Worker 수집·Web·DB 유지와 새 경보 유무 확인.
6. 검증 성공 후에만 기존 Blackbox를 중지·재시작 제외. 컨테이너·이미지·secret·백업은 삭제하지 않는다.
7. 실패 시 기존 Blackbox를 원래 정책으로 시작하고, 백업 파일 복원·Alloy 재생성·Prometheus 재로드 후 기존 경로의 신규 정상 표본을 확인한다.

구체 배포/롤백 스크립트·자동 원복 타이머·명령·기준 해시는 아직 확정하지 않았다. 이 초안만으로 운영 전환을 실행하지 않는다. PR 병합과 운영 전환 승인은 분리한다.

## 운영 실행안 추가

실행 스크립트·해시·고정 경로·적용/롤백 명령을 blackbox-alloy-release-plan.md에 추가했습니다. 위의 스크립트 미확정 설명은 이전 기록입니다. 로컬 안전 조건·mock 복원 테스트 14개를 통과했으나, 실제 운영 전환·systemd 자동 원복 실증은 아직 하지 않았습니다. 승인 전에는 실행하지 않습니다.

## 2026-10-30 저장소 중복 파일 정리 (운영 적용 아님)

현재 후보 검증 경로는 `monitoring/alloy-otel.alloy`와 `monitoring/prometheus.ec2.yaml`를 대표 파일로 사용합니다. 위 날짜별 과거 기록에 등장하는 `alloy-otel-blackbox.alloy`와 `prometheus.alloy-blackbox.yaml`는 삭제된 중복 사본의 당시 경로입니다. 이 변경은 Git 정리용이며 실제 서버 구성이나 과거 검증 결과를 변경하지 않습니다.
