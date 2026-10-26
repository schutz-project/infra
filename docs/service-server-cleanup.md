# 서비스 서버 구성 정리 — 2026-10-23 멘토링 반영

## 범위와 근거

서비스 EC2의 직원 포털과 수집 에이전트를 정리한다. 모니터링 서버 제거·재배포, Terraform 적용, 공개 IP/DNS 구성은 이 변경에 포함하지 않는다.

분석 기준: infra main 527bba70a8116cefb6d53a7b809c16bf9f8cc4ad, fast-api main 7be138701dfa245563e6426adfa93fca3be2b32a. 실행 상태는 대화에서 제공된 점검 결과이며 이번 분석에서 AWS에 직접 접속한 것은 아니다.

녹취록 근거:
- 03:26–07:51: Nginx는 입구와 업무 처리를 분리하고 장애 구간을 구분하므로 유지.
- 22:50–30:57: 현재 Alloy는 로그를 Loki로 전송하며, 수집 통합이 가능하다는 설명.
- 39:22–42:37: 앱 내부 OTel SDK와 별도 Collector를 구분. SDK의 측정 결과가 Collector로 전송됨.
- 56:09–59:22: 별도 Node Exporter와 OTel Collector 기능을 Alloy로 통합하는 방향.
- 1:00:16–1:01:00: 앞단 서비스 서버부터 정리하고, 뒷단 변경은 피드백 후 진행.

## 현재 구조

| 구성 | 역할·현재 경로 | 판단 |
| --- | --- | --- |
| Nginx | 8080으로 포털 요청 수신 → api:8000; 8081 내부 직원 조회 | 유지 |
| FastAPI | 로그인·직원 검색·공지/게시판, 이벤트 기록, OTel SDK 계측 | 유지 |
| PostgreSQL 16 | 포털 업무 데이터와 인증 정보 저장 | 유지 |
| migrate / seed | 스키마 적용·초기 데이터 준비, 완료 후 종료하는 일회성 작업 | 상시 서버로 오해하거나 임의 삭제하지 않음 |
| Alloy v1.9.1 | 앱/Nginx 로그 볼륨 읽기 → Loki 전송 | 유지하고 수집 역할 통합 검토 |
| 별도 Node Exporter | 실행 점검상 schutz-node-exporter, 사설 IP 9100 노출 | Alloy 대체 검증 후 제거할 후보 |
| 앱 내부 OTel SDK | 요청 수·앱/DB 처리시간 측정 → 설정된 OTLP endpoint | 유지 |
| 별도 OTel Collector | monitoring/otel.yaml에 OTLP HTTP 4318 수신 → Prometheus 형식 8889 노출 | 모니터링 서버 구성. 서비스 서버 작업에서 제거하지 않음 |

현재 서비스/수집 흐름:

1. 사용자 → Nginx → FastAPI → 업무 PostgreSQL.
2. Nginx·FastAPI 로그 파일 → 서비스 Alloy → 모니터링 Loki.
3. 호스트 /proc·/sys 지표 → 별도 Node Exporter → 모니터링 Prometheus의 ec2-node 작업.
4. FastAPI OTel SDK → 설정된 OTLP endpoint → 별도 Collector → Prometheus의 portal-otel 작업.
5. Blackbox가 프록시·앱·직원 조회를 점검하고 Prometheus가 결과를 수집.

Alloy가 현재 모든 메트릭을 수집한다고 설명하면 안 된다. 저장소 config.alloy에는 Loki 파일 수집만 정의돼 있다. OTel 메트릭을 Node Exporter가 전달하는 경로도 현재 코드에는 없다.

## 저장소별 책임과 실제 배포 차이

| 저장소 | 확인한 파일 | 역할 |
| --- | --- | --- |
| infra | service/employee-portal/compose.yaml | DB·초기화·API·Nginx 실행 설정 |
| infra | service/alloy/compose.yaml, config.alloy | 로그 볼륨과 수집 에이전트 |
| infra | monitoring/prometheus.ec2.yaml | ec2-node, portal-otel, Blackbox 수집 대상 |
| infra | monitoring/otel.yaml | 별도 Collector의 메트릭 변환 설정 |
| fast-api | portal/telemetry.py, portal/config.py | 앱 내부 계측과 endpoint 설정 |
| fast-api | deploy/fastapi-release.sh | 이미지 교체, 헬스/직원 조회 확인, 롤백 |

확인된 관리 공백:
- infra에는 별도 Node Exporter 배포 파일이 없다. 실제 컨테이너의 이미지·인자·호스트 마운트·네트워크·재시작 정책을 먼저 확보한다.
- 서버의 compose.ecr.yaml은 infra 트리에 없다. 실제 이미지 override를 확보하되 환경 변수·비밀값은 출력하거나 커밋하지 않는다.
- infra의 포털 Compose는 로컬 build context와 .env를 요구하지만 저장소 해당 폴더에는 앱 소스·Dockerfile이 없다. 단독 실행 파일로 간주하지 않는다. 서버 배치/파일 동기화 책임을 문서화해야 한다.
- 앱 배포는 서버의 기존 Compose를 사용한다. infra 파일을 바꾸는 것만으로 서버 설정이 적용되지는 않는다.
- 앱 재생성 후 Nginx DNS 갱신을 위한 reload와 배포 잠금·롤백 경로를 유지한다.

## 서비스 서버 목표

상시 서비스 구성은 Nginx + FastAPI + PostgreSQL + Alloy로 정리하는 방향이다. migrate/seed는 초기화 작업으로 별도 설명한다.

- Nginx의 프록시 로그·독립 헬스체크·내부 직원 조회 경로를 유지한다.
- 앱 OTel SDK와 JSON 이벤트 로그를 제거하지 않는다.
- 별도 Node Exporter 프로세스를 Alloy의 호스트 메트릭 기능으로 대체하는 설계를 준비한다.
- 기존 node_* 메트릭 이름과 instance/job 라벨, 파일시스템 필터를 유지하거나 소비 쿼리를 함께 수정한다.
- OTel Collector 통합은 후속 모니터링 영역 피드백과 연동한다. SDK 제거와 혼동하지 않는다.
- Grafana/Alertmanager 제거, Worker 알림 정책 변경은 이 단계 밖이다.

## 적용 순서와 통과 조건

1. 실제 Node Exporter 컨테이너 설정 및 Alloy 이미지/호스트 권한을 읽기 전용으로 확보한다.
2. 기존 CPU·메모리·디스크·네트워크 메트릭과 Prometheus/관리 웹의 소비 쿼리를 확인한다.
3. Alloy 대체 설정을 별도 파일·브랜치에서 준비한다. 고정된 v1.9.1로 문법 검증한다.
4. 기존 수집기를 유지한 채 별도 라벨로 후보 수집 경로를 검증한다. 운영 쿼리에 두 시계열이 합산되지 않도록 한다.
5. 메트릭 이름·라벨·단위·수집 간격·호스트 파일시스템 값과 최신 샘플을 비교한다. 관리 웹 지표와 Blackbox 정상 상태도 확인한다.
6. 모니터링 Prometheus scrape 대상 변경을 함께 적용해야 함을 명시하고 변경 범위를 검토한다.
7. 전환 성공 후 별도 Node Exporter만 중지한다. 검증 완료 전 컨테이너/복구 파일을 삭제하지 않는다.
8. 로그 Loki 도착, 호스트 지표, 앱/DB 메트릭, 사건·알림 경로를 확인한다. 실패 시 기존 에이전트와 scrape 대상으로 복원한다.

완료 조건: 별도 Node Exporter 없이 기존 호스트 지표가 올바른 값·라벨로 최신 수집되고, 포털 기능·로그·앱 계측·CI/CD가 유지되어야 한다. 기능 동등성 확인 없이 컨테이너 수 감소만으로 완료 처리하지 않는다.

## 이번 변경의 상태

이 문서는 분석 및 전환 계획이다. 실행 Compose·앱 코드·실제 EC2는 변경하지 않았다. 다음 구현을 위해 실제 서버의 Node Exporter 설정을 확보해야 한다. AWS 네트워크/Terraform과 IP·DNS 공개 접속은 서버 관리자 담당이다.
