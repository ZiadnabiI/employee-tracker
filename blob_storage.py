"""
Azure Blob Storage helper for screenshot uploads.
Stores screenshots in Azure Blob Storage and returns public URLs.
"""

import os
import datetime
import uuid
from azure.storage.blob import BlobServiceClient, ContentSettings

# Azure Storage Configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "screenshots")

_blob_service_client = None
_container_client = None


def _get_container_client():
    """Lazy-initialize the Azure Blob Storage container client."""
    global _blob_service_client, _container_client

    if _container_client is not None:
        return _container_client

    if not AZURE_STORAGE_CONNECTION_STRING:
        print("⚠️  AZURE_STORAGE_CONNECTION_STRING not set. Blob storage disabled.")
        return None

    try:
        _blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        _container_client = _blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER)

        # Create container if it doesn't exist (with public blob access)
        if not _container_client.exists():
            _container_client = _blob_service_client.create_container(
                AZURE_STORAGE_CONTAINER,
                public_access="blob"
            )
            print(f"✅ Created Azure Blob container: {AZURE_STORAGE_CONTAINER}")
        else:
            print(f"✅ Connected to Azure Blob container: {AZURE_STORAGE_CONTAINER}")

        return _container_client
    except Exception as e:
        print(f"❌ Azure Blob Storage connection error: {e}")
        return None


def upload_screenshot(employee_name: str, company_id: int, image_bytes: bytes, manual: bool = False) -> str | None:
    """
    Upload a screenshot image to Azure Blob Storage.

    Args:
        employee_name: Name of the employee
        company_id: Company ID for folder organization
        image_bytes: Raw JPEG image bytes
        manual: Whether this was a manual screenshot request

    Returns:
        Public blob URL string, or None if upload failed
    """
    container = _get_container_client()
    if container is None:
        return None

    try:
        # Generate unique blob name: {company_id}/{employee_name}/{timestamp}_{uuid}.jpg
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        safe_name = employee_name.replace(" ", "_").replace("/", "_")
        prefix = "manual" if manual else "auto"
        blob_name = f"{company_id}/{safe_name}/{timestamp}_{prefix}_{unique_id}.jpg"

        # Upload with JPEG content type
        blob_client = container.upload_blob(
            name=blob_name,
            data=image_bytes,
            overwrite=True,
            content_settings=ContentSettings(content_type="image/jpeg")
        )

        # Return the public URL
        blob_url = blob_client.url
        print(f"✅ Screenshot uploaded to blob: {blob_name}")
        return blob_url

    except Exception as e:
        print(f"❌ Blob upload error: {e}")
        return None


def delete_screenshot(blob_url: str) -> bool:
    """
    Delete a screenshot blob by its URL.

    Args:
        blob_url: The full URL of the blob to delete

    Returns:
        True if deleted successfully, False otherwise
    """
    container = _get_container_client()
    if container is None:
        return False

    try:
        # Extract blob name from URL
        # URL format: https://{account}.blob.core.windows.net/{container}/{blob_name}
        parts = blob_url.split(f"/{AZURE_STORAGE_CONTAINER}/", 1)
        if len(parts) < 2:
            print(f"⚠️  Could not parse blob name from URL: {blob_url}")
            return False

        blob_name = parts[1]
        container.delete_blob(blob_name)
        print(f"✅ Deleted blob: {blob_name}")
        return True

    except Exception as e:
        print(f"❌ Blob delete error: {e}")
        return False
