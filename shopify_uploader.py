import os
import requests
import time

class ShopifyFilesUploader:
    """
    Upload product feeds to Shopify Files using Admin API.
    Files are hosted on Shopify's CDN and get public URLs automatically.
    """
    def __init__(self, shop_domain, access_token):
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.base_url = f"https://{shop_domain}/admin/api/2025-10"
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json"
        }

    def upload_file(self, local_path, filename=None):
        """
        Upload a file to Shopify Files.

        Steps:
        1. Create a staged upload
        2. Upload file to the staged URL
        3. Create file record in Shopify

        Args:
            local_path: Path to local file
            filename: Optional custom filename (defaults to basename of local_path)

        Returns:
            Public CDN URL of the uploaded file
        """
        if filename is None:
            filename = os.path.basename(local_path)

        # Get file size and mime type
        file_size = os.path.getsize(local_path)
        mime_type = 'application/gzip' if filename.endswith('.gz') else 'application/xml'

        # Step 1: Create staged upload
        print(f"📤 Uploading {filename} ({file_size / 1024 / 1024:.1f}MB)...")

        staged_upload = self._create_staged_upload(filename, file_size, mime_type)
        upload_url = staged_upload['url']
        upload_params = staged_upload['parameters']

        # Step 2: Upload file to staged location
        self._upload_to_staged_url(local_path, upload_url, upload_params)

        # Step 3: Create file record in Shopify
        file_url = self._create_file_record(staged_upload, filename)

        print(f"✓ Uploaded: {filename} → {file_url}")
        return file_url

    def _create_staged_upload(self, filename, file_size, mime_type):
        """
        Request a staged upload URL from Shopify.
        """
        mutation = """
        mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
          stagedUploadsCreate(input: $input) {
            stagedTargets {
              url
              resourceUrl
              parameters {
                name
                value
              }
            }
            userErrors {
              field
              message
            }
          }
        }
        """

        variables = {
            "input": [{
                "resource": "FILE",
                "filename": filename,
                "mimeType": mime_type,
                "httpMethod": "POST",
                "fileSize": str(file_size)
            }]
        }

        response = requests.post(
            f"{self.base_url}/graphql.json",
            json={"query": mutation, "variables": variables},
            headers=self.headers
        )
        response.raise_for_status()

        data = response.json()

        if 'errors' in data:
            raise Exception(f"GraphQL errors: {data['errors']}")

        staged_targets = data['data']['stagedUploadsCreate']['stagedTargets']
        if not staged_targets:
            user_errors = data['data']['stagedUploadsCreate']['userErrors']
            raise Exception(f"Failed to create staged upload: {user_errors}")

        return staged_targets[0]

    def _upload_to_staged_url(self, local_path, upload_url, upload_params):
        """
        Upload file to the staged URL using multipart/form-data.
        Google Cloud Storage expects parameters first, then file last.
        """
        with open(local_path, 'rb') as f:
            file_content = f.read()

        # Determine content type
        content_type = 'application/gzip' if local_path.endswith('.gz') else 'application/xml'

        # Build multipart form data with parameters in order
        # Important: Parameters must come before the file
        form_data = []
        for param in upload_params:
            form_data.append((param['name'], (None, param['value'])))

        # Add file last (this is critical for GCS)
        form_data.append(('file', (os.path.basename(local_path), file_content, content_type)))

        response = requests.post(upload_url, files=form_data)

        # GCS returns 201 for successful POST uploads, 200/204 for PUT
        if response.status_code not in [200, 201, 204]:
            raise Exception(f"Upload failed with status {response.status_code}: {response.text}")

    def _create_file_record(self, staged_upload, filename):
        """
        Create a File record in Shopify after uploading to staged URL.
        """
        mutation = """
        mutation fileCreate($files: [FileCreateInput!]!) {
          fileCreate(files: $files) {
            files {
              ... on GenericFile {
                id
                url
                alt
              }
            }
            userErrors {
              field
              message
            }
          }
        }
        """

        # Extract the resource URL (staged file location)
        resource_url = staged_upload.get('resourceUrl')

        variables = {
            "files": [{
                "alt": filename,
                "contentType": "FILE",
                "originalSource": resource_url
            }]
        }

        response = requests.post(
            f"{self.base_url}/graphql.json",
            json={"query": mutation, "variables": variables},
            headers=self.headers
        )
        response.raise_for_status()

        data = response.json()

        if 'errors' in data:
            raise Exception(f"GraphQL errors: {data['errors']}")

        file_create_data = data.get('data', {}).get('fileCreate', {})
        files = file_create_data.get('files', [])
        user_errors = file_create_data.get('userErrors', [])

        if user_errors:
            raise Exception(f"Failed to create file record: {user_errors}")

        if not files or not files[0]:
            raise Exception(f"No files returned from fileCreate. Response: {data}")

        # Return the public CDN URL
        file_url = files[0].get('url')
        file_id = files[0].get('id')

        if not file_url and file_id:
            # URL not immediately available, query for it
            print(f"  ⏳ Fetching CDN URL for file {file_id}...")
            time.sleep(2)  # Wait a bit for Shopify to process
            file_url = self._get_file_url(file_id)

        if not file_url:
            # Fall back to resource URL if CDN URL still not available
            print(f"  ⚠ CDN URL not available. Using staging URL.")
            return staged_upload.get('resourceUrl', 'URL not available yet')

        return file_url

    def _get_file_url(self, file_id):
        """Query Shopify for the file's CDN URL."""
        query = """
        query getFile($id: ID!) {
          node(id: $id) {
            ... on GenericFile {
              id
              url
            }
          }
        }
        """

        variables = {"id": file_id}

        response = requests.post(
            f"{self.base_url}/graphql.json",
            json={"query": query, "variables": variables},
            headers=self.headers
        )

        data = response.json()
        node = data.get('data', {}).get('node', {})
        return node.get('url')

    def upload_feeds(self, feeds_dir='feeds'):
        """
        Upload all XML feeds from feeds directory to Shopify Files.
        Uploads compressed .gz files which are much smaller.

        Returns:
            Dict mapping local paths to Shopify CDN URLs
        """
        uploaded = {}

        for root, dirs, files in os.walk(feeds_dir):
            for filename in files:
                # Upload compressed files (.gz) - much smaller and faster
                if filename.endswith('.xml.gz'):
                    local_path = os.path.join(root, filename)

                    # Create descriptive filename including store/channel info
                    relative_path = os.path.relpath(local_path, feeds_dir)
                    shopify_filename = relative_path.replace(os.sep, '_')

                    try:
                        url = self.upload_file(local_path, shopify_filename)
                        uploaded[local_path] = url

                        # Shopify API rate limit: 2 requests/second
                        time.sleep(0.6)
                    except Exception as e:
                        print(f"✗ Error uploading {local_path}: {e}")

        return uploaded


def upload_to_shopify(config, feeds_dir='feeds'):
    """
    Upload all feeds to Shopify Files for each configured store.

    Args:
        config: Config dict loaded from config.yaml
        feeds_dir: Directory containing generated feeds

    Returns:
        Dict mapping store names to their uploaded feed URLs
    """
    all_uploaded = {}

    print("\n📤 Uploading feeds to Shopify Files...")

    for store in config['stores']:
        store_name = store['name']
        print(f"\n--- Uploading feeds for {store_name} ---")

        uploader = ShopifyFilesUploader(
            shop_domain=store['shop_domain'],
            access_token=store['access_token']
        )

        # Upload only this store's feeds
        store_feeds_dir = os.path.join(feeds_dir, store_name)
        if not os.path.exists(store_feeds_dir):
            print(f"⚠ No feeds found for {store_name}")
            continue

        uploaded = uploader.upload_feeds(store_feeds_dir)
        all_uploaded[store_name] = uploaded

    # Print summary
    print("\n" + "="*60)
    print("✓ Upload Complete - Feed URLs:")
    print("="*60)

    for store_name, feeds in all_uploaded.items():
        print(f"\n{store_name}:")
        for local_path, url in feeds.items():
            feed_name = os.path.basename(local_path)
            print(f"  {feed_name}")
            print(f"    → {url}")

    print("\n" + "="*60)
    print("Copy these URLs to your Google Merchant Center / Meta Catalog")
    print("="*60 + "\n")

    return all_uploaded
