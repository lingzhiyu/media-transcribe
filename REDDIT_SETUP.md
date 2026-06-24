# Reddit Support with PRAW

The transcriber can use PRAW (Python Reddit API Wrapper) for more reliable Reddit post extraction. This is optional but recommended for Reddit links.

## Why PRAW?

- ✅ Official Reddit API wrapper
- ✅ More reliable than public JSON endpoint (which Reddit may throttle)
- ✅ Better error handling
- ✅ Support for private/restricted posts (with authentication)

## Setup

### 1. Install PRAW

```bash
pip install praw
```

### 2. Create a Reddit App

Go to https://www.reddit.com/prefs/apps and create a new application:

1. Click "Create an app" at the bottom
2. Fill in the form:
   - **name**: "media-transcribe" (or any name)
   - **app type**: Select "script"
   - **redirect uri**: `http://localhost:8080` (required but unused)
3. Click "create app"
4. You'll see your credentials:
   - **Client ID**: The string under your app name (top-left of the box)
   - **Client Secret**: The string next to "secret"

### 3. Set Environment Variables

Add these to your shell profile (`~/.zshrc`, `~/.bash_profile`, etc.):

```bash
export REDDIT_CLIENT_ID="your_client_id_here"
export REDDIT_CLIENT_SECRET="your_client_secret_here"
export REDDIT_USER_AGENT="media-transcribe/1.0 by your_reddit_username"
```

Then reload your shell:
```bash
source ~/.zshrc  # or ~/.bash_profile
```

### 4. Verify

Test with:
```bash
python3 /Users/zhiyuling/lingzhiyu/media-gobbler/transcribe.py "https://www.reddit.com/r/Python/comments/abcdef/example/"
```

If PRAW is installed and credentials are set, it will use PRAW. Otherwise, it falls back to the public JSON API.

## Fallback Behavior

If PRAW is not installed or credentials are missing, the script automatically falls back to the public JSON API endpoint. This works for most public posts but may be rate-limited by Reddit.

## Troubleshooting

**"ModuleNotFoundError: No module named 'praw'"**
- Run: `pip install praw`

**"PRAW error: Invalid authentication"**
- Check that your Client ID and Client Secret are correct
- Make sure your Reddit username matches the User-Agent

**"Failed to fetch Reddit post"**
- Falling back to JSON API (PRAW not configured)
- The script will still work but may be slower or rate-limited
