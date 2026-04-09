output "minio_bucket_name" {
  description = "Provisioned MinIO bucket"
  value       = minio_s3_bucket.lakehouse.bucket
}
