import asyncio
import logging
from typing import Callable, Coroutine, Any

logger = logging.getLogger(__name__)

class TaskQueue:
    """
    A simple in-memory asyncio task queue for development.
    In production, this should be replaced by Celery, RQ, or a similar robust queue.
    """
    def __init__(self):
        self._queue = asyncio.Queue()
        self._workers = []

    async def enqueue(self, task: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any) -> None:
        """Enqueue a background task."""
        await self._queue.put((task, args, kwargs))
        logger.info(f"Task {task.__name__} enqueued.")

    async def _worker(self):
        """Worker loop to process tasks."""
        while True:
            task, args, kwargs = await self._queue.get()
            try:
                await task(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error executing task {task.__name__}: {e}", exc_info=True)
            finally:
                self._queue.task_done()

    def start_workers(self, num_workers: int = 3):
        """Start worker tasks in the background."""
        for _ in range(num_workers):
            worker_task = asyncio.create_task(self._worker())
            self._workers.append(worker_task)
            
    async def stop_workers(self):
        """Stop all background workers gracefully."""
        await self._queue.join()
        for worker in self._workers:
            worker.cancel()

# Global task queue instance
background_queue = TaskQueue()
