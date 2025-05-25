#!/bin/bash
set -e

# Configuration
MAX_RETRIES=5
RETRY_DELAY=10
ENV="${DISCOVERY_ENV:-production}"
EXPECTED_SPIDERS=("quick" "status" "multi" "seo" "visual" "workflow")
SCRAPYD_URL="${SCRAPYD_URL:-http://localhost:6800}"
PROJECT_NAME="${PROJECT_NAME:-discovery}"

# Logging setup
LOGDIR="./logs"
LOGFILE="${LOGDIR}/spider-deployment-$(date +'%Y%m%d').log"

# Create log directory if it doesn't exist
mkdir -p "${LOGDIR}" 2>/dev/null || true

# Logger function with log levels
log() {
    local level=$1
    local message=$2
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    echo "[$timestamp][$level] $message" | tee -a "$LOGFILE"
}

# Convenience logging functions
log_info() { log "INFO" "$1"; }
log_error() { log "ERROR" "$1"; }
log_warn() { log "WARN" "$1"; }
log_success() { log "SUCCESS" "$1"; }

# Function to deploy a spider with retries
deploy_spider() {
    local spider_name=$1
    local attempt=1
    local max_deploy_attempts=3
    local deploy_delay=5
    local success=false

    while [ $attempt -le $max_deploy_attempts ] && [ "$success" = false ]; do
        log_info "📦 Deploying spider '$spider_name' (attempt $attempt/$max_deploy_attempts)"
        
        response=$(scrapyd-deploy discovery -p $PROJECT_NAME 2>&1)
        if [ $? -eq 0 ]; then
            log_success "✅ Successfully deployed spider '$spider_name'"
            success=true
            break
        else
            log_warn "⚠️ Failed to deploy spider '$spider_name' (attempt $attempt): $response"
            attempt=$((attempt + 1))
            if [ $attempt -le $max_deploy_attempts ]; then
                log_info "⏳ Waiting ${deploy_delay}s before retrying..."
                sleep $deploy_delay
                deploy_delay=$((deploy_delay * 2))  # Exponential backoff
            fi
        fi
    done

    if [ "$success" = false ]; then
        log_error "❌ Failed to deploy spider '$spider_name' after $max_deploy_attempts attempts"
        return 1
    fi
    return 0
}

# Function to check Scrapyd status with improved error handling
check_scrapyd_status() {
    local response
    local curl_cmd="curl -s -m 5"
    
    # Add authentication if credentials are set
    if [[ -n "${SCRAPYD_USERNAME}" && -n "${SCRAPYD_PASSWORD}" ]]; then
        curl_cmd+=" -u \"${SCRAPYD_USERNAME}:${SCRAPYD_PASSWORD}\""
    fi
    
    # Build the complete curl command
    curl_cmd+=" \"${SCRAPYD_URL}/daemonstatus.json\""
    
    # Execute the curl command
    response=$(eval $curl_cmd)
    local status=$?
    
    if [[ $status -ne 0 ]]; then
        log_error "❌ Failed to connect to Scrapyd (curl exit code: $status)"
        return 1
    fi
    
    if ! echo "$response" | jq -e . >/dev/null 2>&1; then
        log_error "❌ Invalid JSON response from Scrapyd: $response"
        return 1
    fi
    
    if echo "$response" | grep -q '"status": "ok"'; then
        log_success "✅ Scrapyd is running and healthy"
        return 0
    else
        log_error "❌ Scrapyd returned non-ok status: $response"
        return 1
    fi
}

# Function to debug spider discovery
debug_spider_discovery() {
    local spider_name=$1
    log_info "🔍 Debugging spider discovery for '$spider_name'"
    
    # Check egg contents
    if [ -f "dist/${PROJECT_NAME}-"*".egg" ]; then
        local egg_file=$(ls dist/${PROJECT_NAME}-*.egg | head -n 1)
        log_info "📦 Inspecting egg file: $egg_file"
        unzip -l "$egg_file" | grep -i "spider" | tee -a "$LOGFILE"
        
        # Extract and inspect spider files
        local temp_dir=$(mktemp -d)
        unzip -q "$egg_file" -d "$temp_dir"
        
        # Check spider module initialization
        if [ -f "$temp_dir/discovery/spiders/__init__.py" ]; then
            log_info "📄 Contents of spiders/__init__.py:"
            cat "$temp_dir/discovery/spiders/__init__.py" | tee -a "$LOGFILE"
        else
            log_warn "⚠️ spiders/__init__.py not found in egg"
        fi
        
        # List all spider files
        log_info "🔍 Spider files in egg:"
        find "$temp_dir" -type f -name "*_spider.py" | tee -a "$LOGFILE"
        
        # Cleanup
        rm -rf "$temp_dir"
    else
        log_error "❌ No egg file found in dist directory"
    fi
}

# Function to verify all expected spiders are deployed
verify_spiders() {
    local response missing_spiders=()
    log_info "🔍 Verifying spider deployment..."
    
    response=$(curl -s -m 5 -u "${SCRAPYD_USERNAME}:${SCRAPYD_PASSWORD}" "${SCRAPYD_URL}/listspiders.json?project=${PROJECT_NAME}")
    
    if [[ $? -ne 0 ]]; then
        log_error "❌ Failed to retrieve spider list"
        return 1
    fi
    
    # Log raw response for debugging
    log_info "📄 Raw Scrapyd response: $response"
    
    # Extract spider names from response
    spiders=$(echo "$response" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    if "spiders" in data:
        print("\n".join(data["spiders"]))
    else:
        print("No spiders key in response")
except Exception as e:
    print(f"Error parsing response: {e}")
')
    
    # Check for each expected spider
    for spider in "${EXPECTED_SPIDERS[@]}"; do
        if ! echo "$spiders" | grep -q "^$spider$"; then
            missing_spiders+=("$spider")
            # Debug this specific spider
            debug_spider_discovery "$spider"
        fi
    done
    
    if [ ${#missing_spiders[@]} -ne 0 ]; then
        log_error "❌ Missing spiders: ${missing_spiders[*]}"
        return 1
    fi
    
    return 0
}

# Function to deploy spiders
deploy_spiders() {
    local retry_count=0
    local scrapyd_deploy_cmd="scrapyd-deploy $ENV -p discovery"

    # Add authentication to scrapyd-deploy command if credentials are set
    if [[ -n "${SCRAPYD_USERNAME}" && -n "${SCRAPYD_PASSWORD}" ]]; then
        export SCRAPYD_AUTH="${SCRAPYD_USERNAME}:${SCRAPYD_PASSWORD}"
    fi

    while [ $retry_count -lt $MAX_RETRIES ]; do
        if check_scrapyd_status; then
            log_info "📦 Deploying spiders in ${ENV} environment..."
            
            # Deploy with environment-specific settings
            if $scrapyd_deploy_cmd; then
                log_info "🔍 Verifying spider deployment..."
                sleep 5  # Give Scrapyd time to process the deployment
                
                if verify_spiders; then
                    log_success "✅ All spiders deployed and verified successfully"
                    return 0
                else
                    log_warn "⚠️ Spider verification failed"
                fi
            else
                log_warn "⚠️ Spider deployment command failed"
            fi
        fi

        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $MAX_RETRIES ]; then
            log_warn "⚠️  Deployment attempt $retry_count failed. Retrying in $RETRY_DELAY seconds..."
            sleep $RETRY_DELAY
        fi
    done

    log_error "❌ Failed to deploy spiders after $MAX_RETRIES attempts"
    return 1
}

# Main execution
log "Starting spider deployment process..."

# Wait for Scrapyd to be ready
log "Waiting for Scrapyd to be ready..."
./wait-for-it.sh localhost:6800 -t 60 || {
    log "❌ Timeout waiting for Scrapyd"
    exit 1
}

# Deploy spiders
if deploy_spiders; then
    log "✅ Deployment process completed successfully"
    exit 0
else
    log "❌ Deployment process failed"
    exit 1
fi
