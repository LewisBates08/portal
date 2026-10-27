resource "aws_sns_topic" "alerts" { name = "${local.name}-alerts" }
resource "aws_sns_topic_subscription" "email" { topic_arn = aws_sns_topic.alerts.arn
  protocol = "email"
  endpoint = var.alert_email }
resource "aws_budgets_budget" "pilot" {
  count = var.environment == "production" ? 1 : 0
  name = "searchroom-account-ceiling"
  budget_type = "COST"
  limit_amount = tostring(var.budget_usd)
  limit_unit = "USD"
  time_unit = "MONTHLY"
  dynamic "notification" {
    for_each = { for item in setproduct([50, 80, 100], ["ACTUAL", "FORECASTED"]) : "${item[0]}-${item[1]}" => item }
    content { comparison_operator = "GREATER_THAN"
      threshold = notification.value[0]
      threshold_type = "PERCENTAGE"
      notification_type = notification.value[1]
      subscriber_email_addresses = [var.alert_email] }
  }
}
resource "aws_cloudwatch_metric_alarm" "native" {
  for_each = {
    instance = { namespace = "AWS/EC2", metric = "StatusCheckFailed", limit = 0, comparison = "GreaterThanThreshold", statistic = "Maximum", dimensions = { InstanceId = aws_instance.app.id } },
    cpu = { namespace = "AWS/EC2", metric = "CPUUtilization", limit = 80, comparison = "GreaterThanThreshold", statistic = "Average", dimensions = { InstanceId = aws_instance.app.id } },
    credits = { namespace = "AWS/EC2", metric = "CPUCreditBalance", limit = 10, comparison = "LessThanThreshold", statistic = "Minimum", dimensions = { InstanceId = aws_instance.app.id } },
    db_storage = { namespace = "AWS/RDS", metric = "FreeStorageSpace", limit = 4294967296, comparison = "LessThanThreshold", statistic = "Minimum", dimensions = { DBInstanceIdentifier = aws_db_instance.portal.id } },
    db_connections = { namespace = "AWS/RDS", metric = "DatabaseConnections", limit = 45, comparison = "GreaterThanThreshold", statistic = "Maximum", dimensions = { DBInstanceIdentifier = aws_db_instance.portal.id } },
    db_cpu = { namespace = "AWS/RDS", metric = "CPUUtilization", limit = 80, comparison = "GreaterThanThreshold", statistic = "Average", dimensions = { DBInstanceIdentifier = aws_db_instance.portal.id } }
  }
  alarm_name = "${local.name}-${each.key}"
  namespace = each.value.namespace
  metric_name = each.value.metric
  threshold = each.value.limit
  comparison_operator = each.value.comparison
  statistic = each.value.statistic
  dimensions = each.value.dimensions
  period = 300
  evaluation_periods = 2
  treat_missing_data = "missing"
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions = [aws_sns_topic.alerts.arn]
}
resource "aws_cloudwatch_metric_alarm" "host" {
  for_each = { Healthy = 1, DiskFreePercent = 20, BackupFresh = 1, CleanupFresh = 1 }
  alarm_name = "${local.name}-${each.key}"
  namespace = "Searchroom"
  metric_name = each.key
  dimensions = { Environment = var.environment }
  threshold = each.value
  comparison_operator = "LessThanThreshold"
  statistic = "Minimum"
  period = 900
  evaluation_periods = 2
  treat_missing_data = "breaching"
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions = [aws_sns_topic.alerts.arn]
}
resource "aws_ses_domain_identity" "sender" { domain = var.sender_domain }
resource "aws_ses_domain_dkim" "sender" { domain = aws_ses_domain_identity.sender.domain }
resource "aws_ses_identity_notification_topic" "feedback" {
  for_each = toset(["Bounce", "Complaint"])
  topic_arn = aws_sns_topic.alerts.arn
  notification_type = each.value
  identity = aws_ses_domain_identity.sender.arn
  include_original_headers = false
}
resource "aws_sns_topic_policy" "ses" {
  arn = aws_sns_topic.alerts.arn
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Principal = { Service = "ses.amazonaws.com" }, Action = "sns:Publish", Resource = aws_sns_topic.alerts.arn, Condition = { StringEquals = { "AWS:SourceAccount" = local.account }, ArnEquals = { "AWS:SourceArn" = aws_ses_domain_identity.sender.arn } } },
    { Effect = "Allow", Principal = { Service = "cloudwatch.amazonaws.com" }, Action = "sns:Publish", Resource = aws_sns_topic.alerts.arn, Condition = { StringEquals = { "AWS:SourceAccount" = local.account } } }
  ] })
}
