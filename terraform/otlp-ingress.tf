resource "aws_vpc_security_group_ingress_rule" "otlp_from_service" {
  security_group_id = aws_security_group.monitoring_managed.id

  ip_protocol = "tcp"
  from_port   = 4318
  to_port     = 4318

  referenced_security_group_id = aws_security_group.service_managed.id

  description = "OTLP from service EC2"
}

import {
  to = aws_vpc_security_group_ingress_rule.otlp_from_service
  id = "sgr-052e223ab5065be01"
}
