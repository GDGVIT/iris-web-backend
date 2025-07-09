from app import celery
from app.services import find_shortest_path
import logging

log = logging.getLogger(__name__)


@celery.task(bind=True)
def find_path_task(self, start_page, end_page):
    """
    Celery task that returns the result directly.
    Celery's backend will handle saving the state.
    """
    try:
        path = find_shortest_path(start_page, end_page)
        # Just return the final result
        return {"status": "SUCCESS", "path": path}
    except Exception as e:
        # Log the exception and re-raise it so Celery marks the task as FAILED
        log.error(f"Task {self.request.id} failed: {e}", exc_info=True)
        # You can also return a failure dictionary if you prefer
        return {"status": "FAILURE", "error": str(e)}
