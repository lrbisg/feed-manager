import os
import re
import requests
import yaml
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree

# Load config
def load_config(path='config.yaml'):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def fetch_products(store):
    """Fetch all products from Shopify Admin API for a given store config, with correct pagination."""
    all_products = []
    base_url = f"https://{store['shop_domain']}/admin/api/2025-10/products.json?limit=250&status=active"
    headers = {
        "X-Shopify-Access-Token": store['access_token']
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
    - URL templates: 'https://{shop_domain}/products/{handle}?variant={variant.id}'
    - Conditional expressions: 'variant.inventory_quantity > 0 ? "in stock" : "out of stock"'
    """
    # Build context with all available fields
    context = {
        'shop_domain': store['shop_domain'],
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

def products_to_channel_xml(products, store, channel, mapping):
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
                    elif xml_field == 'size' and 'size' in variant_options:
                        value = variant_options['size']
                    elif xml_field == 'color' and 'color' in variant_options:
                        value = variant_options['color']
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

def save_xml(root, path):
    """Save XML file with optional compression."""
    import gzip

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
    import argparse
    from shopify_uploader import upload_to_shopify

    parser = argparse.ArgumentParser(description='Generate Shopify product feeds')
    parser.add_argument('--upload', action='store_true', help='Upload feeds to Shopify after generation')
    args = parser.parse_args()

    config = load_config()
    channel_mappings = load_channel_mappings()
    os.makedirs('feeds', exist_ok=True)

    print("="*60)
    print("Shopify Product Feed Generator")
    print("="*60)

    for store in config['stores']:
        store_folder = os.path.join('feeds', store['name'])
        os.makedirs(store_folder, exist_ok=True)

        print(f"\n📦 Fetching products for {store['name']}...")
        products = fetch_products(store)
        print(f"✓ Found {len(products)} products")

        for channel, mapping in channel_mappings['channels'].items():
            print(f"  Generating {channel} feed...")
            xml_root = products_to_channel_xml(products, store, channel, mapping)
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

    # Upload to Shopify if requested
    if args.upload:
        upload_to_shopify(config)

    # Show GitHub Pages URLs
    if copied_files:
        print("\n" + "="*60)
        print("GitHub Pages Feed URLs:")
        print("="*60)
        print("\nOnce you push to GitHub and enable Pages, your feeds will be at:")
        repo_name = "feed-manager"  # Update this if your repo name is different
        github_user = "YOUR-USERNAME"  # You'll need to update this
        for filename in copied_files:
            print(f"  https://{github_user}.github.io/{repo_name}/{filename}")
        print("\n💡 Remember to:")
        print("  1. Push this code to GitHub")
        print("  2. Go to Settings → Pages → Enable GitHub Pages from 'docs' folder")
        print("="*60)

if __name__ == "__main__":
    main()
