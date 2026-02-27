output "backend_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "frontend_repository_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "alarm_names" {
  value = [
    aws_cloudwatch_metric_alarm.api_availability.alarm_name,
    aws_cloudwatch_metric_alarm.auto_recovery_rate.alarm_name,
  ]
}
