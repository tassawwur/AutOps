# AutOps Production Deployment Guide

This guide covers deploying AutOps to production environments with enterprise-grade security, monitoring, and reliability.

## 🚀 Quick Start

For immediate deployment using our automated scripts:

```bash
# Clone the repository
git clone https://github.com/yourorg/autops.git
cd autops

# Run the deployment script
./scripts/deploy.sh production
```

## 📋 Prerequisites

### Infrastructure Requirements

- **Kubernetes cluster** (v1.21+)
- **Container registry** (Docker Hub, ECR, GCR, etc.)
- **Database**: PostgreSQL 13+ or MySQL 8+
- **Cache**: Redis 6+
- **Monitoring**: Prometheus + Grafana stack
- **Load Balancer**: NGINX, ALB, or cloud provider LB

### Minimum Resource Requirements

- **CPU**: 4 cores (8 recommended)
- **Memory**: 8GB (16GB recommended)
- **Storage**: 100GB SSD
- **Network**: 1Gbps bandwidth

### External Services

- **Slack Workspace** with bot permissions
- **GitHub** organization access
- **Datadog** account (optional but recommended)
- **PagerDuty** account (for incident management)
- **OpenAI API** access

## 🔧 Environment Setup

### 1. Configure Secrets

Create a `.env.production` file based on the template:

```bash
cp config/production.env .env.production
```

Set the following required environment variables:

```bash
# Application secrets
SECRET_KEY="your-secret-key-here"
JWT_SECRET="your-jwt-secret-here"
ENCRYPTION_KEY="your-encryption-key-here"

# Database
DATABASE_URL="postgresql://user:password@host:5432/autops"

# Redis
REDIS_URL="redis://user:password@host:6379/0"

# OpenAI
OPENAI_API_KEY="sk-your-openai-api-key"

# Slack
SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
SLACK_SIGNING_SECRET="your-slack-signing-secret"

# GitHub
GITHUB_TOKEN="ghp_your-github-token"
GITHUB_WEBHOOK_SECRET="your-webhook-secret"

# Datadog
DATADOG_API_KEY="your-datadog-api-key"
DATADOG_APP_KEY="your-datadog-app-key"

# PagerDuty
PAGERDUTY_API_KEY="your-pagerduty-api-key"
```

### 2. Generate Secrets

Use our utility script to generate secure secrets:

```bash
python scripts/generate_secrets.py
```

## 🐳 Container Deployment

### Option 1: Docker Compose (Single Host)

For smaller deployments or testing:

```bash
# Build and start services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f autops
```

### Option 2: Kubernetes (Recommended)

#### Step 1: Create Namespace

```bash
kubectl create namespace autops
```

#### Step 2: Create Secrets

```bash
# Create secret from .env file
kubectl create secret generic autops-secrets \
  --from-env-file=.env.production \
  --namespace=autops
```

#### Step 3: Apply Security Policy

```bash
kubectl apply -f security/policy.yaml -n autops
```

#### Step 4: Deploy Application

```bash
# Deploy all Kubernetes resources
kubectl apply -f k8s/ -n autops

# Check deployment status
kubectl get pods -n autops
kubectl get services -n autops
```

#### Step 5: Verify Deployment

```bash
# Check pod status
kubectl describe pods -l app=autops -n autops

# Check logs
kubectl logs -f deployment/autops -n autops

# Test health endpoint
kubectl port-forward service/autops 8000:8000 -n autops
curl http://localhost:8000/health
```

## 🏗️ Infrastructure as Code

### Terraform Configuration

For cloud deployment, use our Terraform modules:

```hcl
module "autops" {
  source = "./terraform/modules/autops"
  
  environment     = "production"
  vpc_id         = var.vpc_id
  subnet_ids     = var.private_subnet_ids
  
  # Database
  db_instance_class = "db.r5.xlarge"
  db_allocated_storage = 100
  
  # Cache
  redis_node_type = "cache.r5.large"
  
  # Compute
  min_capacity = 2
  max_capacity = 10
  desired_capacity = 4
  
  tags = {
    Environment = "production"
    Application = "autops"
  }
}
```

## 📊 Monitoring Setup

### Prometheus Configuration

1. Deploy Prometheus operator:

```bash
kubectl apply -f monitoring/prometheus/
```

2. Configure service monitors:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: autops-metrics
spec:
  selector:
    matchLabels:
      app: autops
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
```

### Grafana Dashboards

Import our pre-built dashboards:

```bash
# Copy dashboard configs
kubectl create configmap autops-dashboards \
  --from-file=monitoring/grafana/dashboards/ \
  -n monitoring

# Apply Grafana configuration
kubectl apply -f monitoring/grafana/
```

### Alerting Rules

Configure Prometheus alerting:

```yaml
groups:
- name: autops.rules
  rules:
  - alert: AutOpsHighErrorRate
    expr: rate(autops_requests_total{status="error"}[5m]) > 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate in AutOps"
      
  - alert: AutOpsHighLatency
    expr: autops_request_duration_seconds{quantile="0.95"} > 3
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High latency in AutOps requests"
```

## 🔒 Security Configuration

### SSL/TLS Setup

1. **Certificate Management**:

```bash
# Install cert-manager
kubectl apply -f https://github.com/jetstack/cert-manager/releases/download/v1.12.0/cert-manager.yaml

# Create ClusterIssuer
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@yourcompany.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

### Network Security

1. **Network Policies**:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: autops-network-policy
spec:
  podSelector:
    matchLabels:
      app: autops
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: autops
    ports:
    - protocol: TCP
      port: 8000
```

### RBAC Configuration

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: autops-role
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps", "secrets"]
  verbs: ["get", "list", "watch"]
```

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow

The CI/CD pipeline automatically:

1. **Runs tests** on pull requests
2. **Builds container images** on main branch
3. **Scans for vulnerabilities**
4. **Deploys to staging** automatically
5. **Requires approval** for production

### Manual Deployment

For manual deployments:

```bash
# Build and push image
docker build -t yourregistry/autops:v1.0.0 .
docker push yourregistry/autops:v1.0.0

# Update Kubernetes deployment
kubectl set image deployment/autops autops=yourregistry/autops:v1.0.0 -n autops

# Monitor rollout
kubectl rollout status deployment/autops -n autops
```

## 🧪 Testing Production Deployment

### Health Checks

```bash
# Basic health check
curl https://autops.yourcompany.com/health

# Readiness check
curl https://autops.yourcompany.com/ready

# Metrics endpoint
curl https://autops.yourcompany.com/metrics
```

### Load Testing

Run performance tests against production:

```bash
# Install Locust
pip install locust

# Run load test
locust -f benchmarks/locustfile.py \
  --host https://autops.yourcompany.com \
  --users 50 \
  --spawn-rate 10 \
  --run-time 5m
```

### End-to-End Testing

```bash
# Run E2E tests
pytest tests/e2e/ --env production
```

## 📈 Performance Tuning

### Application Tuning

1. **Worker Configuration**:
   - Set `WORKER_PROCESSES` based on CPU cores
   - Configure `WORKER_CONNECTIONS` for concurrent requests
   - Tune `KEEPALIVE_TIMEOUT` for connection reuse

2. **Database Optimization**:
   - Configure connection pooling
   - Set appropriate timeout values
   - Enable query optimization

3. **Cache Configuration**:
   - Set Redis memory limits
   - Configure cache expiration policies
   - Monitor cache hit rates

### Kubernetes Resource Management

```yaml
resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2000m
    memory: 4Gi
```

### Horizontal Pod Autoscaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: autops-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: autops
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## 🔍 Troubleshooting

### Common Issues

1. **Pod Startup Failures**:
   ```bash
   kubectl describe pod <pod-name> -n autops
   kubectl logs <pod-name> -n autops
   ```

2. **Database Connection Issues**:
   ```bash
   # Test database connectivity
   kubectl exec -it deployment/autops -n autops -- python -c "
   from autops.config import settings
   import psycopg2
   conn = psycopg2.connect(settings.database_url)
   print('Database connection successful')
   "
   ```

3. **External API Issues**:
   ```bash
   # Test API connectivity
   kubectl exec -it deployment/autops -n autops -- curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" https://slack.com/api/auth.test
   ```

### Debug Mode

Enable debug logging in production (temporarily):

```bash
kubectl set env deployment/autops LOG_LEVEL=DEBUG -n autops
```

## 🛡️ Backup and Recovery

### Database Backups

Automated daily backups:

```bash
# Create backup job
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: autops-db-backup
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:13
            command:
            - /bin/bash
            - -c
            - pg_dump $DATABASE_URL > /backup/autops-$(date +%Y%m%d).sql
            env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: autops-secrets
                  key: DATABASE_URL
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure
EOF
```

### Disaster Recovery

1. **Restore from backup**:
   ```bash
   kubectl exec -it deployment/autops -n autops -- psql $DATABASE_URL < backup.sql
   ```

2. **Scale down during maintenance**:
   ```bash
   kubectl scale deployment autops --replicas=0 -n autops
   ```

3. **Scale back up**:
   ```bash
   kubectl scale deployment autops --replicas=4 -n autops
   ```

## 📞 Support

For deployment issues:

1. **Check our troubleshooting guide**
2. **Review logs and metrics**
3. **Contact the team** via Slack: #autops-support
4. **Create an issue** in GitHub repository

## 🔄 Updates and Maintenance

### Rolling Updates

```bash
# Update to new version
kubectl set image deployment/autops autops=yourregistry/autops:v1.1.0 -n autops

# Monitor rollout
kubectl rollout status deployment/autops -n autops

# Rollback if needed
kubectl rollout undo deployment/autops -n autops
```

### Maintenance Windows

Schedule maintenance during low-traffic periods:

1. **Notify users** via Slack
2. **Scale down non-critical services**
3. **Perform updates**
4. **Run health checks**
5. **Scale services back up**

---

## 📚 Additional Resources

- [Configuration Reference](./CONFIGURATION.md)
- [API Documentation](./API.md)
- [Troubleshooting Guide](./TROUBLESHOOTING.md)
- [Security Best Practices](./SECURITY.md) 