resource "aws_vpc_security_group_ingress_rule" "management_web_public" {
  security_group_id = aws_security_group.monitoring_managed.id

  ip_protocol = "tcp"
  from_port   = 18001
  to_port     = 18001
  cidr_ipv4   = "0.0.0.0/0"

  description = "SCHUTZ Management Web Public Access"
}

import {
  to = aws_vpc_security_group_ingress_rule.management_web_public
  id = "sgr-02695fca4f4e18080"
}
