variable "aws_region" {
  description = "AWS region for PermitPulse"
  type        = string
  default     = "us-east-1"
}

variable "availability_target" {
  description = "SLO target for API availability"
  type        = number
  default     = 99.9
}

variable "auto_recovery_target" {
  description = "SLO target for autonomous recovery success"
  type        = number
  default     = 95
}
