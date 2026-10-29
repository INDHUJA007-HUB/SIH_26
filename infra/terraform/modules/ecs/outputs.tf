output "cluster_id" {
  description = "ECS cluster ID"
  value       = aws_ecs_cluster.main.id
}

output "cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "alb_security_group_id" {
  description = "Public ALB security group ID"
  value       = aws_security_group.alb.id
}

output "app_tasks_security_group_id" {
  description = "Application zone tasks security group ID"
  value       = aws_security_group.app_tasks.id
}

output "untrusted_workers_security_group_id" {
  description = "Untrusted processing zone security group ID"
  value       = aws_security_group.untrusted_workers.id
}

output "connector_workers_security_group_id" {
  description = "Integration zone connector security group ID"
  value       = aws_security_group.connector_workers.id
}

output "task_definition_arns" {
  description = "Map of task definition ARNs by deployment unit"
  value       = { for k, v in aws_ecs_task_definition.tasks : k => v.arn }
}
