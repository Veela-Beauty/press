#!/bin/sh
# Sanad server maintenance - privileged ops invoked by the Frappe bench through a
# fixed sudoers grant. Root-owned + non-writable by frappe; actions are hardcoded
# and all input is validated here, so the sudoers grant cannot be abused.
# Source of truth: press repo press/infra/host/maintenance.sh. Installed copy:
# /opt/sanad/maintenance.sh (root:root 0755). Prints exactly one "RESULT ..." line.
set -eu

action="${1:-}"

reg_vol() { docker inspect -f '{{range .Mounts}}{{.Source}}{{end}}' registry; }

case "$action" in
  registry-gc)
    vol=$(reg_vol)
    before=$(du -sk "$vol" 2>/dev/null | cut -f1)
    docker cp registry:/etc/docker/registry/config.yml /tmp/reg-gc-config.yml
    docker stop registry >/dev/null
    docker run --rm --volumes-from registry -v /tmp/reg-gc-config.yml:/etc/docker/registry/config.yml:ro \
      registry:2 garbage-collect --delete-untagged /etc/docker/registry/config.yml >/tmp/reg-gc.log 2>&1 || true
    docker start registry >/dev/null
    rm -f /tmp/reg-gc-config.yml
    after=$(du -sk "$vol" 2>/dev/null | cut -f1)
    blobs=$(grep -c 'Deleting blob' /tmp/reg-gc.log 2>/dev/null || true)
    [ -n "$blobs" ] || blobs=0
    rm -f /tmp/reg-gc.log
    freed=$(( (before - after) / 1024 ))
    echo "RESULT registry-gc: freed ${freed}MB, ${blobs} blobs deleted"
    ;;
  backup-retention)
    days="${2:-}"
    apply="${3:-}"
    case "$days" in (''|*[!0-9]*) echo "RESULT error: days must be an integer"; exit 2;; esac
    [ "$days" -ge 1 ] || { echo "RESULT error: days must be >= 1"; exit 2; }
    base=/opt/minio/data/press-uploads
    [ -d "$base" ] || { echo "RESULT error: $base not found"; exit 2; }
    now=$(date +%s)
    cutoff=$(( now - days * 86400 ))
    removed=0; freed_kb=0; sites=0
    for site in "$base"/*/; do
      [ -d "$site" ] || continue
      sites=$((sites + 1))
      # newest backup (highest timestamp prefix) is ALWAYS kept, per site
      newest=$(ls -1 "$site" 2>/dev/null | grep -E '^[0-9]+_' | sort -t_ -k1,1nr | head -1)
      for b in "$site"*/; do
        [ -d "$b" ] || continue
        name=$(basename "$b")
        ts=${name%%_*}
        case "$ts" in (''|*[!0-9]*) continue;; esac   # skip anything not <ts>_...
        [ "$name" = "$newest" ] && continue            # never delete the newest
        if [ "$ts" -lt "$cutoff" ]; then
          kb=$(du -sk "$b" 2>/dev/null | cut -f1)
          if [ "$apply" = "--apply" ]; then rm -rf "$b"; fi
          removed=$((removed + 1)); freed_kb=$((freed_kb + kb))
        fi
      done
    done
    mode=dryrun; [ "$apply" = "--apply" ] && mode=applied
    echo "RESULT backup-retention ($mode, keep ${days}d, ${sites} sites): ${removed} old backups, $((freed_kb / 1024))MB"
    ;;
  *)
    echo "RESULT error: unknown action '${action}'"; exit 1;;
esac
