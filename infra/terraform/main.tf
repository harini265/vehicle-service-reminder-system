data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "roadwise" {
  name_prefix = "roadwise-"

  ingress {
    description = "Roadwise web"
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "SSH from operator"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "roadwise" }
}

resource "aws_instance" "roadwise" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  key_name                    = var.key_name
  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.roadwise.id]
  user_data                   = templatefile("${path.module}/user_data.sh.tftpl", { image = var.app_image })
  user_data_replace_on_change = true

  root_block_device {
    volume_size = 16
    volume_type = "gp3"
    encrypted   = true
  }

  tags = { Name = "roadwise-reminder" }
}

output "public_ip" {
  value = aws_instance.roadwise.public_ip
}

output "app_url" {
  value = "http://${aws_instance.roadwise.public_ip}:5000"
}
