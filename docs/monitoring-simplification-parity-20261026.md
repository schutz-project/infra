# 모니터링 간소화 설정 대조 결과

기준일: 2026-10-26 KST

## 적용 범위

사용자가 모니터링 서버 SSM에서 제공한 파일 Git blob SHA-1과 docker compose config 결과를 저장소와 대조했다. 이 PR은 기록과 프로필 전용 설정을 추가하며 서버 배포, 컨테이너 재생성, Terraform plan/apply를 실행하지 않는다. 서비스 서버의 최신 실행 상태 전체는 이번 조회 범위가 아니다.

## 바이트 일치 확인

서버 기준 경로는 /opt/schutz-monitoring/ 이다. Git blob SHA-1은 파일 길이를 포함한 Git blob 형식으로 계산했으며 파일 내용·비밀정보를 출력하지 않았다.

| 서버 상대 경로 | infra 경로 | 확인 |
|---|---|---|
| compose.blackbox-only.yaml | monitoring/compose.blackbox-only.yaml | 동일 |
| compose.loki-only.yaml | monitoring/compose.loki-only.yaml | 동일 |
| compose.management-ec2.yaml | monitoring/compose.management-ec2.yaml | 동일 |
| compose.management-https.yaml | monitoring/compose.management-https.yaml | 동일 |
| compose.otel-only.yaml | monitoring/compose.alloy-otel.yaml | 이름은 다르지만 동일 |
| monitoring/alloy-otel.alloy | monitoring/alloy-otel.alloy | 동일 |
| monitoring/prometheus.ec2.yaml | monitoring/prometheus.alloy-host.yaml | 이름은 다르지만 동일 |
| monitoring/alerts.yaml | monitoring/alerts.yaml | 동일 |
| monitoring/blackbox.yaml | monitoring/blackbox.yaml | 동일 |
| monitoring/loki.yaml | monitoring/loki.yaml | 동일 |
| updates/incident-drafts/compose.incident-drafts.yaml | monitoring/compose.incident-drafts.yaml | 동일 |

compose.otel-only.yaml이라는 이름 또는 otel-collector라는 서비스 별칭만으로 별도 OTel Collector가 실행 중이라고 판단하지 않는다. 위 파일은 Alloy 전환 설정과 동일하다. 실제 이미지와 실행 여부는 runtime inspect로 별도 확인한다.

## Prometheus의 의미상 대응

서버 compose.prometheus-only.yaml의 blob SHA-1은 2879d4d57402ec92e35d789001eebc80c49e913a이다. 저장소는 기본 파일과 monitoring/compose.prometheus-remote-write.yaml로 나눠 보존한다.

확인한 서버 항목:

- image: prom/prometheus:v3.4.1
- restart: unless-stopped, profiles 없음
- ports: 127.0.0.1:9090:9090/tcp
- command: --config.file=/etc/prometheus/prometheus.yaml, --storage.tsdb.path=/prometheus, --storage.tsdb.retention.time=7d, --storage.tsdb.retention.size=2GB, --web.enable-remote-write-receiver

위 실행 옵션·이미지·재시작 정책·포트는 Git 기본 설정에 remote-write 설정을 병합한 결과와 일치한다. 전체 Compose 파일이 바이트 동일하다는 의미는 아니다. 볼륨·네트워크 등 모든 속성을 이번 짧은 출력만으로 재검증했다고 주장하지 않는다. 서버는 이미 원본 파일 안에 수신 옵션이 들어 있으므로 별도 override를 추가할 필요가 없다.

## Grafana 수동 실행 설정

서버 compose.grafana-only.yaml의 blob SHA-1은 2d4044f19e42a5e6b931667d6537f029d7a04e1d이다.

- image: grafana/grafana:12.0.2
- profiles: [manual-grafana]
- Compose restart: unless-stopped
- ports: 127.0.0.1:3000:3000/tcp
- grafana-data 볼륨 및 provisioning·dashboards 읽기 전용 마운트 확인

전체 원문과 환경변수·인증 설정은 수집하지 않았다. 따라서 관측한 일부 필드로 전체 원본 Compose를 재구성하거나 덮어쓰지 않는다. monitoring/compose.grafana-manual-profile.yaml은 확인된 프로필만 담는 추가 설정이며 기존 Grafana 정의와 함께 사용할 때만 유효하다. 서버에는 이미 같은 프로필이 반영돼 있어 지금 복사·적용하지 않는다.

중요한 차이:

- 수동 프로필은 기본 실행 대상에서 제외하지만 명시적 서비스 실행·프로필 활성화는 가능하다.
- Compose restart=unless-stopped와 이전에 컨테이너에 적용한 restart=no는 서로 다르다.
- Grafana를 재생성하면 Compose의 재시작 정책을 따른다. 중지·restart=no 유지가 필요하면 재생성 계획에서 별도 확인한다.
- 이번 출력에는 현재 Grafana 컨테이너 실행 상태·재시작 정책이 포함되지 않아 과거 중지 상태를 현재 조회로 재확인했다고 간주하지 않는다.

## 기존 배포 파일 순서 유지

기존 Web·Worker 배포 검증은 필수 Compose 파일과 HTTPS 추가 파일 순서를 사용한다. 서버 파일을 Git 파일명으로 바꾸거나 프로필 파일을 기존 스택에 무조건 추가하면 배포 검증에 영향을 줄 수 있다. 이번 PR은 파일 이름·개수·순서를 변경하지 않는다.

compose.ecr.yaml은 배포된 이미지 태그를 보존하는 서버 파일이며 이번에 전체 내용을 수집하거나 Git 템플릿으로 덮어쓰지 않았다. 이미지 태그·로그 볼륨·DB 볼륨은 기존 배포 절차로 유지한다.

## Terraform 담당자 전달 사항

- 기존 AWS 자원 11개 Terraform 편입은 유지하며 컨테이너 간소화와 분리한다.
- 모니터링 측 기존 포트 4318(OTLP), 9090(loopback), 3000(loopback), 관리 HTTPS 구성은 이번 대조에서 변경하지 않았다.
- Blackbox는 현재 별도 구성으로 유지한다. Alloy 통합은 아직 적용·검증하지 않았다.
- Blackbox 통합 시 인증 토큰 마운트, 모듈, 프록시·앱·DB 점검, job/instance/check 라벨, Worker 탐지, 복구·롤백을 먼저 검증한다.
- 검증 후에도 포트·보안 그룹 변경이 필요한지 별도 판단한다. 이 문서만으로 보안 그룹을 삭제하지 않는다.
- 서비스 서버 최신 실행 구성과 이전 발표 시연 환경 보존 상태는 후속 확인 항목이다.

## 다음 단계

1. 이 PR의 문서·프로필 설정을 검토한다. 병합과 서버 적용은 구분한다.
2. 기존 간소화 결과는 유지하고, Blackbox Alloy 통합 후보를 격리 검증한다.
3. 성공한 경우에만 운영 전환·롤백 실행안을 확정하고 승인 후 적용한다.

전체 인프라 코드화·서버 복구 검증이 모두 끝났다는 의미는 아니다. 확인되지 않은 Grafana 원문·서버 전용 이미지 파일·서비스 서버 런타임 설정은 보존하고 추정으로 덮어쓰지 않는다.
