"""
Supabase utility functions for database and storage operations.
Uses Supabase admin client for full access to all tables, storage, and operations.
"""

import os
import logging
from typing import Dict, List, Any, Optional, Union
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from app.config import settings

logger = logging.getLogger(__name__)


class SupabaseManager:
    """Manages Supabase client and provides utility methods for database and storage operations."""

    def __init__(self):
        """Initialize Supabase client with service role key for admin access."""
        self.client: Optional[Client] = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Supabase client with admin privileges."""
        try:
            if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
                logger.warning(
                    "Supabase credentials not configured. Supabase operations will be disabled.")
                return

            # Create client with service role key for admin access
            self.client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY,
                options=ClientOptions(
                    postgrest_client_timeout=300,  # 5 minutes for database operations
                    storage_client_timeout=900,    # 15 minutes for storage operations
                    schema="public",
                )
            )
            logger.info(
                "Supabase client initialized successfully with admin privileges")

        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            self.client = None

    def ensure_connection(self):
        """Ensure Supabase connection is active, reconnect if needed."""
        if not self.is_connected():
            logger.info("Reconnecting to Supabase...")
            self._initialize_client()
        return self.is_connected()

    def is_connected(self) -> bool:
        """Check if Supabase client is properly connected."""
        return self.client is not None

    # Database Operations
    async def insert_record(self, table: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insert a single record into a table."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return None

        try:
            result = self.client.table(table).insert(data).execute()
            if result.data:
                logger.info(f"Successfully inserted record into {table}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to insert record into {table}: {e}")
            return None

    def insert_record_sync(self, table: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insert a single record into a table (synchronous version)."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return None

        try:
            result = self.client.table(table).insert(data).execute()
            if result.data:
                logger.info(f"Successfully inserted record into {table}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to insert record into {table}: {e}")
            return None

    async def insert_multiple_records(self, table: str, data: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """Insert multiple records into a table."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return None

        try:
            result = self.client.table(table).insert(data).execute()
            if result.data:
                logger.info(
                    f"Successfully inserted {len(result.data)} records into {table}")
                return result.data
            return None
        except Exception as e:
            logger.error(f"Failed to insert records into {table}: {e}")
            return None

    async def get_record(self, table: str, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get a single record from a table based on filters."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return None

        try:
            query = self.client.table(table).select("*")

            # Apply filters
            for key, value in filters.items():
                query = query.eq(key, value)

            result = query.limit(1).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get record from {table}: {e}")
            return None

    async def get_records(self, table: str, filters: Optional[Dict[str, Any]] = None,
                          limit: Optional[int] = None, offset: Optional[int] = None,
                          order_by: Optional[str] = None, order_direction: str = "asc") -> Optional[List[Dict[str, Any]]]:
        """Get multiple records from a table with optional filtering, pagination, and ordering."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return None

        try:
            query = self.client.table(table).select("*")

            # Apply filters
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)

            # Apply ordering
            if order_by:
                if order_direction.lower() == "desc":
                    query = query.order(order_by, desc=True)
                else:
                    query = query.order(order_by)

            # Apply pagination
            if limit:
                query = query.limit(limit)
            if offset:
                query = query.range(offset, (offset + (limit or 100)) - 1)

            result = query.execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to get records from {table}: {e}")
            return None

    async def update_record(self, table: str, filters: Dict[str, Any], updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a record in a table based on filters."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return None

        try:
            query = self.client.table(table).update(updates)

            # Apply filters
            for key, value in filters.items():
                query = query.eq(key, value)

            result = query.execute()
            if result.data:
                logger.info(f"Successfully updated record in {table}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to update record in {table}: {e}")
            return None

    async def delete_record(self, table: str, filters: Dict[str, Any]) -> bool:
        """Delete a record from a table based on filters."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return False

        try:
            query = self.client.table(table).delete()

            # Apply filters
            for key, value in filters.items():
                query = query.eq(key, value)

            result = query.execute()
            logger.info(f"Successfully deleted record from {table}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete record from {table}: {e}")
            return False

    async def execute_raw_sql(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[List[Dict[str, Any]]]:
        """Execute raw SQL query."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return None

        try:
            result = self.client.rpc(
                'exec_sql', {'sql': sql, 'params': params or {}}).execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to execute raw SQL: {e}")
            return None

    # Storage Operations
    async def upload_file(self, bucket: str, path: str, file_data: bytes,
                          content_type: str = "application/octet-stream") -> Optional[str]:
        """Upload a file to Supabase storage."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return None

        try:
            result = self.client.storage.from_(bucket).upload(
                path=path,
                file=file_data,
                file_options={"content-type": content_type}
            )
            logger.info(f"Successfully uploaded file to {bucket}/{path}")
            return f"{bucket}/{path}"
        except Exception as e:
            logger.error(f"Failed to upload file to {bucket}/{path}: {e}")
            return None

    async def download_file(self, bucket: str, path: str) -> Optional[bytes]:
        """Download a file from Supabase storage."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return None

        try:
            result = self.client.storage.from_(bucket).download(path)
            logger.info(f"Successfully downloaded file from {bucket}/{path}")
            return result
        except Exception as e:
            logger.error(f"Failed to download file from {bucket}/{path}: {e}")
            return None

    async def delete_file(self, bucket: str, path: str) -> bool:
        """Delete a file from Supabase storage."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return False

        try:
            result = self.client.storage.from_(bucket).remove([path])
            logger.info(f"Successfully deleted file from {bucket}/{path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file from {bucket}/{path}: {e}")
            return False

    async def list_files(self, bucket: str, path: str = "") -> Optional[List[Dict[str, Any]]]:
        """List files in a storage bucket."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return None

        try:
            result = self.client.storage.from_(bucket).list(path)
            return result
        except Exception as e:
            logger.error(f"Failed to list files in {bucket}/{path}: {e}")
            return None

    async def get_file_url(self, bucket: str, path: str, expires_in: int = 3600) -> Optional[str]:
        """Get a signed URL for a file."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return None

        try:
            result = self.client.storage.from_(
                bucket).create_signed_url(path, expires_in)
            return result
        except Exception as e:
            logger.error(f"Failed to get signed URL for {bucket}/{path}: {e}")
            return None

    # Bucket Management
    async def create_bucket(self, bucket_name: str, public: bool = False) -> bool:
        """Create a new storage bucket."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return False

        try:
            result = self.client.storage.create_bucket(
                bucket_name,
                options={"public": public}
            )
            logger.info(f"Successfully created bucket: {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create bucket {bucket_name}: {e}")
            return False

    async def delete_bucket(self, bucket_name: str) -> bool:
        """Delete a storage bucket."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return False

        try:
            result = self.client.storage.delete_bucket(bucket_name)
            logger.info(f"Successfully deleted bucket: {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete bucket {bucket_name}: {e}")
            return False

    async def list_buckets(self) -> Optional[List[Dict[str, Any]]]:
        """List all storage buckets."""
        if not self.is_connected():
            logger.error("Supabase client not connected")
            return None

        try:
            result = self.client.storage.list_buckets()
            return result
        except Exception as e:
            logger.error(f"Failed to list buckets: {e}")
            return None


# Global instance
supabase_manager = SupabaseManager()


# Convenience functions for easy access
async def insert_record(table: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Insert a single record into a table."""
    return await supabase_manager.insert_record(table, data)


def insert_record_sync(table: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Insert a single record into a table (synchronous version)."""
    return supabase_manager.insert_record_sync(table, data)


async def insert_multiple_records(table: str, data: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """Insert multiple records into a table."""
    return await supabase_manager.insert_multiple_records(table, data)


async def get_record(table: str, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Get a single record from a table based on filters."""
    return await supabase_manager.get_record(table, filters)


async def get_records(table: str, filters: Optional[Dict[str, Any]] = None,
                      limit: Optional[int] = None, offset: Optional[int] = None,
                      order_by: Optional[str] = None, order_direction: str = "asc") -> Optional[List[Dict[str, Any]]]:
    """Get multiple records from a table with optional filtering, pagination, and ordering."""
    return await supabase_manager.get_records(table, filters, limit, offset, order_by, order_direction)


async def update_record(table: str, filters: Dict[str, Any], updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a record in a table based on filters."""
    return await supabase_manager.update_record(table, filters, updates)


async def delete_record(table: str, filters: Dict[str, Any]) -> bool:
    """Delete a record from a table based on filters."""
    return await supabase_manager.delete_record(table, filters)


async def upload_file(bucket: str, path: str, file_data: bytes,
                      content_type: str = "application/octet-stream") -> Optional[str]:
    """Upload a file to Supabase storage."""
    return await supabase_manager.upload_file(bucket, path, file_data, content_type)


async def download_file(bucket: str, path: str) -> Optional[bytes]:
    """Download a file from Supabase storage."""
    return await supabase_manager.download_file(bucket, path)


async def delete_file(bucket: str, path: str) -> bool:
    """Delete a file from Supabase storage."""
    return await supabase_manager.delete_file(bucket, path)


async def get_file_url(bucket: str, path: str, expires_in: int = 3600) -> Optional[str]:
    """Get a signed URL for a file."""
    return await supabase_manager.get_file_url(bucket, path, expires_in)
