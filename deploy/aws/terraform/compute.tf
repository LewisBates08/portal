resource "aws_cloudwatch_log_group" "app" { name = "/searchroom/${var.environment}"
  retention_in_days = 14 }
resource "aws_cloudwatch_log_group" "database" { name = "/aws/rds/instance/${local.name}/postgresql"
  retention_in_days = 14 }
resource "aws_instance" "app" {
  ami = data.aws_ssm_parameter.ubuntu.value
  instance_type = "t3.small"
  subnet_id = aws_subnet.app.id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile = aws_iam_instance_profile.host.name
  # The EIP is attached after instance creation; bootstrap waits for connectivity.
  associate_public_ip_address = false
  credit_specification { cpu_credits = "standard" }
  metadata_options { http_tokens = "required"
    http_put_response_hop_limit = 1
    http_endpoint = "enabled" }
  root_block_device { volume_size = 20
    volume_type = "gp3"
    encrypted = true }
  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/../host/cloud-init.sh.tftpl", {
    config = base64encode(jsonencode({
      environment = var.environment, hostname = var.hostname,
      region = "eu-west-2", secret_id = aws_secretsmanager_secret.app.arn,
      master_secret_id = aws_db_instance.portal.master_user_secret[0].secret_arn,
      database_host = aws_db_instance.portal.address, database_name = "searchroom",
      repository = aws_ecr_repository.portal.repository_url,
      backup_bucket = aws_s3_bucket.backup.id, backup_key = aws_kms_key.backup.arn,
      releases_bucket = aws_s3_bucket.releases.id, log_group = aws_cloudwatch_log_group.app.name
    }))
  })
  tags = { Name = local.name }
  depends_on = [aws_iam_role_policy.host, aws_iam_role_policy_attachment.ssm, aws_route_table_association.public]
  lifecycle { ignore_changes = [ami] }
}
resource "aws_eip" "app" { domain = "vpc"
  instance = aws_instance.app.id
  depends_on = [aws_internet_gateway.portal] }
resource "aws_ssm_document" "deploy" {
  name = "${local.name}-deploy"
  document_type = "Command"
  content = jsonencode({
    schemaVersion = "2.2", description = "Install a reviewed host bundle and deploy exact tested images",
    parameters = {
      Release = { type = "String", allowedPattern = "^[a-f0-9]{40}$", interpolationType = "ENV_VAR" },
      BundleSha256 = { type = "String", allowedPattern = "^[a-f0-9]{64}$", interpolationType = "ENV_VAR" },
      RuntimeDigest = { type = "String", allowedPattern = "^sha256:[a-f0-9]{64}$", interpolationType = "ENV_VAR" },
      OperationsDigest = { type = "String", allowedPattern = "^sha256:[a-f0-9]{64}$", interpolationType = "ENV_VAR" }
    },
    mainSteps = [{ action = "aws:runShellScript", name = "deploy", inputs = { timeoutSeconds = "1200", runCommand = [
      "set -eu",
      "cloud-init status --wait >/dev/null",
      "test -f /etc/searchroom/host.json",
      "work=$(mktemp -d)",
      "trap 'rm -rf \"$work\"' EXIT",
      "aws s3 cp s3://${aws_s3_bucket.releases.id}/releases/$SSM_Release/host.tar.gz \"$work/host.tar.gz\" --region eu-west-2 --only-show-errors",
      "echo \"$SSM_BundleSha256  $work/host.tar.gz\" | sha256sum --check --status",
      "mkdir \"$work/bundle\"",
      "tar -xzf \"$work/host.tar.gz\" -C \"$work/bundle\" --no-same-owner",
      "bash \"$work/bundle/install.sh\"",
      "/opt/searchroom/host/control.py deploy $SSM_RuntimeDigest $SSM_OperationsDigest"
    ] } }]
  })
}
output "host_ip" { value = aws_eip.app.public_ip }
output "instance_id" { value = aws_instance.app.id }
output "ecr_repository" { value = aws_ecr_repository.portal.repository_url }
output "release_role_arn" { value = aws_iam_role.release.arn }
output "release_bucket" { value = aws_s3_bucket.releases.id }
output "deploy_document" { value = aws_ssm_document.deploy.name }
output "application_secret_arn" { value = aws_secretsmanager_secret.app.arn }
output "ses_verification" { value = aws_ses_domain_identity.sender.verification_token }
output "ses_dkim_tokens" { value = aws_ses_domain_dkim.sender.dkim_tokens }
