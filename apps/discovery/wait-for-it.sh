#!/bin/bash
# Enhanced wait-for-it script with better Scrapyd integration
# Author: Ima DaCosta
# Last modified: 2025

# Default values
TIMEOUT=60
QUIET=0
HEALTH_CHECK_INTERVAL=5
STRICT=0
SCRAPYD_URL="${SCRAPYD_URL:-http://localhost:6800}"
SCRAPYD_USERNAME="${SCRAPYD_USERNAME:-admin}"
SCRAPYD_PASSWORD="${SCRAPYD_PASSWORD}"

# Function to check Scrapyd health
check_scrapyd_health() {
    local response
    local status=1
    log "🔍 Checking Scrapyd health at $SCRAPYD_URL"
    response=$(curl -s -f -m 5 -u "${SCRAPYD_USERNAME}:${SCRAPYD_PASSWORD}" "${SCRAPYD_URL}/daemonstatus.json" 2>&1)
    status=$?
    
    if [ $status -eq 0 ]; then
        if echo "$response" | grep -q '"status": "ok"'; then
            log "✅ Scrapyd is healthy"
            return 0
        else
            log "⚠️ Scrapyd returned non-ok status: $response"
            return 1
        fi
    else
        log "❌ Failed to connect to Scrapyd: $response"
        return 1
    fi
}

# Extract host and port from arguments or SCRAPYD_URL
if [ "$1" ]; then
    HOST="$1"
    PORT="${2:-6800}"
else
    # Extract host and port from SCRAPYD_URL with better validation
    if [[ $SCRAPYD_URL =~ ^http[s]?://([^:/]+)(:([0-9]+))? ]]; then
        HOST="${BASH_REMATCH[1]}"
        PORT="${BASH_REMATCH[3]:-6800}"
    else
        HOST="localhost"
        PORT="6800"
    fi
fi

echoerr() {
    if [ "$QUIET" -ne 1 ]; then printf "%s\n" "$*" 1>&2; fi
}

# Enhanced usage with Scrapyd-specific options
usage() {
    cat << USAGE >&2
Usage:
    $cmdname host:port [-t timeout] [-s] [-q] [-- command args]
    -q | --quiet                     Do not output any status messages
    -s | --strict                    Only succeed if Scrapyd health check passes
    -t TIMEOUT | --timeout=timeout   Timeout in seconds, zero for no timeout
    -- COMMAND ARGS                  Execute command with args after the test finishes
USAGE
    exit 1
}

# Function to check Scrapyd health
check_scrapyd_health() {
    local response
    response=$(curl -s -m 5 "http://$HOST:$PORT/daemonstatus.json")
    if echo "$response" | grep -q '"status": "ok"'; then
        return 0
    fi
    return 1
}

wait_for() {
    for i in `seq $TIMEOUT` ; do
        nc -z "$HOST" "$PORT" > /dev/null 2>&1
        
        result=$?
        if [ $result -eq 0 ] ; then
            if [ $# -gt 0 ] ; then
                exec "$@"
            fi
            exit 0
        fi
        sleep 1
    done
    echo "Operation timed out" >&2
    exit 1
}

while [ $# -gt 0 ]
do
    case "$1" in
        *:* )
        HOST=$(printf "%s\n" "$1"| cut -d : -f 1)
        PORT=$(printf "%s\n" "$1"| cut -d : -f 2)
        shift 1
        ;;
        -q | --quiet)
        QUIET=1
        shift 1
        ;;
        -t)
        TIMEOUT="$2"
        if [ "$TIMEOUT" = "" ]; then break; fi
        shift 2
        ;;
        --timeout=*)
        TIMEOUT="${1#*=}"
        shift 1
        ;;
        --)
        shift
        break
        ;;
        --help)
        usage
        ;;
        *)
        echoerr "Unknown argument: $1"
        usage
        ;;
    esac
done

if [ "$HOST" = "" -o "$PORT" = "" ]; then
    echoerr "Error: you need to provide a host and port"
    usage
fi

wait_for "$@"
