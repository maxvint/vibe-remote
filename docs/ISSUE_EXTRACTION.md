# Issue Extraction Feature

The `/req` command allows you to extract requirements from Slack channel discussions and automatically create GitHub issues.

> **Alias:** `/issue` also works but may conflict with GitHub's built-in command.

## Overview

This feature:
1. Collects recent messages from the current Slack channel
2. Uses Claude AI to analyze the discussion and extract requirements
3. Shows a preview for your review
4. Creates a GitHub issue after your confirmation
5. Optionally mentions a solver agent to handle the issue

## Prerequisites

### 1. GitHub App Configuration

You need a GitHub App configured with the following permissions:
- **Repository permissions:**
  - Issues: Read & Write
  - Contents: Read (optional, for repo info)

Ensure your `config.json` has GitHub configuration:

```json
{
  "github": {
    "app_id": "YOUR_APP_ID",
    "private_key_path": "path/to/private-key.pem",
    "default_installation_id": "YOUR_INSTALLATION_ID",
    "trigger_keyword": "@Codeholic",
    "repo_mappings": {
      "owner/repo": {
        "installation_id": "INSTALLATION_ID",
        "local_path": "~/projects/repo"
      }
    }
  }
}
```

### 2. Anthropic API Key

The feature uses Claude API for requirement extraction. Set your API key:

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### 3. Slack Bot Permissions

Your Slack bot needs these additional scopes:
- `channels:history` - Read channel messages
- `groups:history` - Read private channel messages (if needed)
- `users:read` - Get user display names

## Usage

### Basic Usage

In any Slack channel, type:

```
@Vibe Remote /req
```

This will:
1. Collect messages from the last 24 hours
2. Analyze and extract requirements
3. Show a preview with buttons

### In a Thread

When used inside a thread, `/req` automatically collects **only the thread messages** (no time range needed):

```
@Vibe Remote /req
```

This is useful for focused discussions where a thread contains all the relevant context.

### With Options

```
@Vibe Remote /req --hours 48 --repo owner/repo
```

Options:
- `--hours N` - Look back N hours (default: 24)
- `--repo owner/repo` - Target repository (default: from config)

### Preview and Confirmation

After analysis, you'll see a preview:

```
📋 Issue Preview

Repository: owner/repo
Title: Implement user authentication timeout handling
Labels: enhancement, backend

Description:
Based on the discussion, users are experiencing timeout issues...

[✅ Create Issue] [✏️ Edit] [❌ Cancel]
```

- **Create Issue**: Creates the issue on GitHub
- **Edit**: Opens a modal to modify title, description, labels, and repo
- **Cancel**: Discards the draft

## Configuration

### Optional: Issue Extraction Settings

Add to your `config.json`:

```json
{
  "issue_extraction": {
    "default_repo": "owner/repo",
    "solver_mention": "@Codeholic",
    "default_labels": ["from-slack"]
  }
}
```

- `default_repo`: Default repository for issues
- `solver_mention`: GitHub username/bot to mention for solving issues
- `default_labels`: Labels to add to all extracted issues

### Solver Agent Integration

When an issue is created, the configured `solver_mention` (or `trigger_keyword` from GitHub config) is added to the issue body:

```markdown
## Description
[Extracted requirements...]

---
📍 *Extracted from Slack discussion*

@Codeholic Please review and address this issue.
```

If you have the GitHub integration set up, this mention can trigger another agent to automatically work on the issue.

## Workflow Example

1. **Team discusses a bug in Slack:**
   ```
   Alice: The login page is slow after the last deployment
   Bob: I noticed it takes 5+ seconds to load
   Alice: We should investigate the API response times
   ```

2. **Someone runs `@Vibe Remote /req`**

3. **AI extracts:**
   ```
   Title: Investigate slow login page after recent deployment

   Description:
   ## Problem
   Users report slow login page performance after recent deployment.

   ## Observations
   - Page load time exceeds 5 seconds
   - Likely related to API response times

   ## Suggested Actions
   - Profile API endpoints
   - Check for N+1 queries
   - Review recent deployment changes
   ```

4. **After confirmation, issue is created on GitHub**

5. **Solver agent (if configured) picks up the issue**

## Troubleshooting

### "No repository configured"

Ensure you have either:
- `--repo` flag in the command
- `issue_extraction.default_repo` in config
- At least one repo in `github.repo_mappings`

### "GitHub integration is not configured"

Check your `config.json` has valid GitHub App credentials:
- `app_id`
- `private_key_path` (file must exist and be readable)
- `default_installation_id` or repo-specific installation IDs

### "No GitHub installation found for repository"

The GitHub App must be installed on the target repository. Check:
1. App is installed on the repo's organization/user
2. Installation ID is correct in config

### "Failed to extract requirements"

- Check `ANTHROPIC_API_KEY` is set
- Ensure the channel has recent messages
- Try increasing `--hours` if discussion happened earlier

## Security Notes

- Message content is sent to Claude API for analysis
- Only messages from the specified time range are collected
- Bot messages and system messages are filtered out
- Issue drafts expire after 1 hour
