#!/bin/bash
set -euo pipefail

# Injects infrastructure-level faults into running blueprint-guardain containers
# using Pumba (https://github.com/alexei-led/pumba), to simulate the kind of
# flaky dependency/network behavior a live system sees in production.
#
# Requires Docker (no separate Pumba install — runs via `docker run gaiaadm/pumba`).
#
# Usage:
#   scripts/chaos_infra.sh pause   guardain_kafka        [duration]   # default 30s
#   scripts/chaos_infra.sh kill    guardain_analysis_pg                # then: docker compose up -d postgres
#   scripts/chaos_infra.sh delay   guardain_kafka  [ms]  [duration]   # default 3000ms, 30s
#   scripts/chaos_infra.sh loss    guardain_kafka  [pct] [duration]   # default 50%, 30s
#
# Container names: guardain_kafka, guardain_analysis_pg, guardain_schema_registry,
#                   guardain_ingestion_service, guardain_analysis_worker,
#                   guardain_notification_worker, guardain_dashboard_service

PUMBA_IMAGE="gaiaadm/pumba"
NETEM_IMAGE="gaiadocker/iproute2"

run_pumba() {
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock "$PUMBA_IMAGE" "$@"
}

action="${1:-}"
container="${2:-}"

if [[ -z "$action" || -z "$container" ]]; then
  echo "Usage: $0 <pause|kill|delay|loss> <container> [value] [duration]"
  exit 1
fi

case "$action" in
  pause)
    duration="${3:-30s}"
    echo "Pausing $container for $duration ..."
    run_pumba pumba pause --duration "$duration" "$container"
    ;;
  kill)
    echo "Killing $container (won't restart automatically — no restart policy is set) ..."
    run_pumba pumba kill "$container"
    echo "Bring it back with: docker compose up -d <service-name>"
    ;;
  delay)
    ms="${3:-3000}"
    duration="${4:-30s}"
    echo "Adding ${ms}ms latency to $container for $duration ..."
    run_pumba pumba netem --duration "$duration" --tc-image "$NETEM_IMAGE" delay --time "$ms" "$container"
    ;;
  loss)
    pct="${3:-50}"
    duration="${4:-30s}"
    echo "Dropping ${pct}% of packets on $container for $duration ..."
    run_pumba pumba netem --duration "$duration" --tc-image "$NETEM_IMAGE" loss --percent "$pct" "$container"
    ;;
  *)
    echo "Unknown action: $action (expected pause|kill|delay|loss)"
    exit 1
    ;;
esac
