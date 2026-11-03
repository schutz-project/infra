# SCHUTZ — Terraform 기존 AWS 인프라 Import

SCHUTZ에서 기존에 구축한 AWS 자원을 Terraform으로 Import한 설정 코드입니다. **새 인프라 생성용 예제가 아닙니다.**

## 구성
- `main.tf`: Terraform 버전 및 기본 출력
- `aws-network.tf`: 기존 VPC/서브넷/라우팅/IGW/보안 그룹 조회 및 출력
- `*-import.tf`: 기존 AWS 자원에 대한 `resource` 정의 및 `import` 블록
- `management-web-ingress.tf`, `loki-ingress.tf`, `otlp-ingress.tf`: 기존 보안 그룹 인바운드 규칙 Import
- `backend.tf`: S3 원격 State 및 잠금 파일 설정
- `.gitignore`: 로컬 State, 계획 파일, 인증 자료 제외
- [Import 검증 기록](./IMPORT_VERIFICATION_2026-10-25.md)

## Import 대상 (총 14개)
VPC 1개, 서브넷 2개, 인터넷 게이트웨이 1개, 라우팅 테이블 1개, 라우팅 테이블 연결 2개, 보안 그룹 2개, EC2 2개, 보안 그룹 인바운드 규칙 3개(Management Web TCP 18001, Loki TCP 3100, OTLP HTTP TCP 4318).

- AWS 리전: `ap-northeast-2`
- 서비스 EC2: `i-09af34fe68b6c200c` (`t3.medium`)
- 모니터링 EC2: `i-066c8eee143b5cdff` (`t3.large`)

## 로컬 검증 (2026-10-26)
사용자의 로컬 `C:\schutz-terraform` 환경에서:
- `terraform validate` 성공
- Import 작업의 계획: `1 to import, 0 to add, 0 to change, 0 to destroy` (마지막 모니터링 EC2)
- 최종 `terraform plan`: `No changes. Your infrastructure matches the configuration.`
- 기존 관리 자원 11개 및 인바운드 규칙 3개, 총 관리 자원 14개 확인
- OTLP 규칙 `sgr-052e223ab5065be01`: `1 imported, 0 added, 0 changed, 0 destroyed`
- OTLP Import 후 `terraform plan`: `No changes. Your infrastructure matches the configuration.`

## S3 원격 State 전환 (2026-11-03)

- 버킷: `schutz-terraform-state-2026` (서울 `ap-northeast-2`)
- State 키: `schutz/terraform.tfstate`
- 버킷 버전 관리: 활성화
- 잠금: `use_lockfile = true` (`.tflock`)
- Terraform 실행 IAM 사용자: `schutz-ssm-user` (전용 S3 Backend 접근 정책 적용)
- 로컬 State를 별도 백업한 뒤 `terraform init -migrate-state`로 S3에 이전
- 이전 후 `terraform state list`에서 총 22개 항목(관리 리소스 15개, data source 7개) 확인
- 이전 후 `terraform plan`: `No changes. Your infrastructure matches the configuration.`

새 PC나 CI에서 사용하려면 동일한 `backend.tf`와 적절한 AWS IAM 인증 및 S3 접근 권한이 필요합니다. 동시 실행은 잠금으로 조정되지만 작업 전 협의가 필요합니다. `terraform apply` 또는 `destroy`는 반드시 변경 계획을 검토한 뒤 실행하세요.

**State 파일 원본과 로컬 백업은 GitHub에 올리지 않습니다.** S3 객체 버전 관리가 활성화되어 있어도 삭제/복원 및 IAM 권한은 별도 관리해야 합니다.

## 보안
`terraform.tfstate`, `*.tfplan`, `*.tfvars`, `.env`, 자격 증명, 키 파일은 GitHub에 업로드하지 않습니다. 이 저장소는 비공개로 유지하고, `terraform plan`을 확인하기 전에는 `apply` 또는 `destroy`를 실행하지 마세요.

네트워크 설정에는 두 서브넷이 모두 IGW 기본 경로를 가진 라우팅 테이블에 연결되어 있습니다. 이름만으로 서비스 서브넷을 프라이빗이라고 단정하면 안 됩니다.
