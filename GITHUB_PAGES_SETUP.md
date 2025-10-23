# GitHub Pages Setup Guide

## ✅ What's Ready

Your project is now configured for GitHub Pages hosting:

- ✅ Feeds automatically copied to `docs/` folder
- ✅ Beautiful index page created
- ✅ GitHub Actions workflow configured
- ✅ Feeds compressed to 0.6MB and 0.4MB

## 🚀 Quick Setup (5 minutes)

### Step 1: Push to GitHub

```bash
# If not already a git repo, initialize it
git init
git add .
git commit -m "Initial commit: Feed Manager with GitHub Pages"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git
git branch -M main
git push -u origin main
```

### Step 2: Enable GitHub Pages

1. Go to your GitHub repository
2. Click **Settings** (top right)
3. Click **Pages** in the left sidebar
4. Under "Build and deployment":
   - **Source**: Deploy from a branch
   - **Branch**: `main`
   - **Folder**: `/docs`
5. Click **Save**

### Step 3: Wait 2-3 Minutes

GitHub will build and deploy your site. You'll see a message:
> "Your site is live at https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/"

### Step 4: Get Your Feed URLs

Visit: `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/`

You'll see a beautiful page with your feed URLs:
- `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/FR_google_fr_EUR.xml.gz`
- `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/FR_meta_fr_EUR.xml.gz`

Copy these URLs!

## 📝 Add to Google Merchant Center

1. Go to [Google Merchant Center](https://merchants.google.com/)
2. Click **Products** → **Feeds**
3. Click the **+** button (Add Feed)
4. Choose:
   - **Country**: France
   - **Language**: French
   - **Destinations**: Surfaces across Google
5. Click **Continue**
6. Choose **Scheduled fetch**
7. Paste your Google feed URL:
   ```
   https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/FR_google_fr_EUR.xml.gz
   ```
8. Set **Fetch frequency**: Every day
9. Name it: "FR Google Feed (Auto)"
10. Click **Create feed**

Google will fetch and validate the feed. It should process successfully!

## 📝 Add to Meta Commerce Manager

1. Go to [Meta Commerce Manager](https://business.facebook.com/commerce/)
2. Click your **Catalog**
3. Go to **Data Sources** → **Add Items**
4. Choose **Data Feed**
5. Select **Set a schedule**
6. Paste your Meta feed URL:
   ```
   https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/FR_meta_fr_EUR.xml.gz
   ```
7. Set **Update frequency**: Daily
8. Name it: "FR Meta Feed (Auto)"
9. Click **Upload**

Meta will validate and import your products!

## 🤖 Automated Updates

Your GitHub Actions workflow will automatically:

1. **Every 6 hours**: Generate fresh feeds
2. **Commit** them to the `docs/` folder
3. **Push** to GitHub
4. **GitHub Pages** auto-deploys the update

Google and Meta will fetch the updated feeds based on their schedule (daily).

## 🎨 Customization

### Update the Index Page

Edit `docs/index.html` to:
- Change colors/styling
- Add more stores
- Customize the look

### Change Feed Names

Update in `generate_feeds.py:332`:
```python
repo_name = "your-actual-repo-name"
```

And in `docs/index.html:162`:
```javascript
const feeds = [
    { name: 'Your Store - Google', file: 'YOUR_FILE.xml.gz', channel: 'Google' },
    // Add more feeds here
];
```

### Change Update Frequency

Edit `.github/workflows/generate-feeds.yml:5`:
```yaml
schedule:
  - cron: '0 */4 * * *'  # Every 4 hours
  - cron: '0 9,18 * * *'  # 9 AM and 6 PM daily
  - cron: '0 0 * * *'     # Once daily at midnight
```

## 🔍 Troubleshooting

### Feeds Not Updating

1. Check GitHub Actions tab in your repo
2. Look for workflow runs
3. Check for errors in the logs

### 404 Error on Feed URL

1. Make sure GitHub Pages is enabled
2. Wait 2-3 minutes after enabling
3. Check the `docs/` folder has your `.xml.gz` files
4. Ensure branch is set to `main` and folder to `/docs`

### Google Merchant Center Errors

**"Couldn't fetch feed"**:
- Test feed URL in browser - should download
- Check URL is publicly accessible
- Verify `.gz` file isn't corrupt

**"Invalid XML"**:
- Download and decompress locally: `gunzip file.xml.gz`
- Validate XML structure
- Check for special characters in product descriptions

### GitHub Actions Not Running

1. Go to **Settings** → **Actions** → **General**
2. Under "Workflow permissions":
   - Select **Read and write permissions**
   - Check **Allow GitHub Actions to create and approve pull requests**
3. Save and manually trigger workflow

## 💰 Cost

**GitHub Pages**: 100% Free
- Unlimited bandwidth for public repos
- Automatic SSL/HTTPS
- Fast CDN delivery

**Total monthly cost**: €0 (vs €108 for DataFeedWatch + Confect.io)

## 📊 Monitoring

Watch your feeds work:

**GitHub**:
- Actions tab shows each workflow run
- Commits show feed update timestamps

**Google Merchant Center**:
- Feed processing status
- Error reports
- Product count

**Meta Commerce Manager**:
- Catalog item count
- Feed status
- Last update time

## 🎉 You're Done!

Your feeds are now:
- ✅ Self-hosted (free)
- ✅ Auto-updating every 6 hours
- ✅ Variant-level accurate
- ✅ Compressed for speed
- ✅ Served via CDN

Enjoy your €1,296/year savings! 🎊
