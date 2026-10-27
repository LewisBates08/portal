terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
  backend "s3" {}
}
provider "aws" {
  region = "eu-west-2"
  default_tags { tags = { Project = "searchroom", Environment = var.environment } }
}
data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" { state = "available" }
data "aws_ssm_parameter" "ubuntu" { name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id" }
locals {
  name = "searchroom-${var.environment}"
  account = data.aws_caller_identity.current.account_id
}
