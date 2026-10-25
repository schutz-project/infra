resource "aws_route_table" "schutz_managed" {
  vpc_id = "vpc-083f8357c3147578b"

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = "igw-08ba71d610170ee38"
  }
}

import {
  to = aws_route_table.schutz_managed
  id = "rtb-0e9f1e568ca8e9329"
}
