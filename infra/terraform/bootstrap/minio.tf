locals {
  minio_bucket_arn = "arn:aws:s3:::${var.minio_bucket_name}"
  kms_enforced_prefixes = [
    "bronze/*",
    "silver/*",
    "gold/*",
    "quarantine/*"
  ]
  kms_enforced_resources = sort([
    for prefix in local.kms_enforced_prefixes : "${local.minio_bucket_arn}/${prefix}"
  ])
  kms_write_condition = {
    StringEquals = {
      "s3:x-amz-server-side-encryption"                = "aws:kms"
      "s3:x-amz-server-side-encryption-aws-kms-key-id" = var.minio_kms_key_id
    }
  }
}

resource "minio_s3_bucket" "lakehouse" {
  bucket = var.minio_bucket_name
  acl    = "private"
}

resource "minio_s3_bucket_server_side_encryption" "lakehouse" {
  bucket          = minio_s3_bucket.lakehouse.bucket
  encryption_type = "aws:kms"
  kms_key_id      = var.minio_kms_key_id
}

resource "minio_s3_bucket_policy" "lakehouse_enforced_prefixes" {
  count  = var.minio_enforce_kms_write_prefixes ? 1 : 0
  bucket = minio_s3_bucket.lakehouse.bucket
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyMissingSSEAlgorithmHeader"
        Effect = "Deny"
        Principal = {
          AWS = ["*"]
        }
        Action   = ["s3:PutObject"]
        Resource = local.kms_enforced_resources
        Condition = {
          Null = {
            "s3:x-amz-server-side-encryption" = [true]
          }
        }
      },
      {
        Sid    = "DenyInvalidSSEAlgorithmHeader"
        Effect = "Deny"
        Principal = {
          AWS = ["*"]
        }
        Action   = ["s3:PutObject"]
        Resource = local.kms_enforced_resources
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = ["aws:kms"]
          }
        }
      },
      {
        Sid    = "DenyMissingKMSKeyHeader"
        Effect = "Deny"
        Principal = {
          AWS = ["*"]
        }
        Action   = ["s3:PutObject"]
        Resource = local.kms_enforced_resources
        Condition = {
          Null = {
            "s3:x-amz-server-side-encryption-aws-kms-key-id" = [true]
          }
        }
      },
      {
        Sid    = "DenyInvalidKMSKeyHeader"
        Effect = "Deny"
        Principal = {
          AWS = ["*"]
        }
        Action   = ["s3:PutObject"]
        Resource = local.kms_enforced_resources
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption-aws-kms-key-id" = [var.minio_kms_key_id]
          }
        }
      }
    ]
  })
}

resource "minio_iam_policy" "ingest" {
  name = "minio_ingest"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListAllowedPrefixes"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [local.minio_bucket_arn]
        Condition = {
          StringLike = {
            "s3:prefix" = ["landing/*", "raw/*"]
          }
        }
      },
      {
        Sid    = "ReadWriteLandingRawObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts"
        ]
        Resource = [
          "${local.minio_bucket_arn}/landing/*",
          "${local.minio_bucket_arn}/raw/*"
        ]
      }
    ]
  })
}

resource "minio_iam_policy" "transform" {
  name = "minio_transform"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListTransformPrefixes"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [local.minio_bucket_arn]
        Condition = {
          StringLike = {
            "s3:prefix" = ["raw/*", "bronze/*", "silver/*", "gold/*", "quarantine/*"]
          }
        }
      },
      {
        Sid      = "ReadRawObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["${local.minio_bucket_arn}/raw/*"]
      },
      {
        Sid      = "ReadCuratedLayers"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = local.kms_enforced_resources
      },
      {
        Sid       = "WriteCuratedLayers"
        Effect    = "Allow"
        Action    = ["s3:PutObject"]
        Resource  = local.kms_enforced_resources
        Condition = local.kms_write_condition
      },
      {
        Sid    = "ManageCuratedLayerMultipartUploads"
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts"
        ]
        Resource = local.kms_enforced_resources
      }
    ]
  })
}

resource "minio_iam_policy" "trino_write" {
  name = "minio_trino_write"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListCuratedPrefixes"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [local.minio_bucket_arn]
        Condition = {
          StringLike = {
            "s3:prefix" = ["raw/*", "bronze/*", "silver/*", "gold/*", "quarantine/*"]
          }
        }
      },
      {
        Sid    = "ReadAllCuratedLayers"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = [
          "${local.minio_bucket_arn}/raw/*",
          "${local.minio_bucket_arn}/bronze/*",
          "${local.minio_bucket_arn}/silver/*",
          "${local.minio_bucket_arn}/gold/*",
          "${local.minio_bucket_arn}/quarantine/*"
        ]
      },
      {
        Sid    = "WriteIcebergMetadata"
        Effect = "Allow"
        Action = ["s3:PutObject"]
        Resource = [
          "${local.minio_bucket_arn}/bronze/*",
          "${local.minio_bucket_arn}/silver/*",
          "${local.minio_bucket_arn}/gold/*"
        ]
        Condition = local.kms_write_condition
      },
      {
        Sid    = "ManageIcebergMultipartUploads"
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts"
        ]
        Resource = [
          "${local.minio_bucket_arn}/bronze/*",
          "${local.minio_bucket_arn}/silver/*",
          "${local.minio_bucket_arn}/gold/*"
        ]
      }
    ]
  })
}

resource "minio_iam_policy" "trino_read" {
  name = "minio_trino_read"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListBIPrefixes"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [local.minio_bucket_arn]
        Condition = {
          StringLike = {
            "s3:prefix" = ["silver/*", "gold/*"]
          }
        }
      },
      {
        Sid    = "ReadBILayers"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = [
          "${local.minio_bucket_arn}/silver/*",
          "${local.minio_bucket_arn}/gold/*"
        ]
      }
    ]
  })
}

resource "minio_iam_user" "ingest" {
  name          = var.minio_ingest_user
  secret        = var.minio_ingest_secret
  force_destroy = true
  update_secret = true
}

resource "minio_iam_user" "transform" {
  name          = var.minio_transform_user
  secret        = var.minio_transform_secret
  force_destroy = true
  update_secret = true
}

resource "minio_iam_user" "trino_write" {
  name          = var.minio_trino_write_user
  secret        = var.minio_trino_write_secret
  force_destroy = true
  update_secret = true
}

resource "minio_iam_user" "trino_read" {
  name          = var.minio_trino_read_user
  secret        = var.minio_trino_read_secret
  force_destroy = true
  update_secret = true
}

resource "minio_iam_user_policy_attachment" "ingest" {
  user_name   = var.minio_ingest_user
  policy_name = minio_iam_policy.ingest.name
}

resource "minio_iam_user_policy_attachment" "transform" {
  user_name   = var.minio_transform_user
  policy_name = minio_iam_policy.transform.name
}

resource "minio_iam_user_policy_attachment" "trino_write" {
  user_name   = var.minio_trino_write_user
  policy_name = minio_iam_policy.trino_write.name
}

resource "minio_iam_user_policy_attachment" "trino_read" {
  user_name   = var.minio_trino_read_user
  policy_name = minio_iam_policy.trino_read.name
}
