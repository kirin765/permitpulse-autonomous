terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.91"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_ecr_repository" "backend" {
  name                 = "permitpulse-backend"
  image_tag_mutability = "MUTABLE"
}

resource "aws_ecr_repository" "frontend" {
  name                 = "permitpulse-frontend"
  image_tag_mutability = "MUTABLE"
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/permitpulse/app"
  retention_in_days = 30
}

resource "aws_cloudwatch_metric_alarm" "api_availability" {
  alarm_name          = "permitpulse-api-availability"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ApiAvailability"
  namespace           = "PermitPulse/SLO"
  period              = 300
  statistic           = "Average"
  threshold           = var.availability_target
  alarm_description   = "Trigger autonomous rollback when API availability drops"
  treat_missing_data  = "breaching"
}

resource "aws_cloudwatch_metric_alarm" "auto_recovery_rate" {
  alarm_name          = "permitpulse-auto-recovery-rate"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  metric_name         = "AutoRecoveryRate"
  namespace           = "PermitPulse/SLO"
  period              = 300
  statistic           = "Average"
  threshold           = var.auto_recovery_target
  alarm_description   = "Alert when autonomous recovery drops below target"
  treat_missing_data  = "breaching"
}
