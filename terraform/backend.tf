terraform {
  backend "s3" {
    bucket       = "schutz-terraform-state-2026"
    key          = "schutz/terraform.tfstate"
    region       = "ap-northeast-2"
    encrypt      = true
    use_lockfile = true
  }
}
