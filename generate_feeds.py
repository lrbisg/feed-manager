import os
import re
import requests
import yaml
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree

# Load config
def load_config(path='config.yaml'):
    """Load config with environment variable substitution."""
    # Try local config first (for development)
    if os.path.exists('config.local.yaml'):
        path = 'config.local.yaml'

    with open(path, 'r') as f:
        config_text = f.read()

    # Replace ${VAR} with environment variables
    import re
    def replace_env_var(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    config_text = re.sub(r'\$\{([^}]+)\}', replace_env_var, config_text)

    return yaml.safe_load(config_text)

def get_access_token(store, config):
    """
    Get access token using OAuth 2.0 client credentials grant.
    Tokens are valid for 24 hours.
    """
    token_url = f"https://{store['shop_domain']}/admin/oauth/access_token"

    response = requests.post(
        token_url,
        data={
            'grant_type': 'client_credentials',
            'client_id': config['client_id'],
            'client_secret': config['client_secret']
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    response.raise_for_status()

    token_data = response.json()
    return token_data['access_token']

def fetch_products(store, access_token):
    """Fetch all products from Shopify Admin API for a given store config, with correct pagination."""
    all_products = []
    base_url = f"https://{store['shop_domain']}/admin/api/2025-10/products.json?limit=250&status=active"
    headers = {
        "X-Shopify-Access-Token": access_token
    }
    next_url = base_url
    while next_url:
        response = requests.get(next_url, headers=headers)
        response.raise_for_status()
        products = response.json().get('products', [])
        all_products.extend(products)
        link = response.headers.get('Link')
        next_url = None
        if link and 'rel="next"' in link:
            match = re.search(r'<([^>]+)>; rel="next"', link)
            if match:
                next_url = match.group(1)

    # Optional: Apply filters here if needed
    # Example: filtered = [p for p in all_products if some_condition]
    return all_products

def load_channel_mappings(path='channel_mappings.yaml'):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def strip_html(html_text):
    """Remove HTML tags and clean up text for feed descriptions."""
    if not html_text:
        return ''
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html_text)
    # Decode common HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_nested_value(obj, path):
    """
    Extract nested values from dict using path notation.
    Examples:
      - 'title' -> obj['title']
      - 'images[0].src' -> obj['images'][0]['src']
      - 'variant.price' -> obj['variant']['price']
    """
    parts = re.split(r'\.|\[|\]', path)
    value = obj
    for part in parts:
        if not part:
            continue
        if part.isdigit():
            idx = int(part)
            if isinstance(value, list) and len(value) > idx:
                value = value[idx]
            else:
                return None
        else:
            if isinstance(value, dict):
                value = value.get(part)
                if value is None:
                    return None
            else:
                return None
    return value

def evaluate_template(template, context):
    """
    Evaluate template expressions with conditional logic.
    Supports:
      - Simple field references: {field}
      - Conditionals: field > 0 ? 'yes' : 'no'
      - URLs with placeholders: https://{shop_domain}/products/{handle}
    """
    # Handle conditional expressions (ternary operator)
    ternary_pattern = r'(.+?)\s*\?\s*[\'"](.+?)[\'"]\s*:\s*[\'"](.+?)[\'"]'
    match = re.match(ternary_pattern, template.strip())
    if match:
        condition, true_val, false_val = match.groups()
        # Parse condition (e.g., "variant.inventory_quantity > 0")
        if '>' in condition:
            left, right = condition.split('>')
            left_val = context.get(left.strip())
            right_val = float(right.strip()) if right.strip().replace('.','').isdigit() else right.strip()
            result = true_val if (left_val and float(left_val) > right_val) else false_val
            return result
        elif '<' in condition:
            left, right = condition.split('<')
            left_val = context.get(left.strip())
            right_val = float(right.strip()) if right.strip().replace('.','').isdigit() else right.strip()
            result = true_val if (left_val and float(left_val) < right_val) else false_val
            return result

    # Handle simple string formatting with {placeholders}
    if '{' in template:
        try:
            # Replace {variant.field} with actual values
            result = template
            for key, value in context.items():
                placeholder = '{' + key + '}'
                if placeholder in result:
                    result = result.replace(placeholder, str(value) if value else '')
            return result
        except Exception:
            return template

    # Return as-is if no special processing needed
    return template

def extract_field_value(product, variant, field_spec, store):
    """
    Extract field value from product or variant with support for:
    - Direct fields: 'title', 'vendor'
    - Nested fields: 'images[0].src'
    - Variant fields: 'variant.price', 'variant.sku'
    - URL templates: 'https://{customer_domain}/products/{handle}?variant={variant.id}'
    - Conditional expressions: 'variant.inventory_quantity > 0 ? "in stock" : "out of stock"'
    """
    # Build context with all available fields
    context = {
        'shop_domain': store.get('customer_domain', store['shop_domain']),  # Use customer_domain for URLs
        'customer_domain': store.get('customer_domain', store['shop_domain']),
        'language': store['language'],
        'currency': store['currency']
    }

    # Add all product fields to context (handle nested access)
    context['handle'] = product.get('handle', '')
    context['id'] = product.get('id', '')
    context['title'] = product.get('title', '')
    context['body_html'] = product.get('body_html', '')
    context['vendor'] = product.get('vendor', '')
    context['product_type'] = product.get('product_type', '')

    # Add variant-specific fields to context
    context['variant.id'] = variant.get('id', '')
    context['variant.price'] = variant.get('price', '')
    context['variant.compare_at_price'] = variant.get('compare_at_price', '')
    context['variant.sku'] = variant.get('sku', '')
    context['variant.barcode'] = variant.get('barcode', '')
    context['variant.inventory_quantity'] = variant.get('inventory_quantity', 0)

    # Check if it's a static string (quotes)
    if field_spec.startswith("'") and field_spec.endswith("'"):
        return field_spec[1:-1]

    # Check if it contains template placeholders
    if '{' in field_spec and '}' in field_spec:
        return evaluate_template(field_spec, context)

    # Check for variant field reference
    if field_spec.startswith('variant.'):
        field_path = field_spec.replace('variant.', '')
        value = get_nested_value(variant, field_path)
        return str(value) if value is not None else ''

    # Otherwise try to get from product
    value = get_nested_value(product, field_spec)
    return str(value) if value is not None else ''

def calculate_availability(variant):
    """
    Determine availability status based on variant inventory.
    Returns: 'in stock', 'out of stock', or 'preorder'
    """
    inventory_qty = variant.get('inventory_quantity', 0)
    inventory_policy = variant.get('inventory_policy', 'deny')

    # If inventory_policy is 'continue', items can be sold even when out of stock
    if inventory_policy == 'continue':
        return 'preorder'

    # Otherwise, check actual inventory
    return 'in stock' if inventory_qty > 0 else 'out of stock'

def get_variant_options(product, variant):
    """
    Extract size, color, and other option values for a variant.
    Returns dict with option names as keys.
    """
    options = {}
    for i, option_value in enumerate([variant.get('option1'), variant.get('option2'), variant.get('option3')]):
        if option_value and i < len(product.get('options', [])):
            option_name = product['options'][i]['name'].lower()
            options[option_name] = option_value
    return options

def products_to_channel_xml(products, store, channel, mapping, channel_mappings):
    """
    Generate XML feed with one entry per variant.
    Each variant becomes a separate item with proper item_group_id linking.
    """
    root = Element('rss', version='2.0')
    root.set('xmlns:g', 'http://base.google.com/ns/1.0')
    channel_elem = SubElement(root, 'channel')
    SubElement(channel_elem, 'title').text = f"{store['name']} Product Feed - {channel.upper()}"
    SubElement(channel_elem, 'link').text = f"https://{store['shop_domain']}"
    SubElement(channel_elem, 'description').text = f"Product feed for {channel}"

    for product in products:
        variants = product.get('variants', [])

        for variant in variants:
            item = SubElement(channel_elem, 'item')

            # Get variant options (size, color, etc.)
            variant_options = get_variant_options(product, variant)

            for field_map in mapping['fields']:
                for xml_field, field_spec in field_map.items():
                    # Handle special fields
                    if xml_field == 'availability':
                        value = calculate_availability(variant)
                    elif xml_field == 'description':
                        # Strip HTML from description
                        raw_value = extract_field_value(product, variant, field_spec, store)
                        value = strip_html(raw_value)
                    elif xml_field == 'size' and 'size' in variant_options:
                        value = variant_options['size']
                    elif xml_field == 'color' and 'color' in variant_options:
                        value = variant_options['color']
                    elif xml_field == 'price':
                        # Price should be original price (compare_at_price if on sale, otherwise regular price)
                        compare_at = variant.get('compare_at_price')
                        current_price = variant.get('price', '')
                        if compare_at:
                            value = f"{compare_at} {store['currency']}"
                        else:
                            value = f"{current_price} {store['currency']}"
                    elif xml_field == 'sale_price':
                        # Sale price is the discounted price (only when compare_at_price exists)
                        compare_at = variant.get('compare_at_price')
                        if compare_at:
                            current_price = variant.get('price', '')
                            value = f"{current_price} {store['currency']}"
                        else:
                            value = ''  # No sale price if not on sale
                    elif xml_field == 'additional_image_link' and field_spec == 'additional_images':
                        # Add multiple additional_image_link elements for images 2, 3, etc.
                        images = product.get('images', [])
                        for img in images[1:4]:  # Images 2, 3, 4 (index 1, 2, 3)
                            img_url = img.get('src', '')
                            if img_url:
                                if channel == 'google':
                                    img_elem = SubElement(item, 'g:additional_image_link')
                                else:
                                    img_elem = SubElement(item, 'additional_image_link')
                                img_elem.text = img_url
                        continue  # Skip normal element creation
                    elif xml_field == 'google_product_category':
                        # Look up category based on product_type
                        product_type = product.get('product_type', '').lower()
                        category_map = channel_mappings.get('product_type_categories', {})
                        value = category_map.get(product_type, category_map.get('default', ''))
                    else:
                        value = extract_field_value(product, variant, field_spec, store)

                    # Use Google Shopping namespace for standard fields
                    if channel == 'google' and xml_field in ['id', 'title', 'description', 'link',
                                                              'image_link', 'availability', 'price',
                                                              'brand', 'gtin', 'mpn', 'condition',
                                                              'item_group_id', 'color', 'size',
                                                              'sale_price', 'additional_image_link']:
                        elem = SubElement(item, f'g:{xml_field}')
                    else:
                        elem = SubElement(item, xml_field)

                    elem.text = str(value) if value else ''

    return root

def indent_xml(elem, level=0):
    """Add pretty-print indentation to XML elements."""
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent

def save_xml(root, path):
    """Save XML file with optional compression."""
    import gzip

    # Pretty-print XML with one field per line
    indent_xml(root)

    tree = ElementTree(root)

    # Save regular XML
    tree.write(path, encoding='utf-8', xml_declaration=True)

    # Also save compressed version for upload (much smaller)
    gz_path = path + '.gz'
    with gzip.open(gz_path, 'wb') as gz_file:
        tree.write(gz_file, encoding='utf-8', xml_declaration=True)

    # Print size comparison
    import os
    original_size = os.path.getsize(path) / 1024 / 1024
    compressed_size = os.path.getsize(gz_path) / 1024 / 1024
    print(f"    Compressed: {gz_path} ({compressed_size:.1f}MB, {compressed_size/original_size*100:.0f}% of original)")

def copy_feeds_to_docs():
    """Copy compressed feeds to docs/ folder for GitHub Pages hosting."""
    import shutil

    docs_dir = 'docs'
    os.makedirs(docs_dir, exist_ok=True)

    print("\n📋 Copying feeds to docs/ for GitHub Pages...")

    copied_files = []
    for root, dirs, files in os.walk('feeds'):
        for filename in files:
            if filename.endswith('.xml.gz'):
                src = os.path.join(root, filename)

                # Flatten structure: FR/google_fr_EUR.xml.gz -> FR_google_fr_EUR.xml.gz
                store_name = os.path.basename(os.path.dirname(src))
                dest_filename = f"{store_name}_{filename}"
                dest = os.path.join(docs_dir, dest_filename)

                shutil.copy2(src, dest)
                copied_files.append(dest_filename)
                print(f"  ✓ {dest_filename}")

    return copied_files

def main():
    config = load_config()
    channel_mappings = load_channel_mappings()
    os.makedirs('feeds', exist_ok=True)

    print("="*60)
    print("Shopify Product Feed Generator")
    print("="*60)

    for store in config['stores']:
        store_folder = os.path.join('feeds', store['name'])
        os.makedirs(store_folder, exist_ok=True)

        print(f"\n🔑 Getting access token for {store['name']}...")
        access_token = get_access_token(store, config)
        print(f"✓ Token obtained (valid for 24 hours)")

        print(f"📦 Fetching products for {store['name']}...")
        products = fetch_products(store, access_token)
        print(f"✓ Found {len(products)} products")

        for channel, mapping in channel_mappings['channels'].items():
            print(f"  Generating {channel} feed...")
            xml_root = products_to_channel_xml(products, store, channel, mapping, channel_mappings)
            out_path = os.path.join(store_folder, f"{channel}_{store['language']}_{store['currency']}.xml")
            save_xml(xml_root, out_path)

            # Count variants in feed
            variant_count = len(xml_root.findall('.//item'))
            print(f"  ✓ Saved: {out_path} ({variant_count} variants)")

    print("\n" + "="*60)
    print("✓ Feed generation complete!")
    print("="*60)

    # Copy feeds to docs/ for GitHub Pages
    copied_files = copy_feeds_to_docs()

    # Show GitHub Pages URLs
    if copied_files:
        base_url = config.get('github_pages_url', 'https://YOUR-USERNAME.github.io/REPO-NAME')
        print("\n" + "="*60)
        print("GitHub Pages Feed URLs:")
        print("="*60)
        for filename in copied_files:
            print(f"  {base_url}/{filename}")
        print("="*60)

if __name__ == "__main__":
    main()
