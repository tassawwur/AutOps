#!/bin/bash
# =====================================================
# AutOps Development Setup Script
# =====================================================
# This script sets up your local development environment
# and starts all necessary services
# =====================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "\n${GREEN}======================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}======================================${NC}\n"
}

print_error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

print_success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

# Check prerequisites
print_header "Checking Prerequisites"

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker Desktop first."
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found. Creating from .env.example..."
    
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success "Created .env file from .env.example"
        echo ""
        echo "IMPORTANT: Please edit .env file and add your API keys:"
        echo "  - OPENAI_API_KEY"
        echo "  - SLACK_BOT_TOKEN"
        echo "  - SLACK_SIGNING_SECRET"
        echo "  - GITHUB_TOKEN"
        echo "  - GITHUB_OWNER"
        echo ""
        echo "Press Enter after updating .env file..."
        read -r
    else
        print_error ".env.example not found. Cannot create .env file."
        exit 1
    fi
fi

# Validate required environment variables
print_header "Validating Environment Variables"

# Source .env file
export $(grep -v '^#' .env | xargs)

# Check required variables
REQUIRED_VARS=("OPENAI_API_KEY" "SLACK_BOT_TOKEN" "SLACK_SIGNING_SECRET" "GITHUB_TOKEN" "GITHUB_OWNER")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ] || [[ "${!var}" == *"..."* ]]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    print_error "Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Please update your .env file with valid values."
    exit 1
fi

print_success "All required environment variables are set"

# Start Docker services
print_header "Starting Docker Services"

# Pull latest images
echo "Pulling latest Docker images..."
docker-compose pull

# Build the application
echo "Building AutOps application..."
docker-compose build

# Start services
echo "Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 5

# Check if services are running
if docker-compose ps | grep -q "autops.*Up"; then
    print_success "AutOps service is running"
else
    print_error "AutOps service failed to start"
    echo "Checking logs..."
    docker-compose logs autops
    exit 1
fi

# Get container IP/Port
API_URL="http://localhost:8000"

# Check API health
print_header "Checking API Health"

MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s "${API_URL}/health" > /dev/null 2>&1; then
        print_success "API is healthy"
        break
    else
        echo "Waiting for API to be ready... ($((RETRY_COUNT + 1))/$MAX_RETRIES)"
        sleep 2
        RETRY_COUNT=$((RETRY_COUNT + 1))
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "API failed to become healthy"
    docker-compose logs autops
    exit 1
fi

# Setup ngrok tunnel
print_header "Setting up Ngrok Tunnel"

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    print_warning "Ngrok is not installed. Installing..."
    
    # Detect OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install ngrok/ngrok/ngrok
        else
            print_error "Please install Homebrew first or download ngrok from https://ngrok.com/download"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
        echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
        sudo apt update && sudo apt install ngrok
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        # Windows
        print_error "Please download ngrok from https://ngrok.com/download and add to PATH"
        print_warning "After installing ngrok, run this script again"
        exit 1
    fi
fi

# Kill any existing ngrok processes
pkill -f ngrok || true

# Start ngrok in background
echo "Starting ngrok tunnel..."
ngrok http 8000 --log=stdout > ngrok.log 2>&1 &
NGROK_PID=$!

# Wait for ngrok to start
sleep 3

# Get ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | grep -o 'https://[^"]*' | head -1)

if [ -z "$NGROK_URL" ]; then
    print_error "Failed to get ngrok URL"
    cat ngrok.log
    exit 1
fi

# Display setup information
print_header "Setup Complete!"

echo -e "${GREEN}Your AutOps development environment is ready!${NC}"
echo ""
echo "Local API URL: ${API_URL}"
echo "Public URL (for Slack): ${NGROK_URL}"
echo ""
echo "Next steps:"
echo "1. Update your Slack app configuration:"
echo "   - Go to https://api.slack.com/apps"
echo "   - Select your app"
echo "   - Update the following URLs:"
echo ""
echo "   Interactivity & Shortcuts:"
echo "   - Request URL: ${NGROK_URL}/api/slack/interactive"
echo ""
echo "   Event Subscriptions:"
echo "   - Request URL: ${NGROK_URL}/api/slack/events"
echo ""
echo "   Slash Commands (if configured):"
echo "   - Request URL: ${NGROK_URL}/api/slack/slash"
echo ""
echo "2. Save your Slack app configuration"
echo ""
echo "3. Reinstall your app to your workspace (if needed)"
echo ""
echo "4. Test your bot by mentioning it in a Slack channel!"
echo ""
echo "Useful commands:"
echo "  - View logs: docker-compose logs -f autops"
echo "  - Stop services: docker-compose down"
echo "  - Restart services: docker-compose restart"
echo "  - View ngrok dashboard: http://localhost:4040"
echo ""

# Save ngrok URL to file for other scripts
echo "$NGROK_URL" > .ngrok-url

# Keep script running to maintain ngrok tunnel
print_warning "Keep this terminal open to maintain the ngrok tunnel"
print_warning "Press Ctrl+C to stop all services"

# Trap Ctrl+C
trap cleanup INT

cleanup() {
    echo ""
    print_header "Shutting down services"
    
    # Kill ngrok
    kill $NGROK_PID 2>/dev/null || true
    
    # Stop Docker services
    docker-compose down
    
    # Clean up
    rm -f .ngrok-url ngrok.log
    
    print_success "All services stopped"
    exit 0
}

# Keep script running
while true; do
    sleep 1
done 