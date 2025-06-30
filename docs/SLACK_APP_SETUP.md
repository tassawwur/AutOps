# Slack App Setup Guide for AutOps

This guide will walk you through creating and configuring a Slack app for AutOps in under 10 minutes.

## Prerequisites

- Admin access to a Slack workspace
- AutOps `.env` file ready to receive tokens

## Step 1: Create a New Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"**
3. Choose **"From scratch"**
4. Enter:
   - **App Name**: `AutOps`
   - **Pick a workspace**: Select your workspace
5. Click **"Create App"**

## Step 2: Configure Basic Information

1. In the **Basic Information** page, scroll to **"App Credentials"**
2. Copy these values to your `.env` file:
   ```
   SLACK_APP_ID=<App ID>
   SLACK_CLIENT_ID=<Client ID>
   SLACK_CLIENT_SECRET=<Client Secret>
   SLACK_SIGNING_SECRET=<Signing Secret>
   ```

## Step 3: Configure OAuth & Permissions

1. Go to **"OAuth & Permissions"** in the left sidebar
2. Scroll to **"Scopes"** section
3. Add the following **Bot Token Scopes**:

### Copy-Paste Bot Token Scopes
```
app_mentions:read
channels:history
channels:join
channels:read
chat:write
chat:write.customize
chat:write.public
commands
files:read
files:write
groups:history
groups:read
im:history
im:read
im:write
mpim:history
mpim:read
mpim:write
reactions:read
reactions:write
team:read
users:read
users:read.email
```

4. Scroll up and click **"Install to Workspace"**
5. Review permissions and click **"Allow"**
6. Copy the **Bot User OAuth Token** that starts with `xoxb-`
7. Add to your `.env` file:
   ```
   SLACK_BOT_TOKEN=xoxb-...
   ```

## Step 4: Configure Event Subscriptions

1. Go to **"Event Subscriptions"** in the left sidebar
2. Toggle **"Enable Events"** to ON
3. For **Request URL**, you'll need your ngrok URL:
   - If running locally: `https://<your-ngrok-subdomain>.ngrok.io/api/slack/events`
   - If deployed: `https://your-domain.com/api/slack/events`
4. Wait for **"Verified"** ✓ to appear

### Subscribe to Bot Events
Add these events under **"Subscribe to bot events"**:

```
app_mention
message.channels
message.groups
message.im
message.mpim
```

5. Click **"Save Changes"**

## Step 5: Configure Interactivity & Shortcuts

1. Go to **"Interactivity & Shortcuts"** in the left sidebar
2. Toggle **"Interactivity"** to ON
3. For **Request URL**, enter:
   - If running locally: `https://<your-ngrok-subdomain>.ngrok.io/api/slack/interactive`
   - If deployed: `https://your-domain.com/api/slack/interactive`
4. Click **"Save Changes"**

## Step 6: Configure Slash Commands (Optional)

1. Go to **"Slash Commands"** in the left sidebar
2. Click **"Create New Command"**
3. Enter:
   - **Command**: `/autops`
   - **Request URL**: `https://<your-ngrok-subdomain>.ngrok.io/api/slack/slash`
   - **Short Description**: `Interact with AutOps AI assistant`
   - **Usage Hint**: `[your question or command]`
4. Click **"Save"**

## Step 7: Configure App Home

1. Go to **"App Home"** in the left sidebar
2. Under **"Show Tabs"**, enable:
   - ✓ Home Tab
   - ✓ Messages Tab
3. Check **"Allow users to send Slash commands and messages from the messages tab"**

## Step 8: Update App Display Information

1. Go to **"Basic Information"**
2. Scroll to **"Display Information"**
3. Add:
   - **Description**: "AutOps is an AI-powered DevOps assistant that helps with incident response, monitoring, and automation"
   - **Background color**: `#2C3E50`
4. Upload an app icon (optional)
5. Click **"Save Changes"**

## Quick Setup JSON

For faster setup, you can use the Slack App Manifest. Go to **"App Manifest"** in the left sidebar and paste:

```json
{
  "display_information": {
    "name": "AutOps",
    "description": "AI-powered DevOps assistant for incident response and automation",
    "background_color": "#2C3E50"
  },
  "features": {
    "app_home": {
      "home_tab_enabled": true,
      "messages_tab_enabled": true,
      "messages_tab_read_only_enabled": false
    },
    "bot_user": {
      "display_name": "AutOps",
      "always_online": true
    },
    "slash_commands": [
      {
        "command": "/autops",
        "description": "Interact with AutOps AI assistant",
        "usage_hint": "[your question or command]",
        "should_escape": false
      }
    ]
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "channels:history",
        "channels:join",
        "channels:read",
        "chat:write",
        "chat:write.customize",
        "chat:write.public",
        "commands",
        "files:read",
        "files:write",
        "groups:history",
        "groups:read",
        "im:history",
        "im:read",
        "im:write",
        "mpim:history",
        "mpim:read",
        "mpim:write",
        "reactions:read",
        "reactions:write",
        "team:read",
        "users:read",
        "users:read.email"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim"
      ]
    },
    "interactivity": {
      "is_enabled": true
    },
    "org_deploy_enabled": false,
    "socket_mode_enabled": false,
    "token_rotation_enabled": false
  }
}
```

## Testing Your Setup

1. Invite the bot to a channel:
   ```
   /invite @AutOps
   ```

2. Test with a mention:
   ```
   @AutOps hello
   ```

3. Test with a direct message:
   - Go to the Apps section in Slack
   - Find AutOps
   - Send a direct message

4. Test slash command (if configured):
   ```
   /autops What's the status of our services?
   ```

## Troubleshooting

### Bot doesn't respond
- Check your ngrok URL is still active
- Verify all tokens in `.env` are correct
- Check Docker logs: `docker-compose logs -f autops`

### "Verification failed" for URLs
- Ensure your app is running (`./scripts/dev.sh`)
- Check that ngrok is forwarding to port 8000
- Verify `SLACK_SIGNING_SECRET` is correct in `.env`

### Permission errors
- Reinstall the app to your workspace
- Ensure all required scopes are added
- Check that bot is invited to the channel

## Local Development URLs

When running locally with `./scripts/dev.sh`, update these URLs in your Slack app:

1. **Event Subscriptions Request URL**:
   ```
   https://<ngrok-subdomain>.ngrok.io/api/slack/events
   ```

2. **Interactivity Request URL**:
   ```
   https://<ngrok-subdomain>.ngrok.io/api/slack/interactive
   ```

3. **Slash Commands Request URL**:
   ```
   https://<ngrok-subdomain>.ngrok.io/api/slack/slash
   ```

The ngrok subdomain changes each time you restart, so you'll need to update these URLs accordingly.

## Production Deployment

For production, replace ngrok URLs with your actual domain:
- `https://your-domain.com/api/slack/events`
- `https://your-domain.com/api/slack/interactive`
- `https://your-domain.com/api/slack/slash`

## Next Steps

1. Run `./scripts/dev.sh` to start your local environment
2. Update Slack app URLs with your ngrok URL
3. Test the bot in your Slack workspace
4. Check logs for any issues: `docker-compose logs -f autops`

## Security Best Practices

1. **Never commit tokens**: Keep `.env` in `.gitignore`
2. **Rotate tokens regularly**: Regenerate tokens periodically
3. **Use environment-specific apps**: Separate apps for dev/staging/prod
4. **Verify requests**: AutOps validates signatures automatically
5. **Limit scopes**: Only request permissions you need

## Quick Reference

| Token | Where to Find | Environment Variable |
|-------|--------------|---------------------|
| Bot Token | OAuth & Permissions → Bot User OAuth Token | `SLACK_BOT_TOKEN` |
| Signing Secret | Basic Information → App Credentials | `SLACK_SIGNING_SECRET` |
| App ID | Basic Information → App Credentials | `SLACK_APP_ID` |
| Client ID | Basic Information → App Credentials | `SLACK_CLIENT_ID` |
| Client Secret | Basic Information → App Credentials | `SLACK_CLIENT_SECRET` |

---

**Time to Complete**: ~10 minutes

**Support**: If you encounter issues, check the logs with `docker-compose logs -f autops` or create an issue in the repository. 