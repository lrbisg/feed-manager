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

    # Support both top-level and per-store credentials
    client_id = config.get('client_id') or store.get('client_id')
    client_secret = config.get('client_secret') or store.get('client_secret')

    response = requests.post(
        token_url,
        data={
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    response.raise_for_status()

    token_data = response.json()
    return token_data['access_token']

def fetch_products(store, access_token):
    """Fetch all products with metafields from Shopify GraphQL API."""
    all_products = []
    graphql_url = f"https://{store['shop_domain']}/admin/api/2025-10/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }

    # GraphQL query to fetch products with metafields
    query = """
    query($cursor: String) {
      products(first: 100, after: $cursor, query: "status:active") {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          handle
          title
          descriptionHtml
          vendor
          productType
          images(first: 10) {
            nodes {
              src: url
            }
          }
          variants(first: 100) {
            nodes {
              id
              price
              compareAtPrice
              sku
              barcode
              inventoryQuantity
              inventoryPolicy
              selectedOptions {
                name
                value
              }
            }
          }
          metafields(first: 50, namespace: "custom") {
            nodes {
              namespace
              key
              value
            }
          }
        }
      }
    }
    """

    cursor = None
    while True:
        response = requests.post(
            graphql_url,
            headers=headers,
            json={"query": query, "variables": {"cursor": cursor}}
        )
        response.raise_for_status()
        data = response.json()

        if 'errors' in data:
            raise Exception(f"GraphQL errors: {data['errors']}")

        products_data = data['data']['products']

        for node in products_data['nodes']:
            # Convert GraphQL response to REST-like format for compatibility
            product = {
                'id': node['id'].split('/')[-1],  # Extract numeric ID
                'handle': node['handle'],
                'title': node['title'],
                'body_html': node['descriptionHtml'],
                'vendor': node['vendor'],
                'product_type': node['productType'],
                'images': [{'src': img['src']} for img in node['images']['nodes']],
                'variants': [],
                'metafields': {}
            }

            # Convert variants
            for var in node['variants']['nodes']:
                variant = {
                    'id': var['id'].split('/')[-1],
                    'price': var['price'],
                    'compare_at_price': var['compareAtPrice'],
                    'sku': var['sku'],
                    'barcode': var['barcode'],
                    'inventory_quantity': var['inventoryQuantity'],
                    'inventory_policy': var['inventoryPolicy'].lower() if var['inventoryPolicy'] else 'deny'
                }
                # Add options (option1, option2, option3)
                for i, opt in enumerate(var['selectedOptions']):
                    variant[f'option{i+1}'] = opt['value']
                product['variants'].append(variant)

            # Convert metafields to dict
            for mf in node['metafields']['nodes']:
                product['metafields'][f"{mf['namespace']}.{mf['key']}"] = mf['value']

            # Also need options metadata for get_variant_options
            product['options'] = []
            if node['variants']['nodes']:
                for i, opt in enumerate(node['variants']['nodes'][0]['selectedOptions']):
                    product['options'].append({'name': opt['name']})

            all_products.append(product)

        if not products_data['pageInfo']['hasNextPage']:
            break
        cursor = products_data['pageInfo']['endCursor']

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

def get_field_value(xml_field, field_spec, product, variant, variant_options, store, channel_mappings):
    """
    Get field value based on field_spec format:
    - "literal string" -> literal value
    - metafields.custom.key -> metafield value
    - variant.field -> variant field
    - field -> product field
    - "{template}" -> template with placeholders
    - Special fields: availability, price, sale_price, size, color, google_product_category
    """
    import json
    metafields = product.get('metafields', {})

    # Special field handlers
    if xml_field == 'availability':
        return calculate_availability(variant)

    if xml_field == 'description':
        raw_value = extract_field_value(product, variant, field_spec, store)
        return strip_html(raw_value)

    if xml_field == 'size':
        return variant_options.get('size') or variant_options.get('sizes') or variant_options.get('størrelse') or ''

    if xml_field == 'color':
        return variant_options.get('color') or variant_options.get('colour') or variant_options.get('farve') or ''

    if xml_field == 'price' or field_spec == 'price':
        compare_at = variant.get('compare_at_price')
        current_price = variant.get('price', '')
        if compare_at:
            return f"{compare_at} {store['currency']}"
        return f"{current_price} {store['currency']}"

    if xml_field == 'sale_price' or field_spec == 'sale_price':
        compare_at = variant.get('compare_at_price')
        if compare_at:
            current_price = variant.get('price', '')
            return f"{current_price} {store['currency']}"
        return ''

    if xml_field == 'google_product_category':
        product_type = product.get('product_type', '').lower()
        category_map = channel_mappings.get('product_type_categories', {})
        return category_map.get(product_type, category_map.get('default', ''))

    # Handle metafields.namespace.key syntax
    if isinstance(field_spec, str) and field_spec.startswith('metafields.'):
        metafield_path = field_spec.replace('metafields.', '')
        value = metafields.get(metafield_path, '')
        # Also try with _global suffix as fallback
        if not value:
            value = metafields.get(f'{metafield_path}_global', '')
        # Parse JSON array and get first element
        if isinstance(value, str) and value.startswith('['):
            try:
                parsed = json.loads(value)
                return parsed[0] if parsed else ''
            except:
                pass
        return value

    # Handle literal strings (no braces, no dots except in domains)
    if isinstance(field_spec, str) and not field_spec.startswith('{') and '.' not in field_spec and not field_spec.startswith('variant'):
        # Check if it's a known product field
        known_fields = ['title', 'body_html', 'vendor', 'product_type', 'handle', 'id']
        if field_spec in known_fields:
            return product.get(field_spec, '')
        # Otherwise treat as literal
        return field_spec

    # Handle template strings, variant fields, nested fields via existing function
    return extract_field_value(product, variant, field_spec, store)

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
                    # Handle product_highlight specially (dict with boolean metafield mappings)
                    if xml_field == 'product_highlight' and isinstance(field_spec, dict):
                        metafields = product.get('metafields', {})
                        for metafield_key, label in field_spec.items():
                            mf_value = metafields.get(f'custom.{metafield_key}', '')
                            if mf_value == 'true' or mf_value == True:
                                if channel == 'google':
                                    hl_elem = SubElement(item, 'g:product_highlight')
                                else:
                                    hl_elem = SubElement(item, 'product_highlight')
                                hl_elem.text = label
                        continue  # Skip normal element creation

                    # Handle additional_image_link (multiple elements)
                    if xml_field == 'additional_image_link' and field_spec == 'additional_images':
                        images = product.get('images', [])
                        for img in images[1:4]:
                            img_url = img.get('src', '')
                            if img_url:
                                if channel == 'google':
                                    img_elem = SubElement(item, 'g:additional_image_link')
                                else:
                                    img_elem = SubElement(item, 'additional_image_link')
                                img_elem.text = img_url
                        continue

                    # Determine field value based on field_spec
                    value = get_field_value(xml_field, field_spec, product, variant, variant_options, store, channel_mappings)

                    # Use Google Shopping namespace for standard fields
                    if channel == 'google' and xml_field in ['id', 'title', 'description', 'link',
                                                              'image_link', 'availability', 'price',
                                                              'brand', 'gtin', 'mpn', 'condition',
                                                              'item_group_id', 'color', 'size',
                                                              'sale_price', 'additional_image_link',
                                                              'material', 'product_highlight',
                                                              'custom_label_0', 'custom_label_1',
                                                              'google_product_category', 'age_group', 'gender']:
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
