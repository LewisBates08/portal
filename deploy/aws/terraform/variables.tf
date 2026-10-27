variable "environment" {
  type = string
  validation { condition = contains(["staging", "production"], var.environment)
    error_message = "Use staging or production." }
}
variable "hostname" {
  type = string
  validation { condition = can(regex("^[a-z0-9][a-z0-9.-]+\\.[a-z]{2,}$", var.hostname))
    error_message = "Supply the controlled production or staging DNS hostname." }
}
variable "sender_domain" { type = string }
variable "alert_email" { type = string }
variable "github_repository" { type = string
  default = "LewisBates08/portal" }
variable "github_oidc_provider_arn" {
  type = string
  description = "Existing account GitHub OIDC provider ARN. Create once in bootstrap."
}
variable "budget_usd" {
  type = number
  description = "Account-wide USD alert budget, converted from the GBP75 ceiling including tax buffer."
  validation { condition = var.budget_usd > 0 && var.budget_usd <= 100
    error_message = "Supply a reviewed USD budget up to 100; this is an alert, not a spending cap." }
}
variable "cost_reviewed" {
  type = bool
  default = false
  validation { condition = var.cost_reviewed
    error_message = "Review current London prices, VAT, exchange rate and temporary staging against GBP75 first." }
}
variable "bootstrap_database_access" {
  type = bool
  default = false
  description = "Temporarily allow the host to read the RDS master secret for first database initialization; revoke afterwards."
}
variable "protect_database" { type = bool
  default = true }
