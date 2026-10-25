resource "aws_internet_gateway" "schutz_managed" {
  vpc_id = "vpc-083f8357c3147578b"

  tags = {
    Name = "schutz-igw"
  }
}

import {
  to = aws_internet_gateway.schutz_managed
  id = "igw-08ba71d610170ee38"
}
