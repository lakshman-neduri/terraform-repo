terraform {
    required_version = "~> 1.15.1"
    required_providers {
        aws = {
            source = "hashicorp/aws"
            required_version = "~> 6.0"
        }
    }
}


provider "aws" {
    region = "us-east-1"
    assume_role {
        role_arn = "arn:aws:iam::431662316646:role/terraform-iam-admin-role"
    }
}