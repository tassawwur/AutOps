# AutOps Credentials Setup

## Required API Keys

1. **OpenAI API Key** - Required for AI agents
   - Get from: https://platform.openai.com/api-keys

2. **GitHub Token** - Required for repository access
   - Create Personal Access Token with `repo` scope
   - Set `GITHUB_OWNER` to your username

3. **Slack Bot Token** - Required for Slack integration
   - Follow `docs/SLACK_APP_SETUP.md` for complete setup

## Optional Integrations

- **DataDog**: API Key + App Key for metrics
- **PagerDuty**: API Key for incident management  
- **GitLab**: Token for GitLab repositories

## Quick Setup

1. **Copy environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Update `.env` with your keys:**
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   GITHUB_TOKEN=github_pat_your_token_here
   GITHUB_OWNER=your_github_username
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_SIGNING_SECRET=your_signing_secret
   ```

3. **Start the application:**
   ```bash
   ./scripts/dev.sh
   ```

## Testing Setup

```bash
# Verify configuration
python -c "from src.autops.config import get_settings; print('✅ Config loaded')"

# Test Slack (if configured)
curl -X POST http://localhost:8000/api/slack/events -d '{"challenge":"test"}'
```

## Production Deployment

For Kubernetes deployment, use the setup script:
```bash
./scripts/setup-secrets.sh
kubectl apply -f k8s/
```

## Troubleshooting

- **Missing OpenAI key**: AI agents won't work
- **Invalid GitHub token**: Repository operations will fail  
- **Slack issues**: Check bot permissions and signing secret
- **Environment variables**: Restart application after changes 