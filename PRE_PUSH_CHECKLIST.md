# Pre-Push Security Checklist ✅

## Before You Push to GitHub

Run through this checklist to ensure no secrets are committed:

### ✅ 1. Verify .gitignore is working
```bash
git check-ignore config.local.yaml
# Should output: config.local.yaml
```

### ✅ 2. Check config.yaml has no real tokens
```bash
cat config.yaml | grep "access_token"
# Should show: access_token: ${SHOPIFY_TOKEN_FR}
# Should NOT show: access_token: shpat_...
```

### ✅ 3. Verify what will be committed
```bash
git status
# config.local.yaml should NOT appear in the list
# config.yaml SHOULD appear (it's safe)
```

### ✅ 4. Double-check for secrets
```bash
git diff --cached | grep -i "shpat_"
# Should return nothing (no output)
```

### ✅ 5. Add GitHub Secret BEFORE pushing
1. Go to GitHub repository (create it if needed)
2. Settings → Secrets and variables → Actions
3. New repository secret:
   - Name: `SHOPIFY_TOKEN_FR`
   - Value: [your actual token from config.local.yaml]

### ✅ 6. Safe to push!
```bash
git add .
git commit -m "Feed Manager with GitHub Pages"
git push
```

## 🚨 If Push Gets Blocked

If GitHub still blocks your push:

1. **Check what's being committed**:
   ```bash
   git diff --cached | grep -E "shpat_|access_token"
   ```

2. **Remove sensitive file from staging**:
   ```bash
   git reset config.local.yaml
   ```

3. **Verify .gitignore**:
   ```bash
   cat .gitignore | grep config.local
   ```

4. **Try again**:
   ```bash
   git push
   ```

## 🔒 Security Status

- ✅ config.yaml: Safe (uses placeholders)
- ✅ config.local.yaml: Ignored by git
- ✅ .gitignore: Properly configured
- ✅ GitHub Actions: Uses secrets
- ✅ Documentation: Sanitized

You're ready to push! 🚀
