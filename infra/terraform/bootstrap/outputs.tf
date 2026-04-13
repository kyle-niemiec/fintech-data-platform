output "minio_bucket_name" {
  description = "Provisioned MinIO bucket"
  value       = minio_s3_bucket.lakehouse.bucket
}

output "minio_kms_key_id" {
  description = "Provisioned MinIO KMS key id used by SSE-KMS policy enforcement"
  value       = var.minio_kms_key_id
}

output "event_append_db_user" {
  description = "Append-only event-store runtime DB login"
  value       = postgresql_role.event_append_runtime.name
}
