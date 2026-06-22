# AI PR Review

An automated code review system that uses AI to analyze GitHub pull requests and provide intelligent feedback. The system fetches PR code changes, analyzes them with Mistral LLM, and posts reviews as comments on the PR while sending high-severity alerts to Slack.

## Features

✨ **Automated Code Review** - Uses Mistral LLM to analyze code patches for errors and issues
📝 **GitHub Integration** - Automatically fetches PR files and posts review comments
🚨 **Slack Alerts** - Sends notifications for high-severity issues
📊 **Error Classification** - Categorizes issues by severity (low, medium, high)
🔄 **GitHub Actions Integration** - Runs automatically on PR events

## Architecture

This project uses **LangGraph** to implement a workflow with the following steps:

1. **PR Files Fetcher** - Retrieves all changed files from the GitHub PR
2. **Code Analyzer** - Analyzes code using Mistral LLM and identifies issues
3. **GitHub Commenter** - Posts review findings as a comment on the PR
4. **Slack Notifier** - Sends high-severity alerts to Slack webhook

## Prerequisites

- Python 3.8+
- [Ollama](https://ollama.ai/) with Mistral model installed
- GitHub token (for API access)
- Slack webhook URL (for notifications)

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd Github_code_review
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create an `.env` file with your credentials:
```bash
cp env.example .env
```

Then edit `.env` and add your GitHub token and Slack webhook URL:
```env
GITHUB_TOKEN=your_github_token_here
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_TOKEN` | GitHub Personal Access Token | Yes |
| `SLACK_WEBHOOK_URL` | Slack webhook URL for notifications | Yes |
| `PR_NUMBER` | PR number (set by GitHub Actions) | Set by workflow |
| `PR_TITLE` | PR title (set by GitHub Actions) | Set by workflow |

### Repository Settings

Update these in `main.py`:
```python
REPO_OWNER = "your-username"
REPO_NAME = "your-repo-name"
```

## GitHub Actions Setup

1. Create `.github/workflows/ai-review.yml`:
```yaml
name: AI PR Review

on:
  pull_request:
    types:
      - opened
      - synchronize

jobs:
  review:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Run AI Review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          PR_TITLE: ${{ github.event.pull_request.title }}
        run: python main.py
```

2. Add secrets to your repository:
   - Go to Settings → Secrets and variables → Actions
   - Add `GITHUB_TOKEN` (use default or create a new one)
   - Add `SLACK_WEBHOOK_URL` (from your Slack workspace)

## Local Development

Run the analysis locally:
```bash
# Set environment variables
export GITHUB_TOKEN="your_token"
export SLACK_WEBHOOK_URL="your_webhook_url"
export PR_NUMBER=42
export PR_TITLE="Your PR Title"

# Run the script
python main.py
```

## Testing

Run the test suite:
```bash
pytest test_main.py -v
```

Run specific test class:
```bash
pytest test_main.py::TestGitHubAPIs -v
```

Run with coverage:
```bash
pytest test_main.py --cov=main
```

## How It Works

### 1. Fetch PR Files
The system retrieves all files changed in the pull request from GitHub API.

### 2. Code Analysis
Mistral LLM analyzes the code patches and identifies:
- Syntax errors
- Logical errors
- Potential bugs
- Code quality issues

Each issue is classified with:
- Error line number
- Error message
- Suggested correction
- Severity level (low/medium/high)

### 3. Post Comment
Results are formatted and posted as a comment on the PR for developer review.

### 4. Slack Notification
High-severity issues trigger immediate Slack notifications to alert the team.

## Workflow Graph

```
START
  ↓
pr_files_fetcher (Fetch changed files)
  ↓
code_analyzer (Analyze with LLM)
  ↓
├→ post_comment (Post to GitHub)
├→ slack_notif (Alert Slack - high severity only)
  ↓
END
```

## API Endpoints Used

### GitHub API
- `GET /repos/{owner}/{repo}/pulls` - List pull requests
- `GET /repos/{owner}/{repo}/pulls/{number}/files` - Get PR files
- `POST /repos/{owner}/{repo}/issues/{number}/comments` - Post comment

### Slack API
- `POST {webhook_url}` - Send message to channel

## Models

### `error_response`
Represents a code issue found during analysis:
- `error_line` (int): Line number where error occurs
- `error_message` (str): Description of the error
- `error_correction` (str): Suggested fix
- `severity` (Literal["low", "medium", "high"]): Issue severity

### `ReviewResponse`
Contains analysis results:
- `errors` (list[error_response]): List of identified issues

## Error Handling

The system handles various error scenarios:
- Missing PR files
- GitHub API failures
- Slack webhook failures
- LLM analysis errors

All errors are logged and the workflow continues gracefully.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes and add tests
4. Run tests: `pytest test_main.py -v`
5. Commit: `git commit -am 'Add your feature'`
6. Push: `git push origin feature/your-feature`
7. Submit a pull request

## Requirements

See [requirements.txt](requirements.txt) for complete dependencies:
- `langchain` - LLM framework
- `langchain-core` - Core LLM utilities
- `langchain_ollama` - Ollama LLM integration
- `langgraph` - Workflow orchestration
- `pydantic` - Data validation
- `requests` - HTTP requests
- `python-dotenv` - Environment variables

## License

MIT License - see LICENSE file for details

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

## Roadmap

- [ ] Support for multiple LLM providers
- [ ] Configurable severity thresholds
- [ ] PR analytics dashboard
- [ ] Custom review rules
- [ ] Integration with more notification channels
- [ ] Performance metrics tracking

## Troubleshooting

### "Ollama connection failed"
Ensure Ollama is running and accessible. Start Ollama with:
```bash
ollama serve
```

### "GitHub API rate limit exceeded"
Use a GitHub token with sufficient permissions. Check your rate limit:
```bash
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit
```

### "Slack webhook failed"
Verify the webhook URL is correct and the Slack app has permissions to post messages.

### Tests failing
Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
pip install pytest pytest-mock
```