resource "aws_subnet" "monitoring_managed" {
  vpc_id                  = "vpc-083f8357c3147578b"
  cidr_block              = "10.20.20.0/24"
  availability_zone       = "ap-northeast-2a"
  map_public_ip_on_launch = true

  assign_ipv6_address_on_creation = false
  enable_dns64                    = false
  ipv6_native                     = false

  private_dns_hostname_type_on_launch = "ip-name"

  tags = {
    Name = "schutz-monitor-subnet"
  }
}

import {
  to = aws_subnet.monitoring_managed
  id = "subnet-028bd179fda958fca"
}
