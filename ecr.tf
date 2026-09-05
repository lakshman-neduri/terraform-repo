resource "aws_ecr_repository" "frontend_poc" {
  count = contains(["dev","prod"], terraform.workspace) ? 1 : 0
  name                 = local.ecr_repository_name
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  tags = {
    Env = terraform.workspace
  }
}
