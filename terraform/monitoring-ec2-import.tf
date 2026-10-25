resource "aws_instance" "monitoring_managed" {
  ami                    = "ami-0e4ab31f1847c850c"
  instance_type          = "t3.large"
  subnet_id              = "subnet-028bd179fda958fca"
  vpc_security_group_ids = ["sg-074a3fa99695f104f"]
  key_name               = "schutz-service-key"
  iam_instance_profile   = "schutz-ec2-ssm-role"

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    http_endpoint               = "enabled"
  }

  root_block_device {
    volume_size = 50
    volume_type = "gp3"
    iops        = 3000
    throughput  = 125
    encrypted   = true
  }

  tags = {
    Name = "schutz-monitor-ec2"
  }
}

import {
  to = aws_instance.monitoring_managed
  id = "i-066c8eee143b5cdff"
}
