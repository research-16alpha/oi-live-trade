# Streamlit Cloud Deployment Guide

This guide will help you deploy your Option Chain Trading Portfolio Dashboard to Streamlit Cloud.

## Prerequisites

1. **GitHub Account**: You need a GitHub account
2. **Streamlit Cloud Account**: Sign up at [share.streamlit.io](https://share.streamlit.io) (it's free!)

## Step 1: Push Code to GitHub

### If you don't have a GitHub repository yet:

1. Create a new repository on GitHub:
   - Go to [github.com/new](https://github.com/new)
   - Name it something like `option-chain-trading` or `oi-monitor`
   - Make it **Public** (required for free Streamlit Cloud)
   - Don't initialize with README (we already have one)

2. Push your code:
```bash
cd /Users/16alpha/Desktop/Automate_OI

# Initialize git if not already done
git init

# Add all files (sensitive files are excluded by .gitignore)
git add .

# Commit
git commit -m "Initial commit: Option Chain Trading Monitor with Streamlit Dashboard"

# Add remote (replace YOUR_USERNAME and REPO_NAME)
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### If you already have a GitHub repository:

```bash
cd /Users/16alpha/Desktop/Automate_OI

# Add all changes
git add .

# Commit
git commit -m "Add Streamlit dashboard and deployment config"

# Push
git push
```

## Step 2: Deploy to Streamlit Cloud

1. **Go to Streamlit Cloud**:
   - Visit [share.streamlit.io](https://share.streamlit.io)
   - Sign in with your GitHub account

2. **Create New App**:
   - Click "New app"
   - Select your GitHub repository
   - Choose the branch (usually `main`)
   - Set **Main file path**: `portfolio_dashboard.py`
   - Click "Deploy!"

3. **Wait for Deployment**:
   - Streamlit will install dependencies from `requirements.txt`
   - First deployment takes 2-3 minutes
   - You'll get a public URL like: `https://your-app.streamlit.app`

## Step 3: Configure Environment Variables (Optional)

If your dashboard needs database credentials (for live data), you can add them in Streamlit Cloud:

1. Go to your app settings in Streamlit Cloud
2. Click "Secrets"
3. Add your environment variables:
```toml
DB_TYPE = "mysql"
DB_SERVER = "your-server"
DB_DATABASE = "your-database"
DB_USER = "your-user"
DB_PASSWORD = "your-password"
DB_PORT = "3306"
TICKER = "NIFTY"
```

**Note**: The dashboard will work without these if you're just viewing portfolio data from `portfolio.json`.

## Step 4: Update App (After Changes)

Whenever you push changes to GitHub, Streamlit Cloud will automatically redeploy your app.

Or manually trigger a redeploy:
1. Go to your app in Streamlit Cloud
2. Click "⋮" (three dots) → "Reboot app"

## Troubleshooting

### App won't deploy:
- Check that `portfolio_dashboard.py` exists in the root directory
- Verify `requirements.txt` has all dependencies
- Check the logs in Streamlit Cloud dashboard

### Dashboard shows "No portfolio data":
- The dashboard reads from `portfolio.json`
- This file is excluded from git (for security)
- You can either:
  - Manually upload `portfolio.json` to Streamlit Cloud secrets
  - Or run the monitor locally to generate portfolio data first

### Import errors:
- Make sure all Python files are in the repository
- Check that `portfolio_manager.py` and `generate_signal.py` are committed

## Making Your App Public

By default, Streamlit Cloud apps are public. Anyone with the URL can view them.

To make it private:
- Streamlit Cloud doesn't support private apps on the free tier
- Consider using Streamlit Community Cloud (paid) or self-hosting

## Next Steps

1. **Share your dashboard**: Send the Streamlit URL to anyone
2. **Monitor your portfolio**: The dashboard updates when you push new `portfolio.json` data
3. **Customize**: Edit `portfolio_dashboard.py` and push changes to update the live app

## Support

- Streamlit Docs: [docs.streamlit.io](https://docs.streamlit.io)
- Streamlit Community: [discuss.streamlit.io](https://discuss.streamlit.io)
