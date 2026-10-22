# SCHUTZ — Terraform AWS 인프라 조회

SCHUTZ 프로젝트에서 기존에 구축한 AWS 네트워크 리소스를 Terraform `data` 블록으로 **조회하고 문서화**하는 예제입니다.

> **중요:** 현재 코드는 AWS 인프라를 생성하거나 Terraform 관리 대상으로 가져오는 코드가 아닙니다. EC2 정보는 AWS CLI로 확인한 값을 `output`에 정적으로 기록했습니다. 실제 EC2 설정과 달라질 수 있습니다.

## 구성 파일

| 파일 | 역할 |
|---|---|
| `main.tf` | Terraform 최소 버전 및 프로젝트 설명 |
| `aws-network.tf` | AWS Provider, 기존 VPC·서브넷·라우팅 테이블·IGW·보안 그룹 조회 및 출력 |
| `.gitignore` | 상태 파일, 로컬 설정 및 인증 자료 Git 추적 제외 |

## 조회 대상 (2026-10-22 기준)

- 리전: `ap-northeast-2` (서울)
- VPC: `vpc-083f8357c3147578b`, `10.20.0.0/16`
- 서비스 서브넷: `subnet-0d552e4820a937007`, `10.20.10.0/24`
- 모니터링 서브넷: `subnet-028bd179fda958fca`, `10.20.20.0/24`
- 라우팅 테이블: `rtb-0e9f1e568ca8e9329`
- 인터넷 게이트웨이: `igw-08ba71d610170ee38`
- 서비스 보안 그룹: `schutz-service-sg` (`sg-01cfaa76f49d26533`)
- 모니터링 보안 그룹: `schutz-monitor-sg` (`sg-074a3fa99695f104f`)
- 서비스 EC2 기록: `i-09af34fe68b6c200c`, 사설 IP `10.20.10.62`
- 모니터링 EC2 기록: `i-066c8eee143b5cdff`, 사설 IP `10.20.20.10`

### 보안 그룹 규칙 (AWS CLI 확인 결과)

| 대상 보안 그룹 | 인바운드 포트 | 허용 출발지 |
|---|---|---|
| 서비스 | TCP 8080, 8081, 9100 | 모니터링 보안 그룹 |
| 모니터링 | TCP 4318, 3100 | 서비스 보안 그룹 |

두 보안 그룹의 아웃바운드는 모든 IPv4 목적지(`0.0.0.0/0`)를 허용합니다. 위 규칙은 AWS CLI 조회 결과를 문서화한 것이며, 현재 Terraform 데이터 소스에서 규칙 자체를 출력하지는 않습니다.

### 네트워크 확인 사항

확인한 라우팅 테이블에는 `0.0.0.0/0 → IGW` 경로가 있고 **두 서브넷에 연결**되어 있습니다. 따라서 현재 구성을 '서비스 프라이빗 서브넷 / 모니터링 퍼블릭 서브넷'이라고 단정하면 안 됩니다. 서브넷 연결 및 퍼블릭 IP, 실제 보안 그룹 설정을 함께 검토해야 합니다.

## 실행 방법

Terraform 1.17 이상과 AWS 인증(읽기 권한)이 필요합니다. 이 폴더에서:

```powershell
terraform init
terraform fmt -check
terraform validate
terraform plan
```

`terraform plan`은 조회 결과와 출력값 변경을 보여주며, 여기에는 실제 AWS 리소스 생성·변경용 `resource` 블록이 없습니다. `terraform apply` 또는 `terraform destroy`는 이 조회·문서화 작업에 필요하지 않으므로 실행하지 마세요.

## 보안 및 GitHub 업로드

`terraform.tfstate`, `terraform.tfstate.backup`, `.terraform/`, `*.tfvars`, 비밀키·AWS 자격 증명은 커밋하지 않습니다. `.terraform.lock.hcl`은 Terraform `init` 실행 시 생성되는 공급자 잠금 파일로, 실제 생성된 파일을 확인한 후 함께 커밋하는 것이 좋습니다(이 배포본에는 포함되지 않음).

## 다음 단계

현재는 기존 AWS 인프라의 조회·문서화 단계까지 완료했습니다. 실제 Terraform 관리 전환을 진행한다면 별도 브랜치에서 리소스 정의 및 `import` 계획을 검토하고, 기존 인프라에 변경이 없는지 충분히 검증해야 합니다.
