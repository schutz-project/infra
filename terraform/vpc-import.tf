resource "aws_vpc" "schutz_managed" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "schutz-vpc"
  }
}

import {
  to = aws_vpc.schutz_managed
  id = "vpc-083f8357c3147578b"
}
