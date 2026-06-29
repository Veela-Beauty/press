"""
Press-specific alert checks for Watch Tower.

STUB -  all logic moved to watch_tower/alerts/ package.
This file re-exports for backward compatibility with existing
Watch Tower rule python_method paths.
"""
# Re-export all check functions so existing paths work
from .alerts import (  # noqa: F401
	check_error_log_spike,
	check_failed_deploys,
	check_scheduler_health,
	check_scheduled_job_failures,
	check_failed_background_jobs,
	check_stuck_jobs,
	check_backup_health,
	check_github_token_health,
	check_server_disk_usage,
	check_docker_container_health,
	check_ssh_connectivity,
	check_redis_health,
	check_mariadb_health,
	check_site_reachability,
	check_ssl_expiry,
	check_email_queue_growth,
	check_worker_queue_depth,
	check_bench_updates_pending,
	cleanup_old_error_logs,
)
