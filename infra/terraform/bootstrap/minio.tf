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
  landing_partition_paths = [
    "landing/source=excel/year=*/month=*/day=*/run_id=*/*"
  ]
  raw_excel_partition_paths = [
    "raw/source=excel/year=*/month=*/day=*/run_id=*/*"
  ]
  raw_salesforce_partition_paths = [
    "raw/source=salesforce/object=*/year=*/month=*/day=*/run_id=*/*"
  ]
  raw_partition_paths = concat(
    local.raw_excel_partition_paths,
    local.raw_salesforce_partition_paths
  )
  raw_excel_partition_resources = sort([
    for path in local.raw_excel_partition_paths : "${local.minio_bucket_arn}/${path}"
  ])
  raw_partition_resources = sort([
    for path in local.raw_partition_paths : "${local.minio_bucket_arn}/${path}"
  ])
  quarantine_partition_paths = [
    "quarantine/source=*/year=*/month=*/day=*/run_id=*/*"
  ]
  bronze_partition_paths = [
    "bronze/source=cdc/table=*/year=*/month=*/day=*/hour=*/run_id=*/*",
    "bronze/source=excel/year=*/month=*/day=*/run_id=*/*",
    "bronze/source=salesforce/object=*/year=*/month=*/day=*/run_id=*/*"
  ]
  silver_partition_paths = [
    "silver/domain=*/year=*/month=*/day=*/run_id=*/*"
  ]
  gold_partition_paths = [
    "gold/metric=*/year=*/month=*/day=*/run_id=*/*"
  ]
  landing_partition_resources = sort([
    for path in local.landing_partition_paths : "${local.minio_bucket_arn}/${path}"
  ])
  quarantine_partition_resources = sort([
    for path in local.quarantine_partition_paths : "${local.minio_bucket_arn}/${path}"
  ])
  validation_partition_resources = sort(concat(
    local.landing_partition_resources,
    local.raw_excel_partition_resources,
    local.quarantine_partition_resources
  ))
  curated_partition_resources = sort([
    for path in concat(
      local.quarantine_partition_paths,
      local.bronze_partition_paths,
      local.silver_partition_paths,
      local.gold_partition_paths
    ) : "${local.minio_bucket_arn}/${path}"
  ])
  trino_write_partition_resources = sort([
    for path in concat(
      local.bronze_partition_paths,
      local.silver_partition_paths,
      local.gold_partition_paths
    ) : "${local.minio_bucket_arn}/${path}"
  ])
  trino_read_partition_resources = sort([
    for path in concat(local.silver_partition_paths, local.gold_partition_paths) : "${local.minio_bucket_arn}/${path}"
  ])
  kafka_notification_arn = "arn:minio:sqs::PRIMARY:kafka"
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

resource "minio_s3_bucket_notification" "excel_upload_created" {
  bucket = minio_s3_bucket.lakehouse.bucket

  queue {
    queue_arn     = local.kafka_notification_arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "landing/source=excel/"
  }
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
            "s3:prefix" = [
              "landing/source=excel/*",
              "raw/source=excel/*",
              "raw/source=salesforce/*"
            ]
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
        Resource = sort(concat(local.landing_partition_resources, local.raw_partition_resources))
      }
    ]
  })
}

resource "minio_iam_policy" "validation" {
  name = "minio_validation"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListValidationPrefixes"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [local.minio_bucket_arn]
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "landing/source=excel/*",
              "raw/source=excel/*",
              "quarantine/source=*/*"
            ]
          }
        }
      },
      {
        Sid      = "ReadValidationInputs"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = local.validation_partition_resources
      },
      {
        Sid      = "WriteRawExcelObjects"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = local.raw_excel_partition_resources
      },
      {
        Sid       = "WriteQuarantineObjects"
        Effect    = "Allow"
        Action    = ["s3:PutObject"]
        Resource  = local.quarantine_partition_resources
        Condition = local.kms_write_condition
      },
      {
        Sid    = "ManageValidationMultipartUploads"
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts"
        ]
        Resource = sort(concat(local.raw_excel_partition_resources, local.quarantine_partition_resources))
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
            "s3:prefix" = [
              "raw/source=*/*",
              "quarantine/source=*/*",
              "bronze/source=*/*",
              "silver/domain=*/*",
              "gold/metric=*/*"
            ]
          }
        }
      },
      {
        Sid      = "ReadRawObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = local.raw_partition_resources
      },
      {
        Sid      = "ReadCuratedLayers"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = local.curated_partition_resources
      },
      {
        Sid       = "WriteCuratedLayers"
        Effect    = "Allow"
        Action    = ["s3:PutObject"]
        Resource  = local.curated_partition_resources
        Condition = local.kms_write_condition
      },
      {
        Sid    = "ManageCuratedLayerMultipartUploads"
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts"
        ]
        Resource = local.curated_partition_resources
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
            "s3:prefix" = [
              "raw/source=*/*",
              "quarantine/source=*/*",
              "bronze/source=*/*",
              "silver/domain=*/*",
              "gold/metric=*/*"
            ]
          }
        }
      },
      {
        Sid      = "ReadAllCuratedLayers"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = sort(concat(local.raw_partition_resources, local.curated_partition_resources))
      },
      {
        Sid       = "WriteIcebergMetadata"
        Effect    = "Allow"
        Action    = ["s3:PutObject"]
        Resource  = local.trino_write_partition_resources
        Condition = local.kms_write_condition
      },
      {
        Sid    = "ManageIcebergMultipartUploads"
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts"
        ]
        Resource = local.trino_write_partition_resources
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
            "s3:prefix" = ["silver/domain=*/*", "gold/metric=*/*"]
          }
        }
      },
      {
        Sid      = "ReadBILayers"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = local.trino_read_partition_resources
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

resource "minio_iam_user" "validation" {
  name          = var.minio_validation_user
  secret        = var.minio_validation_secret
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

resource "minio_iam_user_policy_attachment" "validation" {
  user_name   = var.minio_validation_user
  policy_name = minio_iam_policy.validation.name
}

resource "minio_iam_user_policy_attachment" "trino_write" {
  user_name   = var.minio_trino_write_user
  policy_name = minio_iam_policy.trino_write.name
}

resource "minio_iam_user_policy_attachment" "trino_read" {
  user_name   = var.minio_trino_read_user
  policy_name = minio_iam_policy.trino_read.name
}
