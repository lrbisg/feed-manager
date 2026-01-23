# Shopify Product Feed Manager

Automated product feed generator for Shopify stores that creates variant-level XML feeds for Google Shopping, Meta (Facebook), and other advertising channels.

## Features

✅ **Variant-Level Inventory** - Each product variant (size/color) is a separate feed entry with accurate stock status
✅ **Free Hosting** - Feeds hosted on GitHub Pages at no cost
✅ **Multi-Channel Support** - Google Shopping and Meta feeds out of the box
✅ **Automated Scheduling** - GitHub Actions workflow runs every 6 hours
✅ **Configurable Mappings** - Easy YAML configuration for field mappings
✅ **API 2025-10** - Uses latest Shopify Admin API version

## Why This Matters

**Problem**: Third-party feed services like DataFeedWatch charge monthly fees and often show products as "in stock" when only unpopular sizes are available.

**Solution**: This tool generates feeds at the variant level, so:
- Only truly available products show as "in stock"
- No monthly fees for feed generation
- Full control over feed customization
- Feeds hosted on your Shopify CDN (free)

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Your Store

Edit `config.yaml`:

```yaml
stores:
  - name: FR
    shop_domain: your-store.myshopify.com
    customer_domain: your-store.com
    client_id: ${SHOPIFY_CLIENT_ID_FR}
    client_secret: ${SHOPIFY_CLIENT_SECRET_FR}
    language: fr
    currency: EUR
```

**Get Shopify OAuth Credentials:**
1. Go to [Shopify Partners](https://partners.shopify.com) and log in (or create an account)
2. Click "Apps" → "Create app"
3. Choose "Create app manually" and give it a name (e.g., "Feed Generator")
4. In your app settings, go to "Configuration" → "Admin API access scopes"
5. Enable `read_products` scope and save
6. Copy the **Client ID** and **Client secret** from "Client credentials"
7. Install the app on your store

> ⚠️ **Note**: As of January 2026, Shopify uses OAuth client credentials instead of permanent tokens. The feed generator automatically obtains short-lived access tokens (valid 24 hours) using your client credentials.

### 3. Customize Channel Mappings (Optional)

Edit `channel_mappings.yaml` to customize which Shopify fields map to feed fields:

```yaml
channels:
  google:
    fields:
      - id: variant.id
      - item_group_id: id
      - title: title
      - price: "{variant.price} {currency}"
      - availability: availability
      # ... more fields
```

**Template Syntax:**
- `variant.price` - Gets variant price
- `{variant.price} {currency}` - Template with placeholders
- `'new'` - Static string value
- `images[0].src` - Nested array/object access

## Usage

### Generate Feeds Locally

```bash
python generate_feeds.py
```

Feeds are saved to `feeds/` and `docs/` (for GitHub Pages).

### Automated Scheduling with GitHub Actions

The included workflow (`.github/workflows/generate-feeds.yml`) automatically:
- Runs every 6 hours
- Generates fresh feeds
- Commits to `docs/` for GitHub Pages hosting
- Archives feed copies as artifacts

**To enable:**
1. Push this code to a GitHub repository
2. GitHub Actions will run automatically
3. Check Actions tab for status

**Manual trigger:**
- Go to Actions → "Generate and Upload Product Feeds" → "Run workflow"

## Feed Structure

### Variant-Level Feeds

Each product variant becomes a separate item:

```xml
<item>
  <g:id>49802838671706</g:id>                      <!-- Variant ID -->
  <g:item_group_id>9877227897178</g:item_group_id> <!-- Product ID (groups variants) -->
  <g:title>bisgaard aarhus rain jacket caramel</g:title>
  <g:link>https://your-store.com/products/jacket?variant=49802838671706</g:link>
  <g:price>69.95 EUR</g:price>
  <g:availability>in stock</g:availability>         <!-- Accurate per-variant stock -->
  <g:size>4Y</g:size>
  <g:color>caramel</g:color>
</item>
```

### Inventory Logic

```python
# generate_feeds.py:149-162
def calculate_availability(variant):
    inventory_qty = variant.get('inventory_quantity', 0)
    inventory_policy = variant.get('inventory_policy', 'deny')

    if inventory_policy == 'continue':
        return 'preorder'  # Can sell when out of stock

    return 'in stock' if inventory_qty > 0 else 'out of stock'
```

## File Structure

```
Feed Manager/
├── generate_feeds.py          # Main feed generator
├── config.yaml                # Store credentials & settings
├── channel_mappings.yaml      # Field mapping configuration
├── requirements.txt           # Python dependencies
├── .github/
│   └── workflows/
│       └── generate-feeds.yml # Automated scheduling
└── feeds/                     # Generated XML files
    └── FR/
        ├── google_fr_EUR.xml
        └── meta_fr_EUR.xml
```

## Adding More Stores

Edit `config.yaml` to add additional stores:

```yaml
stores:
  - name: FR
    shop_domain: store-fr.myshopify.com
    customer_domain: store-fr.com
    client_id: ${SHOPIFY_CLIENT_ID_FR}
    client_secret: ${SHOPIFY_CLIENT_SECRET_FR}
    language: fr
    currency: EUR

  - name: DE
    shop_domain: store-de.myshopify.com
    customer_domain: store-de.com
    client_id: ${SHOPIFY_CLIENT_ID_DE}
    client_secret: ${SHOPIFY_CLIENT_SECRET_DE}
    language: de
    currency: EUR
```

Remember to add the corresponding GitHub Secrets for each store's credentials.

Feeds will be generated for each store automatically.

## Using Feeds in Ad Platforms

### Google Merchant Center

1. Get your GitHub Pages feed URL (e.g., `https://username.github.io/repo/EN_google_en_EUR.xml.gz`)
2. In Merchant Center → Products → Feeds → Add feed
3. Choose "Scheduled fetch" and paste the URL
4. Set fetch schedule (daily recommended)

### Meta Commerce Manager

1. Get your GitHub Pages feed URL (e.g., `https://username.github.io/repo/EN_meta_en_EUR.xml.gz`)
2. In Commerce Manager → Catalog → Data Sources
3. Add data feed with the Meta feed URL
4. Set update frequency

## Troubleshooting

### Feeds not generating

- Check Shopify access token has `read_products` scope
- Verify API version is 2025-10 or later
- Check your token hasn't expired

### Missing product fields

- Check if field exists in Shopify: Add `print(product)` in generate_feeds.py:248
- Update `channel_mappings.yaml` with correct field path
- Use `variant.field_name` for variant-specific fields

### GitHub Actions failing

- Ensure repository secrets are set (if using secrets instead of config.yaml)
- Check Actions logs for specific error messages
- Verify Python 3.11 compatibility

## Customization

### Add New Channels

Edit `channel_mappings.yaml`:

```yaml
channels:
  google:
    # ... existing
  meta:
    # ... existing
  new_channel:
    fields:
      - id: variant.id
      - title: title
      # ... your mappings
```

### Change Upload Frequency

Edit `.github/workflows/generate-feeds.yml`:

```yaml
schedule:
  - cron: '0 */4 * * *'  # Every 4 hours instead of 6
```

### Add Product Filters

Edit `generate_feeds.py:32`:

```python
# Example: Only products with specific tag
return [p for p in all_products if 'sale' in p.get('tags', '').lower()]
```

## Cost Savings

Replacing DataFeedWatch (~€79/month) + Confect.io (~€29/month):
- **Annual savings**: ~€1,296
- **This solution**: Free (using GitHub Pages for hosting)

## Support

For issues or questions:
- Check the troubleshooting section above
- Review Shopify Admin API docs: https://shopify.dev/docs/api/admin
- Open an issue in this repository

## License

MIT License - Use freely for commercial purposes
