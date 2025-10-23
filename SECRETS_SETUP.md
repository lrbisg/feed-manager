# GitHub Secrets Setup

## 🔐 Security Fix Applied

Your Shopify access tokens are now protected and won't be committed to GitHub.

## How It Works

### Local Development
- Uses `config.local.yaml` (which is in `.gitignore`)
- This file contains your actual tokens
- **Never gets committed to Git**

### GitHub Actions (Production)
- Uses `config.yaml` with environment variable placeholders: `${SHOPIFY_TOKEN_FR}`
- Reads tokens from GitHub Secrets
- Secrets are encrypted and never exposed in logs

## 🚀 Setup Instructions

### Step 1: Add GitHub Secret

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add your secret:
   - **Name**: `SHOPIFY_TOKEN_FR`
   - **Value**: `xxx`
5. Click **Add secret**

### Step 2: Push to GitHub

Now you can safely push:

```bash
git add .
git commit -m "Feed Manager with GitHub Pages and secrets"
git push
```

GitHub's push protection will no longer block you because `config.yaml` only contains placeholders, and `config.local.yaml` is ignored.

## 📁 File Structure

```
Feed Manager/
├── config.yaml              # Safe to commit (uses ${VARIABLES})
├── config.local.yaml        # NEVER committed (has real tokens)
├── .gitignore               # Ignores config.local.yaml
└── .github/workflows/
    └── generate-feeds.yml   # Uses secrets.SHOPIFY_TOKEN_FR
```

## 🧪 Testing

### Local Testing
```bash
# Works automatically - uses config.local.yaml
python generate_feeds.py
```

### Testing with Environment Variables
```bash
# Simulates GitHub Actions environment
export SHOPIFY_TOKEN_FR="xxx"
mv config.local.yaml config.local.yaml.bak  # Temporarily hide local config
python generate_feeds.py
mv config.local.yaml.bak config.local.yaml  # Restore
unset SHOPIFY_TOKEN_FR
```

## 🔄 Adding More Stores

### 1. Update config.yaml (safe to commit)
```yaml
stores:
  - name: FR
    shop_domain: bisgaardshoes-fr.myshopify.com
    access_token: ${SHOPIFY_TOKEN_FR}
    language: fr
    currency: EUR

  - name: DE
    shop_domain: bisgaardshoes-de.myshopify.com
    access_token: ${SHOPIFY_TOKEN_DE}
    language: de
    currency: EUR
```

### 2. Update config.local.yaml (for local dev)
```yaml
stores:
  - name: FR
    shop_domain: bisgaardshoes-fr.myshopify.com
    access_token: shpat_YOUR_FR_TOKEN
    language: fr
    currency: EUR

  - name: DE
    shop_domain: bisgaardshoes-de.myshopify.com
    access_token: shpat_YOUR_DE_TOKEN
    language: de
    currency: EUR
```

### 3. Add GitHub Secret
- Name: `SHOPIFY_TOKEN_DE`
- Value: Your DE store token

### 4. Update GitHub Actions workflow
```yaml
env:
  SHOPIFY_TOKEN_FR: ${{ secrets.SHOPIFY_TOKEN_FR }}
  SHOPIFY_TOKEN_DE: ${{ secrets.SHOPIFY_TOKEN_DE }}
```

## ✅ Verification

Check that secrets are working:

1. **Local**: Run `python generate_feeds.py` - should work using `config.local.yaml`
2. **GitHub**: Push code and check Actions tab - workflow should succeed
3. **Logs**: GitHub Action logs will show `***` instead of actual tokens

## 🚨 Important Notes

- **NEVER** commit `config.local.yaml`
- **NEVER** put real tokens in `config.yaml`
- **ALWAYS** use `${VARIABLE}` syntax in `config.yaml`
- **DO** add new secrets in GitHub Settings before using them in workflows

## 🔒 Security Best Practices

✅ Tokens in GitHub Secrets (encrypted)
✅ Local tokens in .gitignore'd file
✅ Placeholders in committed config
✅ No tokens in logs or history

## 🆘 If You Already Committed a Token

1. **Revoke the token immediately**:
   - Go to Shopify Admin → Settings → Apps and sales channels
   - Find your app → Revoke access token
   - Generate a new token

2. **Update everywhere**:
   - `config.local.yaml` (local)
   - GitHub Secrets (GitHub Actions)

3. **Clear Git history** (optional but recommended):
   ```bash
   # Remove sensitive file from history
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch config.yaml" \
     --prune-empty --tag-name-filter cat -- --all

   # Force push
   git push origin --force --all
   ```

You're now secure and ready to push! 🎉
