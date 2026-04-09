terraform {
  required_version = ">= 1.6.0"

  required_providers {
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "~> 1.26"
    }

    minio = {
      source  = "aminueza/minio"
      version = "~> 3.0"
    }
  }
}
