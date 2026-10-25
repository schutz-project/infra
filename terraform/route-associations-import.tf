resource "aws_route_table_association" "service_managed" {
  subnet_id      = "subnet-0d552e4820a937007"
  route_table_id = "rtb-0e9f1e568ca8e9329"
}

import {
  to = aws_route_table_association.service_managed
  id = "subnet-0d552e4820a937007/rtb-0e9f1e568ca8e9329"
}

resource "aws_route_table_association" "monitoring_managed" {
  subnet_id      = "subnet-028bd179fda958fca"
  route_table_id = "rtb-0e9f1e568ca8e9329"
}

import {
  to = aws_route_table_association.monitoring_managed
  id = "subnet-028bd179fda958fca/rtb-0e9f1e568ca8e9329"
}
