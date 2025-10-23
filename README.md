# Shopify Product Feed Manager

Automated product feed generator for Shopify stores that creates variant-level XML feeds for Google Shopping, Meta (Facebook), and other advertising channels.

## Features

✅ **Variant-Level Inventory** - Each product variant (size/color) is a separate feed entry with accurate stock status
✅ **Automatic Uploads** - Feeds are uploaded directly to Shopify Files CDN
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
    access_token: shpat_your_access_token_here
    language: fr
    currency: EUR
```

**Get Shopify Access Token:**
1. Go to Shopify Admin → Settings → Apps and sales channels
2. Click "Develop apps" → "Create an app"
3. Configure Admin API scopes:
   - `read_products`
   - `write_files` (for uploading feeds)
4. Install app and copy the Admin API access token

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
# Generate feeds only (saves to feeds/ directory)
python generate_feeds.py

# Generate AND upload to Shopify Files
python generate_feeds.py --upload
```

### Automated Scheduling with GitHub Actions

The included workflow (`.github/workflows/generate-feeds.yml`) automatically:
- Runs every 6 hours
- Generates fresh feeds
- Uploads to Shopify Files
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
├── shopify_uploader.py        # Shopify Files upload module
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
    access_token: shpat_token_fr
    language: fr
    currency: EUR

  - name: DE
    shop_domain: store-de.myshopify.com
    access_token: shpat_token_de
    language: de
    currency: EUR
```

Feeds will be generated for each store automatically.

## Using Feeds in Ad Platforms

### Google Merchant Center

1. Run `python generate_feeds.py --upload`
2. Copy the feed URL from output (e.g., `https://cdn.shopify.com/s/files/.../google_fr_EUR.xml`)
3. In Merchant Center → Products → Feeds → Add feed
4. Choose "Scheduled fetch" and paste the URL
5. Set fetch schedule (daily recommended)

### Meta Commerce Manager

1. Same process as Google - upload and copy URL
2. In Commerce Manager → Catalog → Data Sources
3. Add data feed with the Meta feed URL
4. Set update frequency

## Troubleshooting

### Feeds not uploading

- Check Shopify access token has `write_files` scope
- Verify API version is 2025-10 or later
- Check rate limits (script waits 0.6s between uploads)

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
- **This solution**: Free (using Shopify's included API/CDN)

## Support

For issues or questions:
- Check the troubleshooting section above
- Review Shopify Admin API docs: https://shopify.dev/docs/api/admin
- Open an issue in this repository

## License

MIT License - Use freely for commercial purposes
