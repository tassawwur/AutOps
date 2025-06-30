#!/bin/bash
# Script to set up AutOps secrets for Kubernetes deployment
# This script helps create Kubernetes secrets from environment variables

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default namespace
NAMESPACE=${NAMESPACE:-autops}

echo -e "${GREEN}Setting up AutOps secrets in namespace: $NAMESPACE${NC}"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl could not be found. Please install kubectl first.${NC}"
    exit 1
fi

# Create namespace if it doesn't exist
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    echo -e "${YELLOW}Creating namespace $NAMESPACE...${NC}"
    kubectl create namespace $NAMESPACE
fi

# Function to create secret from environment variables
create_secret() {
    local secret_name=$1
    shift
    local args=()
    
    for var in "$@"; do
        if [ -z "${!var:-}" ]; then
            echo -e "${YELLOW}Warning: $var is not set${NC}"
        else
            args+=("--from-literal=$var=${!var}")
        fi
    done
    
    if [ ${#args[@]} -gt 0 ]; then
        echo -e "${GREEN}Creating secret $secret_name...${NC}"
        kubectl create secret generic $secret_name \
            --namespace=$NAMESPACE \
            "${args[@]}" \
            --dry-run=client -o yaml | kubectl apply -f -
    else
        echo -e "${RED}No variables set for secret $secret_name${NC}"
    fi
}

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo -e "${GREEN}Loading environment variables from .env file...${NC}"
    export $(cat .env | grep -v '^#' | xargs)
elif [ -f config/production.env ]; then
    echo -e "${GREEN}Loading environment variables from config/production.env...${NC}"
    export $(cat config/production.env | grep -v '^#' | xargs)
else
    echo -e "${YELLOW}No .env or config/production.env file found. Using existing environment variables.${NC}"
fi

# Create AutOps main secrets
create_secret "autops-secrets" \
    "OPENAI_API_KEY" \
    "SLACK_BOT_TOKEN" \
    "SLACK_SIGNING_SECRET" \
    "SLACK_CLIENT_SECRET" \
    "GITHUB_TOKEN" \
    "GITLAB_TOKEN" \
    "PAGERDUTY_API_KEY" \
    "SECRET_KEY"

# Create Datadog secret
create_secret "datadog-secret" \
    "DATADOG_API_KEY" \
    "DATADOG_APP_KEY"

# Create Docker registry secret
if [ -n "${DOCKER_USERNAME:-}" ] && [ -n "${DOCKER_TOKEN:-}" ]; then
    echo -e "${GREEN}Creating Docker registry secret...${NC}"
    kubectl create secret docker-registry docker-registry-secret \
        --namespace=$NAMESPACE \
        --docker-server=https://index.docker.io/v1/ \
        --docker-username=$DOCKER_USERNAME \
        --docker-password=$DOCKER_TOKEN \
        --dry-run=client -o yaml | kubectl apply -f -
else
    echo -e "${YELLOW}Docker credentials not set, skipping Docker registry secret${NC}"
fi

# Verify secrets were created
echo -e "\n${GREEN}Verifying secrets:${NC}"
kubectl get secrets -n $NAMESPACE

echo -e "\n${GREEN}Secret setup complete!${NC}"
echo -e "${YELLOW}Note: Make sure to update any placeholder values with actual credentials.${NC}"

# Optional: Install Datadog Operator if requested
if [ "${INSTALL_DATADOG_OPERATOR:-false}" = "true" ]; then
    echo -e "\n${GREEN}Installing Datadog Operator...${NC}"
    helm repo add datadog https://helm.datadoghq.com
    helm repo update
    helm install datadog-operator datadog/datadog-operator --namespace $NAMESPACE
    
    echo -e "${GREEN}Applying Datadog Agent configuration...${NC}"
    kubectl apply -f k8s/datadog-agent.yaml
fi 