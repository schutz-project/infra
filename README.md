# SCHUTZ — AWS 인프라 및 모니터링

SCHUTZ는 테스트용 직원 포털의 상태와 로그를 수집하고, 장애를 감지하여 운영자가 확인·대응할 수 있도록 구성하는 프로젝트입니다. 이 저장소는 **서비스 EC2와 모니터링/관리 EC2의 배포 설정**을 관리합니다.

> 이 문서는 GitHub에 등록된 설정 파일을 기준으로 작성했습니다. AWS의 실시간 실행 상태나 모든 연동의 정상 작동을 보증하지 않습니다.

## 저장소 구성

```text
infra/
├── README.md
├── monitoring/
│   ├── alerts.yaml                    # Prometheus 경고 규칙
│   ├── blackbox.yaml                  # HTTP 프로브 정의
│   ├── prometheus.ec2.yaml            # 수집 대상 및 점검 작업
│   ├── loki.yaml                      # 로그 저장 및 보존 설정
│   ├── otel.yaml                      # OTLP 수신 → Prometheus exporter
│   ├── compose.management.yaml        # 관리 서비스 구성(다른 실행 방식)
│   ├── compose.management-ec2.yaml    # 관리 EC2 구성
│   └── compose.*-only.yaml            # 개별 구성 요소 실행 파일
├── service/
    ├── alloy/
    │   ├── compose.yaml               # 서비스 서버 Alloy 컨테이너
    │   └── config.alloy               # 로그 파일 수집 → Loki
    └── employee-portal/
        ├── compose.yaml               # Nginx/API/PostgreSQL 및 초기화
        └── deploy/
            ├── nginx.conf.template
            └── rotate-portal-logs.sh
└── terraform/
    ├── main.tf                      # Terraform 기본 설정
    ├── aws-network.tf               # 기존 AWS 네트워크 조회
    ├── .gitignore                   # 로컬 상태/인증 파일 제외
    └── README.md                    # Terraform 상세 설명
```

## 구성 요소와 역할

| 영역 | 구성 요소 | 역할 |
| --- | --- | --- |
| 서비스 EC2 | Nginx | 직원 포털 요청을 API로 전달하고 헬스체크 경로 제공 |
| 서비스 EC2 | API | 포털 애플리케이션 처리 |
| 서비스 EC2 | PostgreSQL | 포털 데이터 저장 |
| 서비스 EC2 | Grafana Alloy | 애플리케이션/Nginx 로그를 Loki로 전달 |
| 모니터링 영역 | Prometheus | 서비스 상태 및 메트릭 수집, 경고 규칙 평가 |
| 모니터링 영역 | Blackbox Exporter | HTTP 응답과 내부 점검 엔드포인트 검사 |
| 모니터링 영역 | Loki | 로그 저장 및 검색용 백엔드 |
| 모니터링 영역 | OpenTelemetry Collector | OTLP 메트릭 수신 및 Prometheus 형식 노출 |
| 관리 영역 | 관리 웹/워커/PostgreSQL | 사건 처리 관련 서비스 구성 (Compose 정의 기준) |

Grafana 대시보드 및 Slack 알림은 프로젝트의 운영 목표에 포함되지만, 이 저장소의 현재 파일만으로 완전한 배포·연동 여부를 확정할 수 없습니다.

## 데이터 흐름

1. 사용자가 Nginx를 통해 직원 포털 API에 요청합니다.
2. Prometheus가 Blackbox Exporter를 통해 `/proxy-health`, `/health`, 내부 DB 점검 경로를 확인합니다.
3. Prometheus가 Node Exporter 및 OTLP 메트릭 노출 엔드포인트에서도 지표를 수집하도록 설정되어 있습니다.
4. 서비스 EC2의 Alloy가 API/Nginx 로그 파일을 읽어 Loki로 전송합니다.
5. Prometheus는 `alerts.yaml`의 규칙을 평가합니다. **경고 평가와 Slack 발송은 별개**이며, 실제 알림 전송 경로는 추가 확인이 필요합니다.

## 현재 설정에 포함된 점검

- `PortalProbeFailed`: 포털 또는 DB 점검 실패가 1분 지속
- `MonitoringTargetDown`: 메트릭 수집 대상 연결 실패가 1분 지속
- `PortalTelemetryMissing`: 포털 요청 메트릭이 3분간 관측되지 않음
- `PortalHighServerErrorRate`: 5xx 오류 비율이 5%를 초과한 상태가 2분 지속

위 시간과 조건은 **Prometheus 경고 규칙** 기준입니다. 프로젝트의 사건 생성/중복 억제 정책(연속 실패 3회 등)과 동일하다고 간주하지 않습니다.

## Terraform — 기존 AWS 인프라 조회 및 문서화

[Terraform 코드와 상세 사용법 보기](./terraform/README.md)

Terraform 1.17 및 AWS Provider를 사용해 SCHUTZ 프로젝트에서 **이미 구축한 AWS 네트워크 리소스를 조회**하고, 조회 결과를 문서화했습니다. 이 코드는 현재 인프라를 생성하거나 변경하는 IaC 관리 코드가 아닌 **읽기 전용 인프라 조회 코드**입니다.

| 항목 | 현재 작업 |
| --- | --- |
| VPC | `10.20.0.0/16` 네트워크 조회 |
| 서비스 서브넷 | `10.20.10.0/24` 조회 |
| 모니터링 서브넷 | `10.20.20.0/24` 조회 |
| 라우팅 테이블 및 IGW | 연결 정보와 기본 경로 조회 |
| 보안 그룹 | 서비스·모니터링 보안 그룹 ID 및 이름 조회 |
| EC2 | AWS CLI로 확인한 인스턴스 ID·사설 IP·서브넷 ID를 정적 출력값으로 기록 |
| 보안 그룹 규칙 | AWS CLI로 인바운드/아웃바운드 규칙 확인 후 문서화 |

**검증:** `terraform validate` 성공, `terraform plan` 성공. `plan`의 출력값 변경은 실제 AWS 인프라 변경을 의미하지 않습니다.

**네트워크 주의:** 확인된 기본 라우팅 테이블의 `0.0.0.0/0 → IGW` 경로가 두 서브넷에 연결되어 있습니다. 서비스 서브넷을 프라이빗이라고 단정하지 않고, 퍼블릭 IP·보안 그룹·라우팅 설정을 함께 검토해야 합니다.

**다음 단계:** 기존 리소스의 Terraform 관리 전환이 필요한 경우, 별도 브랜치에서 `import`와 변경 계획을 먼저 검토합니다. 현재 조회 작업에는 `terraform apply`나 `terraform destroy`가 필요하지 않습니다.

## 배포 전 확인 사항

- [ ] AWS VPC·서브넷·보안 그룹·라우팅과 실제 EC2 주소 확인
- [ ] Compose 파일의 상대 경로와 필요한 Dockerfile/애플리케이션 소스 존재 확인
- [ ] `.env`, `.management.env`, 토큰 및 비밀번호를 안전하게 주입
- [ ] 서비스 서버 `/health` 및 `/proxy-health` 응답 확인
- [ ] Prometheus `up` 및 Blackbox `probe_success` 확인
- [ ] Alloy → Loki 로그 수집 확인
- [ ] Grafana 데이터소스 및 대시보드 연결 확인
- [ ] 경고 발생 → 사건 생성 → Slack 알림 → 복구 처리 전체 흐름 검증

## 보안 주의사항

- 실제 AWS 키, DB 비밀번호, Slack Webhook URL, API 토큰, `.env` 파일을 커밋하지 마세요.
- 현재 설정에는 EC2 내부 IP 및 서비스 엔드포인트가 포함되어 있습니다. 외부 공개 전 주소·구성 정보 노출을 검토하세요.
- `loki.yaml`은 `auth_enabled: false`이므로 Loki 포트의 외부 접근을 차단하고 네트워크 접근 범위를 제한해야 합니다.
- `service/employee-portal/compose.yaml`의 포트 바인딩은 특정 EC2 내부 IP를 사용합니다. 다른 환경에서 재사용할 때 수정이 필요합니다.

## 관련 저장소

- [management-worker](https://github.com/schutz-project/management-worker) — 관리 작업 처리 코드
- [management-web](https://github.com/schutz-project/management-web) — 관리 웹 저장소
- [fast-api](https://github.com/schutz-project/fast-api) — API 저장소

---

**문서 범위:** 현재 `infra/main`의 파일 구조 및 설정을 설명하는 문서. 실제 운영 절차와 통합 테스트 결과는 별도로 기록합니다.
