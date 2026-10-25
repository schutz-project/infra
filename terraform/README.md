# SCHUTZ — Terraform 기존 AWS 인프라 Import

SCHUTZ에서 기존에 구축한 AWS 자원 11개를 Terraform State로 Import한 설정 코드입니다. **새 인프라 생성용 예제가 아닙니다.**

## 구성
- `main.tf`: Terraform 버전 및 기본 출력
- `aws-network.tf`: 기존 VPC/서브넷/라우팅/IGW/보안 그룹 조회 및 출력
- `*-import.tf`: 기존 AWS 자원에 대한 `resource` 정의 및 `import` 블록
- `.gitignore`: 로컬 State, 계획 파일, 인증 자료 제외
- [Import 검증 기록](./IMPORT_VERIFICATION_2026-10-25.md)

## Import 대상 (총 11개)
VPC 1개, 서브넷 2개, 인터넷 게이트웨이 1개, 라우팅 테이블 1개, 라우팅 테이블 연결 2개, 보안 그룹 2개, EC2 2개.

- AWS 리전: `ap-northeast-2`
- 서비스 EC2: `i-09af34fe68b6c200c` (`t3.medium`)
- 모니터링 EC2: `i-066c8eee143b5cdff` (`t3.large`)

## 로컬 검증 (2026-10-25)
사용자의 로컬 `C:\schutz-terraform` 환경에서:
- `terraform validate` 성공
- Import 작업의 계획: `1 to import, 0 to add, 0 to change, 0 to destroy` (마지막 모니터링 EC2)
- 최종 `terraform plan`: `No changes. Your infrastructure matches the configuration.`
- `terraform state list`: 관리 자원 11개 + data source 7개 확인

**주의:** GitHub에 `.tf` 파일을 업로드해도 로컬 Terraform State가 자동으로 GitHub에 옮겨지지는 않습니다. 새 PC나 CI에서 이 폴더를 바로 `terraform apply`하지 마세요. Terraform State와 자원 관리 전환 방법을 별도로 설계해야 합니다. 기존 AWS 리소스가 새로 생성되거나 변경될 수 있습니다.

## 보안
`terraform.tfstate`, `*.tfplan`, `*.tfvars`, `.env`, 자격 증명, 키 파일은 GitHub에 업로드하지 않습니다. 이 저장소는 비공개로 유지하고, `terraform plan`을 확인하기 전에는 `apply` 또는 `destroy`를 실행하지 마세요.

네트워크 설정에는 두 서브넷이 모두 IGW 기본 경로를 가진 라우팅 테이블에 연결되어 있습니다. 이름만으로 서비스 서브넷을 프라이빗이라고 단정하면 안 됩니다.
