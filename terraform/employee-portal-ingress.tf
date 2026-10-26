resource "aws_vpc_security_group_ingress_rule" "employee_portal_public" {
  security_group_id = aws_security_group.service_managed.id

  ip_protocol = "tcp"
  from_port   = 18080
  to_port     = 18080
  cidr_ipv4   = "0.0.0.0/0"

  description = "Employee Portal external access"
}

import {
  to = aws_vpc_security_group_ingress_rule.employee_portal_public
  id = "sgr-07aa369ce6a79170e"
}
