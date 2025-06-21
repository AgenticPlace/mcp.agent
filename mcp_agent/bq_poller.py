import asyncio
import logging
from typing import Optional

from google.cloud import bigquery
from google.api_core import exceptions as google_exceptions

try:
    from .job_store import FirestoreBqJobStore, BqJobInfo
    from .utils import retry_on_gcp_transient_error # For direct BQ calls if needed
except ImportError:
    # This fallback is primarily for scenarios where the module might be loaded in isolation
    # or if there's a temporary PYTHONPATH issue during development.
    # In a packaged application, this should ideally not be hit.
    logging.critical("Failed to import job_store or utils in bq_poller.py. Poller may not function.")
    # Define dummy classes/decorators if needed for the file to load without error,
    # though functionality will be broken.
    class BqJobInfo: pass
    class FirestoreBqJobStore: pass
    def retry_on_gcp_transient_error(func): return func


logger = logging.getLogger("mcp_agent.bq_poller")

# Define a synchronous helper for get_job to apply tenacity retry
@retry_on_gcp_transient_error
def _get_bq_job_sync(client: bigquery.Client, job_id: str, location: Optional[str]) -> bigquery.QueryJob:
    """Synchronous helper to fetch a BigQuery job, wrapped with retry."""
    logger.debug(f"Polling BQ API for job {job_id} in location {location or 'default'}")
    return client.get_job(job_id, location=location)


async def run_bq_job_poller(
    firestore_job_store: FirestoreBqJobStore,
    bq_client: bigquery.Client,
    poll_interval_seconds: int = 60, # Default poll interval 1 minute
    pending_job_query_limit: int = 50 # Max jobs to fetch from Firestore per poll cycle
):
    """
    Periodically queries Firestore for pending BigQuery jobs,
    checks their status against the BigQuery API, and updates Firestore.
    """
    logger.info(f"Starting BigQuery Job Poller. Poll interval: {poll_interval_seconds}s, Firestore query limit: {pending_job_query_limit} jobs.")

    while True:
        try:
            logger.debug("Polling for pending BigQuery jobs...")
            # Query Firestore for jobs that are not in a terminal state
            # older_than_minutes can be 0 to get all pending jobs, or a value to pick up potentially stuck ones.
            pending_jobs = await firestore_job_store.query_pending_jobs(older_than_minutes=0, limit=pending_job_query_limit)

            if not pending_jobs:
                logger.debug("No pending BQ jobs found in Firestore to poll.")
            else:
                logger.info(f"Found {len(pending_jobs)} pending BQ job(s) to check.")

            for job_info in pending_jobs:
                try:
                    logger.debug(f"Checking status of BQ job {job_info.job_id} (Firestore status: {job_info.status})")

                    # Get current job status from BigQuery API
                    bq_job: Optional[bigquery.QueryJob] = await asyncio.to_thread(
                        _get_bq_job_sync, bq_client, job_info.job_id, job_info.location
                    )

                    if not bq_job: # Should not happen if get_job_sync is robust, but as a safeguard
                        logger.warning(f"BQ job {job_info.job_id} not found via API, though pending in Firestore. Marking as ERROR.")
                        await firestore_job_store.update_job_status(
                            job_id=job_info.job_id,
                            status="ERROR",
                            error_result={"error_type": "PollingError", "message": "Job not found via BQ API during polling."}
                        )
                        continue

                    current_bq_status = bq_job.state
                    logger.debug(f"BQ API status for job {job_info.job_id}: {current_bq_status}")

                    if current_bq_status == job_info.status and current_bq_status not in ["DONE", "ERROR"]:
                        # Status hasn't changed, but ensure updated_time is touched in Firestore to prevent
                        # it from being picked up by older_than_minutes filter if it's actively being polled.
                        # However, only update if it's truly PENDING/RUNNING. If it's DONE/ERROR in BQ but not FS,
                        # the below conditions will handle it.
                        # For now, let's only update if status truly changes to avoid too many writes.
                        # If a job is genuinely stuck in PENDING/RUNNING in BQ, it will keep being polled.
                        logger.debug(f"Job {job_info.job_id} status ({current_bq_status}) unchanged from Firestore. No update unless terminal.")
                        # Optionally, one could update `updated_time` here to show polling activity.
                        # await firestore_job_store.update_job_status(job_id=job_info.job_id, status=current_bq_status)


                    if current_bq_status == "DONE":
                        error_info = None
                        if bq_job.error_result:
                            logger.warning(f"BQ job {job_info.job_id} completed with errors: {bq_job.error_result}")
                            error_info = bq_job.error_result # This is already a dict
                        else:
                            logger.info(f"BQ job {job_info.job_id} completed successfully.")

                        # TODO: Optionally, gather some results summary here (schema, total rows)
                        # query_details_update = {"schema": bq_job.schema, "total_rows": bq_job.total_rows}
                        # For now, just status and error.
                        await firestore_job_store.update_job_status(
                            job_id=job_info.job_id,
                            status="DONE",
                            error_result=error_info
                            # query_details=query_details_update
                        )
                    elif current_bq_status != job_info.status: # Status changed, but not to DONE (e.g., PENDING -> RUNNING)
                        logger.info(f"BQ job {job_info.job_id} status changed from {job_info.status} to {current_bq_status}. Updating Firestore.")
                        await firestore_job_store.update_job_status(job_id=job_info.job_id, status=current_bq_status)

                    # If BQ status is ERROR (which is not DONE), it would be caught by bq_job.error_result
                    # and handled by the current_bq_status == "DONE" block if BQ API reports "DONE" for errored jobs.
                    # BigQuery API usually sets state to "DONE" even if there are errors (job.error_result is populated).
                    # If BQ API can return a distinct "ERROR" state, that needs specific handling.
                    # Assuming error_result being populated means it's effectively an error state.

                except google_exceptions.NotFound:
                    logger.warning(f"BQ job {job_info.job_id} not found via BQ API during polling. Marking as ERROR in Firestore.")
                    await firestore_job_store.update_job_status(
                        job_id=job_info.job_id,
                        status="ERROR",
                        error_result={"error_type": "NotFound", "message": "Job not found in BigQuery during polling cycle."}
                    )
                except Exception as e:
                    logger.error(f"Error processing job {job_info.job_id} in BQ poller: {e}", exc_info=True)
                    # Optionally, update Firestore with a poller-specific error, or just let it retry.
                    # For now, we log and continue to the next job. The job will be picked up again.

        except Exception as e:
            logger.error(f"BigQuery Job Poller encountered an unexpected error in its main loop: {e}", exc_info=True)
            # Avoid exiting the poller; wait before retrying the whole loop.

        logger.debug(f"BQ poller cycle complete. Waiting for {poll_interval_seconds} seconds.")
        await asyncio.sleep(poll_interval_seconds)
