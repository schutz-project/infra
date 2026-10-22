provider "aws" {
  region = "ap-northeast-2"
}

data "aws_vpc" "schutz" {
  id = "vpc-083f8357c3147578b"
}

output "schutz_vpc_id" {
  value = data.aws_vpc.schutz.id
}

output "schutz_vpc_cidr" {
  value = data.aws_vpc.schutz.cidr_block
}

# 서비스 서버가 연결된 서브넷 조회
data "aws_subnet" "service" {
  id = "subnet-0d552e4820a937007"
}

# 모니터링 서버가 연결된 서브넷 조회
data "aws_subnet" "monitoring" {
  id = "subnet-028bd179fda958fca"
}

# 서비스 서브넷 IP 범위 출력
output "service_subnet_cidr" {
  value = data.aws_subnet.service.cidr_block
}

# 모니터링 서브넷 IP 범위 출력
output "monitoring_subnet_cidr" {
  value = data.aws_subnet.monitoring.cidr_block
}

# 기존 SCHUTZ 라우팅 테이블 조회
data "aws_route_table" "schutz" {
  route_table_id = "rtb-0e9f1e568ca8e9329"
}

# 라우팅 테이블 ID 출력
output "schutz_route_table_id" {
  value = data.aws_route_table.schutz.id
}

# 라우팅 테이블의 경로 출력
output "schutz_routes" {
  value = data.aws_route_table.schutz.routes
}

# 기존 인터넷 게이트웨이 조회
data "aws_internet_gateway" "schutz" {
  internet_gateway_id = "igw-08ba71d610170ee38"
}

# 인터넷 게이트웨이 ID 출력
output "schutz_igw_id" {
  value = data.aws_internet_gateway.schutz.id
}

# 인터넷 게이트웨이가 연결된 VPC 확인
output "schutz_igw_vpc_id" {
  value = one(data.aws_internet_gateway.schutz.attachments[*].vpc_id)
}

# AWS CLI로 확인한 서비스 EC2 정보 (정적 기록)
output "service_ec2_info" {
  value = {
    instance_id = "i-09af34fe68b6c200c"
    private_ip  = "10.20.10.62"
    subnet_id   = "subnet-0d552e4820a937007"
  }
}

# AWS CLI로 확인한 모니터링 EC2 정보 (정적 기록)
output "monitoring_ec2_info" {
  value = {
    instance_id = "i-066c8eee143b5cdff"
    private_ip  = "10.20.20.10"
    subnet_id   = "subnet-028bd179fda958fca"
  }
}

# 서비스 서버 보안 그룹 조회
data "aws_security_group" "service" {
  id = "sg-01cfaa76f49d26533"
}

# 모니터링 서버 보안 그룹 조회
data "aws_security_group" "monitoring" {
  id = "sg-074a3fa99695f104f"
}

# 서비스 보안 그룹 정보 출력
output "service_security_group" {
  value = {
    id   = data.aws_security_group.service.id
    name = data.aws_security_group.service.name
  }
}

# 모니터링 보안 그룹 정보 출력
output "monitoring_security_group" {
  value = {
    id   = data.aws_security_group.monitoring.id
    name = data.aws_security_group.monitoring.name
  }
}
