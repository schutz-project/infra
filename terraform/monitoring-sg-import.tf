resource "aws_security_group" "monitoring_managed" {
  name        = "schutz-monitor-sg"
  description = "SCHUTZ monitoring EC2 security group"
  vpc_id      = "vpc-083f8357c3147578b"
}

import {
  to = aws_security_group.monitoring_managed
  id = "sg-074a3fa99695f104f"
}
