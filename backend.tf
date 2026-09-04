terraform {
  backend "s3" {
    bucket = "lakshman-terraform-state-bucket"
    key    = "terraform-repo"
    region = "us-east-1"
    use_lockfile = true
  }
}