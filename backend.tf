terraform {
  backend "s3" {
    bucket = "lakshman-terraform-state-bucket"
    key    = var.repo_name
    region = "us-east-1"
    use_lockfile = true
  }
}