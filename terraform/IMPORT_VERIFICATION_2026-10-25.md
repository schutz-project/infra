# SCHUTZ Terraform Import 검증 기록 (2026-10-25)

## 목적
기존 AWS 인프라를 새로 생성하거나 변경하지 않고 Terraform State에 등록하여 관리 대상으로 전환.

## 로컬 검증 결과
- 작업 폴더: `C:\schutz-terraform`
- AWS 리전: `ap-northeast-2`
- `terraform validate`: 성공
- 모니터링 EC2 Import 계획: `1 to import, 0 to add, 0 to change, 0 to destroy`
- `terraform apply "schutz-monitoring-ec2.tfplan"`: `1 imported, 0 added, 0 changed, 0 destroyed`
- Import 후 `terraform plan`: `No changes. Your infrastructure matches the configuration.`
- `terraform state list`: 관리 리소스 11개 + data source 7개 확인

## Import 완료한 관리 리소스 (11개)

| Terraform 주소 | 기존 AWS 리소스 ID |
| --- | --- |
| `aws_vpc.schutz_managed` | `vpc-083f8357c3147578b` |
| `aws_subnet.service_managed` | `subnet-0d552e4820a937007` |
| `aws_subnet.monitoring_managed` | `subnet-028bd179fda958fca` |
| `aws_internet_gateway.schutz_managed` | `igw-08ba71d610170ee38` |
| `aws_route_table.schutz_managed` | `rtb-0e9f1e568ca8e9329` |
| `aws_route_table_association.service_managed` | `rtbassoc-0b1a19cb322938173` |
| `aws_route_table_association.monitoring_managed` | `rtbassoc-0b303299b30149730` |
| `aws_security_group.service_managed` | `sg-01cfaa76f49d26533` |
| `aws_security_group.monitoring_managed` | `sg-074a3fa99695f104f` |
| `aws_instance.service_managed` | `i-09af34fe68b6c200c` |
| `aws_instance.monitoring_managed` | `i-066c8eee143b5cdff` |

## 주의
- 이 문서는 **사용자 로컬 PowerShell 검증 결과**를 기록한 것임.
- GitHub의 `terraform/` 폴더에는 기존 조회형 코드가 남아 있을 수 있으며, **로컬 Import용 .tf 파일의 업로드/동기화는 별도 작업**임. 따라서 이 문서만으로 GitHub의 Terraform 코드가 현재 로컬 상태와 일치한다고 판단하면 안 됨.
- `terraform.tfstate`, `*.tfplan`, `*.tfvars`, `.env`, 자격 증명/비밀키는 절대 커밋하지 말 것.
- 기존 AWS 자원을 Terraform으로 관리한 이후에는 코드 변경과 `apply`가 실제 AWS 자원 변경/교체/삭제로 이어질 수 있으므로 `terraform plan`을 먼저 검토할 것.
