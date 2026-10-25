resource "aws_instance" "service_managed" {
  ami                    = "ami-0e4ab31f1847c850c"
  instance_type          = "t3.medium"
  subnet_id              = "subnet-0d552e4820a937007"
  vpc_security_group_ids = ["sg-01cfaa76f49d26533"]
  key_name               = "schutz-service-key"
  iam_instance_profile   = "schutz-ec2-ssm-role"

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    http_endpoint               = "enabled"
  }

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    iops        = 3000
    throughput  = 125
    encrypted   = false
  }

  tags = {
    Name = "schutz-service-ec2"
  }
}

import {
  to = aws_instance.service_managed
  id = "i-09af34fe68b6c200c"
}
