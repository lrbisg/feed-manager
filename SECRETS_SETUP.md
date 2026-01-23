# GitHub Secrets Setup

## 🔐 Security Setup

Your Shopify OAuth credentials are protected and won't be committed to GitHub.

## How It Works

### Local Development
- Uses `config.local.yaml` (which is in `.gitignore`)
- This file contains your actual client ID and secret
- **Never gets committed to Git**

### GitHub Actions (Production)
- Uses `config.yaml` with environment variable placeholders: `${SHOPIFY_CLIENT_ID_FR}`
- Reads credentials from GitHub Secrets
- Secrets are encrypted and never exposed in logs

## 🚀 Setup Instructions

### Step 1: Add GitHub Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add your secrets (for each store):
   - **Name**: `SHOPIFY_CLIENT_ID_FR` / **Value**: Your client ID
   - **Name**: `SHOPIFY_CLIENT_SECRET_FR` / **Value**: Your client secret
5. Click **Add secret** for each

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
├── config.local.yaml        # NEVER committed (has real credentials)
├── .gitignore               # Ignores config.local.yaml
└── .github/workflows/
    └── generate-feeds.yml   # Uses secrets.SHOPIFY_CLIENT_ID_FR etc.
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
export SHOPIFY_CLIENT_ID_FR="your_client_id"
export SHOPIFY_CLIENT_SECRET_FR="your_client_secret"
mv config.local.yaml config.local.yaml.bak  # Temporarily hide local config
python generate_feeds.py
mv config.local.yaml.bak config.local.yaml  # Restore
unset SHOPIFY_CLIENT_ID_FR SHOPIFY_CLIENT_SECRET_FR
```

## 🔄 Adding More Stores

### 1. Update config.yaml (safe to commit)
```yaml
stores:
  - name: FR
    shop_domain: bisgaardshoes-fr.myshopify.com
    customer_domain: bisgaardshoes.fr
    client_id: ${SHOPIFY_CLIENT_ID_FR}
    client_secret: ${SHOPIFY_CLIENT_SECRET_FR}
    language: fr
    currency: EUR

  - name: DE
    shop_domain: bisgaardshoes-de.myshopify.com
    customer_domain: bisgaardshoes.de
    client_id: ${SHOPIFY_CLIENT_ID_DE}
    client_secret: ${SHOPIFY_CLIENT_SECRET_DE}
    language: de
    currency: EUR
```

### 2. Update config.local.yaml (for local dev)
```yaml
stores:
  - name: FR
    shop_domain: bisgaardshoes-fr.myshopify.com
    customer_domain: bisgaardshoes.fr
    client_id: YOUR_FR_CLIENT_ID
    client_secret: YOUR_FR_CLIENT_SECRET
    language: fr
    currency: EUR

  - name: DE
    shop_domain: bisgaardshoes-de.myshopify.com
    customer_domain: bisgaardshoes.de
    client_id: YOUR_DE_CLIENT_ID
    client_secret: YOUR_DE_CLIENT_SECRET
    language: de
    currency: EUR
```

### 3. Add GitHub Secrets
- `SHOPIFY_CLIENT_ID_DE`: Your DE store client ID
- `SHOPIFY_CLIENT_SECRET_DE`: Your DE store client secret

### 4. Update GitHub Actions workflow
```yaml
env:
  SHOPIFY_CLIENT_ID_FR: ${{ secrets.SHOPIFY_CLIENT_ID_FR }}
  SHOPIFY_CLIENT_SECRET_FR: ${{ secrets.SHOPIFY_CLIENT_SECRET_FR }}
  SHOPIFY_CLIENT_ID_DE: ${{ secrets.SHOPIFY_CLIENT_ID_DE }}
  SHOPIFY_CLIENT_SECRET_DE: ${{ secrets.SHOPIFY_CLIENT_SECRET_DE }}
```

## ✅ Verification

Check that secrets are working:

1. **Local**: Run `python generate_feeds.py` - should work using `config.local.yaml`
2. **GitHub**: Push code and check Actions tab - workflow should succeed
3. **Logs**: GitHub Action logs will show `***` instead of actual credentials

## 🚨 Important Notes

- **NEVER** commit `config.local.yaml`
- **NEVER** put real credentials in `config.yaml`
- **ALWAYS** use `${VARIABLE}` syntax in `config.yaml`
- **DO** add new secrets in GitHub Settings before using them in workflows

## 🔒 Security Best Practices

✅ Credentials in GitHub Secrets (encrypted)
✅ Local credentials in .gitignore'd file
✅ Placeholders in committed config
✅ No credentials in logs or history
✅ Short-lived tokens (24h) via OAuth client credentials

## 🆘 If You Already Committed Credentials

1. **Regenerate credentials immediately**:
   - Go to [Shopify Partners](https://partners.shopify.com) → Apps
   - Find your app → API access → Regenerate client secret

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
