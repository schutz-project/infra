resource "aws_vpc_security_group_ingress_rule" "loki_from_service" {
  security_group_id = aws_security_group.monitoring_managed.id

  ip_protocol                  = "tcp"
  from_port                    = 3100
  to_port                      = 3100
  referenced_security_group_id = aws_security_group.service_managed.id

  description = "Loki logs from service EC2"
}

import {
  to = aws_vpc_security_group_ingress_rule.loki_from_service
  id = "sgr-017719ac2dfe160d4"
}
