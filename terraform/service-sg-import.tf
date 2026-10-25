resource "aws_security_group" "service_managed" {
  name        = "schutz-service-sg"
  description = "SCHUTZ service EC2 security group"
  vpc_id      = "vpc-083f8357c3147578b"
}

import {
  to = aws_security_group.service_managed
  id = "sg-01cfaa76f49d26533"
}
