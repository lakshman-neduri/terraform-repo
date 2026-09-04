terraform {
  backend "aws" {
    bucket = "lakshman-terraform-state-bucket"
    key    = var.repo_name
    region = "us-east-1"
    use_lockfile = true
  }
}