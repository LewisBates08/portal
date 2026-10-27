resource "aws_db_subnet_group" "portal" { name = local.name
  subnet_ids = aws_subnet.database[*].id }
resource "aws_db_parameter_group" "portal" {
  name = local.name
  family = "postgres17"
  parameter { name = "rds.force_ssl"
    value = "1" }
  parameter { name = "max_connections"
    value = "60"
    apply_method = "pending-reboot" }
}
resource "aws_db_instance" "portal" {
  identifier = local.name
  engine = "postgres"
  engine_version = "17"
  instance_class = "db.t4g.micro"
  allocated_storage = 20
  storage_type = "gp3"
  storage_encrypted = true
  db_name = "searchroom"
  username = "searchroom_owner"
  manage_master_user_password = true
  db_subnet_group_name = aws_db_subnet_group.portal.name
  parameter_group_name = aws_db_parameter_group.portal.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible = false
  multi_az = false
  backup_retention_period = 7
  backup_window = "02:00-03:00"
  maintenance_window = "sun:03:00-sun:04:00"
  auto_minor_version_upgrade = true
  deletion_protection = var.protect_database
  skip_final_snapshot = false
  final_snapshot_identifier = "${local.name}-final"
  copy_tags_to_snapshot = true
  enabled_cloudwatch_logs_exports = ["postgresql"]
}
resource "aws_secretsmanager_secret" "app" {
  name = "${local.name}/application"
  description = "Populated interactively outside Terraform; never put secret values in state."
  recovery_window_in_days = 30
}
resource "aws_kms_key" "backup" { description = "${local.name} backup encryption"
  enable_key_rotation = true
  deletion_window_in_days = 30 }
resource "aws_s3_bucket" "backup" { bucket = "${local.name}-${local.account}-backups" }
resource "aws_s3_bucket" "releases" { bucket = "${local.name}-${local.account}-releases" }
resource "aws_s3_bucket_public_access_block" "private" {
  for_each = { backup = aws_s3_bucket.backup.id, releases = aws_s3_bucket.releases.id }
  bucket = each.value
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "backup" {
  bucket = aws_s3_bucket.backup.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "aws:kms"
    kms_master_key_id = aws_kms_key.backup.arn }
    bucket_key_enabled = true }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "releases" {
  bucket = aws_s3_bucket.releases.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}
resource "aws_s3_bucket_lifecycle_configuration" "backup" {
  bucket = aws_s3_bucket.backup.id
  rule { id = "expire-exports"
    status = "Enabled"
    filter { prefix = "postgres/" }
    expiration { days = 30 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 } }
}
resource "aws_s3_bucket_lifecycle_configuration" "releases" {
  bucket = aws_s3_bucket.releases.id
  rule { id = "expire-bundles"
    status = "Enabled"
    filter { prefix = "releases/" }
    expiration { days = 90 } }
}
resource "aws_s3_bucket_policy" "tls" {
  for_each = { backup = aws_s3_bucket.backup, releases = aws_s3_bucket.releases }
  bucket = each.value.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Deny", Principal = "*", Action = "s3:*", Resource = [each.value.arn, "${each.value.arn}/*"], Condition = { Bool = { "aws:SecureTransport" = "false" } } }] })
}
resource "aws_ecr_repository" "portal" {
  name = local.name
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}
