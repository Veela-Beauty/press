"""
Watch Tower Alerts package -  split by concern.

All check functions are re-exported here so existing import paths
and Watch Tower rule python_method paths continue to work.
"""
# Deploy
from .deploy_alerts import check_failed_deploys

# Scheduler & errors (+ hidden job-failure / stuck-job checks)
from .scheduler_alerts import (
	check_error_log_spike,
	check_scheduler_health,
	check_worker_queue_depth,
	check_scheduled_job_failures,
	check_failed_background_jobs,
	check_stuck_jobs,
)

# Backup
from .backup_alerts import check_backup_health

# Infrastructure
from .infra_alerts import (
	check_server_disk_usage,
	check_docker_container_health,
	check_ssh_connectivity,
	check_redis_health,
	check_mariadb_health,
	check_microservice_health,
)

# Sites
from .site_alerts import (
	check_site_reachability,
	check_ssl_expiry,
	check_email_queue_growth,
	check_bench_updates_pending,
)

# GitHub
from .github_alerts import check_github_token_health

# Cleanup utility
from ._helpers import cleanup_old_error_logs
