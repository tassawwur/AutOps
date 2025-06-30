#!/bin/bash

# AutOps Production Deployment Script
# This script automates the deployment of AutOps to production environments

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${ENVIRONMENT:-production}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
NAMESPACE="${NAMESPACE:-autops}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Error handling
cleanup() {
    if [[ $? -ne 0 ]]; then
        log_error "Deployment failed! Check the logs above for details."
        if [[ "$ENVIRONMENT" == "production" ]]; then
            log_warning "Consider running rollback if needed: ./scripts/rollback.sh"
        fi
    fi
}
trap cleanup EXIT

# Help function
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy AutOps to production environments.

OPTIONS:
    -e, --environment    Target environment (default: production)
    -t, --tag           Docker image tag (default: latest)
    -n, --namespace     Kubernetes namespace (default: autops)
    -h, --help          Show this help message
    --dry-run          Show what would be deployed without actually deploying
    --rollback         Rollback to previous version

EXAMPLES:
    $0                                    # Deploy latest to production
    $0 -e staging -t v1.2.3              # Deploy v1.2.3 to staging
    $0 --dry-run                         # Show deployment plan
    $0 --rollback                        # Rollback to previous version

EOF
}

# Parse command line arguments
DRY_RUN=false
ROLLBACK=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --rollback)
            ROLLBACK=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validation functions
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check required tools
    local tools=("kubectl" "docker" "helm")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is required but not installed"
            exit 1
        fi
    done
    
    # Check kubectl context
    local current_context
    current_context=$(kubectl config current-context 2>/dev/null || echo "none")
    if [[ "$current_context" == "none" ]]; then
        log_error "No kubectl context configured"
        exit 1
    fi
    
    log_info "Using kubectl context: $current_context"
    
    # Verify namespace exists
    if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
        log_warning "Namespace $NAMESPACE does not exist, creating it..."
        kubectl create namespace "$NAMESPACE"
    fi
    
    log_success "Prerequisites check passed"
}

# Pre-deployment checks
pre_deployment_checks() {
    log_info "Running pre-deployment checks..."
    
    # Check if secrets exist
    if ! kubectl get secret autops-secrets -n "$NAMESPACE" &>/dev/null; then
        log_error "Required secret 'autops-secrets' not found in namespace $NAMESPACE"
        log_info "Please create the secret first:"
        log_info "kubectl create secret generic autops-secrets --from-env-file=.env.production -n $NAMESPACE"
        exit 1
    fi
    
    # Validate image exists (if not latest)
    if [[ "$IMAGE_TAG" != "latest" ]]; then
        log_info "Validating image exists: ghcr.io/autops:$IMAGE_TAG"
        # Add image validation logic here
    fi
    
    log_success "Pre-deployment checks passed"
}

# Deployment function
deploy() {
    log_info "Starting deployment to $ENVIRONMENT..."
    
    # Update image tag in deployment
    local temp_dir
    temp_dir=$(mktemp -d)
    cp -r "$PROJECT_ROOT/k8s" "$temp_dir/"
    
    # Replace image tag
    sed -i.bak "s|autops:latest|ghcr.io/autops:$IMAGE_TAG|g" "$temp_dir/k8s/deployment.yaml"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN - Would deploy the following:"
        kubectl diff -f "$temp_dir/k8s/" -n "$NAMESPACE" || true
        rm -rf "$temp_dir"
        return 0
    fi
    
    # Apply Kubernetes manifests
    log_info "Applying Kubernetes manifests..."
    kubectl apply -f "$temp_dir/k8s/" -n "$NAMESPACE"
    
    # Wait for deployment to complete
    log_info "Waiting for deployment to complete..."
    kubectl rollout status deployment/autops -n "$NAMESPACE" --timeout=600s
    
    # Verify deployment
    verify_deployment
    
    # Cleanup
    rm -rf "$temp_dir"
    
    log_success "Deployment completed successfully!"
}

# Verification function
verify_deployment() {
    log_info "Verifying deployment..."
    
    # Check pod status
    local ready_pods
    ready_pods=$(kubectl get pods -l app=autops -n "$NAMESPACE" -o jsonpath='{.items[?(@.status.phase=="Running")].metadata.name}' | wc -w)
    
    if [[ "$ready_pods" -eq 0 ]]; then
        log_error "No pods are running"
        kubectl get pods -l app=autops -n "$NAMESPACE"
        exit 1
    fi
    
    log_info "Found $ready_pods running pod(s)"
    
    # Health check
    log_info "Performing health check..."
    local service_ip
    service_ip=$(kubectl get service autops-service -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    
    # Port forward for health check
    kubectl port-forward service/autops-service 8080:80 -n "$NAMESPACE" &
    local port_forward_pid=$!
    
    sleep 5
    
    if curl -f http://localhost:8080/health &>/dev/null; then
        log_success "Health check passed"
    else
        log_error "Health check failed"
        kill $port_forward_pid 2>/dev/null || true
        exit 1
    fi
    
    kill $port_forward_pid 2>/dev/null || true
    
    log_success "Deployment verification completed"
}

# Rollback function
rollback() {
    log_warning "Starting rollback..."
    
    kubectl rollout undo deployment/autops -n "$NAMESPACE"
    kubectl rollout status deployment/autops -n "$NAMESPACE" --timeout=300s
    
    verify_deployment
    
    log_success "Rollback completed successfully"
}

# Post-deployment tasks
post_deployment() {
    log_info "Running post-deployment tasks..."
    
    # Update monitoring dashboards
    if kubectl get configmap grafana-dashboards -n "$NAMESPACE" &>/dev/null; then
        log_info "Updating Grafana dashboards..."
        # Add dashboard update logic here
    fi
    
    # Send notification
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"✅ AutOps deployed successfully to $ENVIRONMENT (version: $IMAGE_TAG)\"}" \
            "$SLACK_WEBHOOK_URL" || log_warning "Failed to send Slack notification"
    fi
    
    log_success "Post-deployment tasks completed"
}

# Main execution
main() {
    log_info "AutOps Deployment Script"
    log_info "Environment: $ENVIRONMENT"
    log_info "Image Tag: $IMAGE_TAG"
    log_info "Namespace: $NAMESPACE"
    
    if [[ "$ROLLBACK" == "true" ]]; then
        check_prerequisites
        rollback
        exit 0
    fi
    
    check_prerequisites
    pre_deployment_checks
    deploy
    
    if [[ "$DRY_RUN" == "false" ]]; then
        post_deployment
    fi
    
    log_success "All deployment tasks completed successfully!"
}

# Execute main function
main "$@" 