import asyncio
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class ConnectionContextManager:
    """Manages context (GCS bucket, BQ dataset) per connection ID."""

    def __init__(self):
        # Structure: { conn_id: {"gcs_bucket": "...", "bq_project": "...", "bq_dataset": "..."} }
        self._context_store: Dict[str, Dict[str, Optional[str]]] = {}
        self._lock = asyncio.Lock()
        logger.info("ConnectionContextManager initialized.")

    async def set_gcs_context(self, conn_id: str, bucket_name: str):
        async with self._lock:
            if conn_id not in self._context_store:
                self._context_store[conn_id] = {}
            self._context_store[conn_id]["gcs_bucket"] = bucket_name
            logger.info(f"[Conn: {conn_id}] GCS context set to bucket '{bucket_name}'")

    async def get_gcs_context(self, conn_id: str) -> Optional[str]:
        async with self._lock:
            return self._context_store.get(conn_id, {}).get("gcs_bucket")

    async def clear_gcs_context(self, conn_id: str):
        async with self._lock:
            if conn_id in self._context_store:
                if "gcs_bucket" in self._context_store[conn_id]:
                    del self._context_store[conn_id]["gcs_bucket"]
                    logger.info(f"[Conn: {conn_id}] GCS context cleared.")
                if not self._context_store[conn_id]: # Remove conn_id if empty
                    del self._context_store[conn_id]

    async def set_bq_context(self, conn_id: str, project_id: str, dataset_id: str):
         async with self._lock:
            if conn_id not in self._context_store:
                self._context_store[conn_id] = {}
            self._context_store[conn_id]["bq_project"] = project_id
            self._context_store[conn_id]["bq_dataset"] = dataset_id
            logger.info(f"[Conn: {conn_id}] BQ context set to '{project_id}:{dataset_id}'")

    async def get_bq_context(self, conn_id: str) -> Optional[Tuple[str, str]]:
         async with self._lock:
            conn_data = self._context_store.get(conn_id, {})
            project = conn_data.get("bq_project")
            dataset = conn_data.get("bq_dataset")
            if project and dataset:
                return project, dataset
            return None

    async def clear_bq_context(self, conn_id: str):
        async with self._lock:
            if conn_id in self._context_store:
                cleared = False
                if "bq_project" in self._context_store[conn_id]:
                    del self._context_store[conn_id]["bq_project"]
                    cleared = True
                if "bq_dataset" in self._context_store[conn_id]:
                    del self._context_store[conn_id]["bq_dataset"]
                    cleared = True
                if cleared:
                     logger.info(f"[Conn: {conn_id}] BQ context cleared.")
                if not self._context_store[conn_id]: # Remove conn_id if empty
                    del self._context_store[conn_id]

    async def clear_connection_context(self, conn_id: str):
        async with self._lock:
            if conn_id in self._context_store:
                del self._context_store[conn_id]
                logger.info(f"[Conn: {conn_id}] All context cleared upon disconnect.")
