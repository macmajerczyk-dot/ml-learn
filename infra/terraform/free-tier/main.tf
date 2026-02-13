# ---------------------------------------------------------------------------
# AWS Free-Tier Infrastructure for ML Pipeline
# Single EC2 t2.micro + Docker Compose (no EKS, no MSK — $0/mo)
# ---------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------
variable "aws_region" {
  default = "eu-west-1"
}

variable "project_name" {
  default = "ml-pipeline"
}

variable "key_pair_name" {
  description = "Name of an existing EC2 key pair for SSH access"
  type        = string
}

variable "my_ip" {
  description = "Your public IP for SSH access (e.g. 1.2.3.4/32). Use 0.0.0.0/0 to allow all."
  type        = string
  default     = "0.0.0.0/0"
}

variable "git_repo_url" {
  description = "Git repository URL to clone on the EC2 instance"
  type        = string
  default     = "https://github.com/macmajerczyk-dot/ml-learn.git"
}

# ---------------------------------------------------------------------------
# Data: Latest Amazon Linux 2023 AMI
# ---------------------------------------------------------------------------
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ---------------------------------------------------------------------------
# VPC: Use default VPC (free, no NAT gateway needed)
# ---------------------------------------------------------------------------
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ---------------------------------------------------------------------------
# Security Group
# ---------------------------------------------------------------------------
resource "aws_security_group" "ml_pipeline" {
  name_prefix = "${var.project_name}-"
  vpc_id      = data.aws_vpc.default.id

  # SSH
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
    description = "SSH access"
  }

  # Gateway API
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Gateway API"
  }

  # Prometheus (optional)
  ingress {
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
    description = "Prometheus"
  }

  # Grafana (optional)
  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
    description = "Grafana"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-sg", Project = var.project_name }
}

# ---------------------------------------------------------------------------
# ECR Repositories (free tier: 500MB storage)
# ---------------------------------------------------------------------------
resource "aws_ecr_repository" "gateway" {
  name                 = "${var.project_name}-gateway"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = false
  }

  tags = { Project = var.project_name }
}

resource "aws_ecr_repository" "worker" {
  name                 = "${var.project_name}-worker"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = false
  }

  tags = { Project = var.project_name }
}

# Keep only last 5 images to stay within free-tier storage
resource "aws_ecr_lifecycle_policy" "gateway" {
  repository = aws_ecr_repository.gateway.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_ecr_lifecycle_policy" "worker" {
  repository = aws_ecr_repository.worker.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

# ---------------------------------------------------------------------------
# IAM Role for EC2 to pull from ECR
# ---------------------------------------------------------------------------
resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  tags = { Project = var.project_name }
}

resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# ---------------------------------------------------------------------------
# EC2 Instance (t2.micro — free tier eligible)
# ---------------------------------------------------------------------------
resource "aws_instance" "ml_pipeline" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t2.micro"
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.ml_pipeline.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  subnet_id              = data.aws_subnets.default.ids[0]

  associate_public_ip_address = true

  root_block_device {
    volume_size = 20  # GB — free tier allows up to 30GB
    volume_type = "gp3"
  }

  user_data = <<-EOF
    #!/bin/bash
    set -ex

    # --- Swap (2GB) to handle ML model memory ---
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile swap swap defaults 0 0' >> /etc/fstab
    sysctl vm.swappiness=60

    # --- Install Docker ---
    dnf update -y
    dnf install -y docker git
    systemctl enable docker
    systemctl start docker
    usermod -aG docker ec2-user

    # --- Install Docker Compose ---
    DOCKER_COMPOSE_VERSION="v2.32.4"
    curl -L "https://github.com/docker/compose/releases/download/$${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" \
      -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

    # --- Install AWS CLI (for ECR login) ---
    dnf install -y aws-cli

    # --- Clone repo ---
    cd /home/ec2-user
    git clone ${var.git_repo_url} app || true
    chown -R ec2-user:ec2-user /home/ec2-user/app

    # --- Create deploy script ---
    cat > /home/ec2-user/deploy.sh << 'DEPLOY'
    #!/bin/bash
    set -e
    cd /home/ec2-user/app

    # Login to ECR
    REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

    # Pull latest images
    docker compose -f docker-compose-freetier.yml pull

    # Deploy
    docker compose -f docker-compose-freetier.yml up -d --remove-orphans

    echo "Deployed successfully!"
    docker compose -f docker-compose-freetier.yml ps
    DEPLOY
    chmod +x /home/ec2-user/deploy.sh
    chown ec2-user:ec2-user /home/ec2-user/deploy.sh

    echo "Setup complete. Run /home/ec2-user/deploy.sh to deploy."
  EOF

  tags = {
    Name    = "${var.project_name}-server"
    Project = var.project_name
  }
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "instance_public_ip" {
  value = aws_instance.ml_pipeline.public_ip
}

output "instance_public_dns" {
  value = aws_instance.ml_pipeline.public_dns
}

output "ecr_gateway_url" {
  value = aws_ecr_repository.gateway.repository_url
}

output "ecr_worker_url" {
  value = aws_ecr_repository.worker.repository_url
}

output "ssh_command" {
  value = "ssh -i <your-key>.pem ec2-user@${aws_instance.ml_pipeline.public_ip}"
}

output "api_url" {
  value = "http://${aws_instance.ml_pipeline.public_ip}:8000"
}
