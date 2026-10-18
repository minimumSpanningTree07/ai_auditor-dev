from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from agent.graph import process_invoice
from agent.services.checksum import ChecksumError, get_file_metadata

logger = logging.getLogger(__name__)
INCOMING_DIR = Path("/app/data/incoming")
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}


class InvoiceWatcher:
    """Poll the mounted input directory and process each unchanged file once.

    Failed files are retried after a cooldown. A successful workflow is not
    rerun on every poll, which prevents duplicate LLM calls and audit writes.
    """

    def __init__(self, directory: Path = INCOMING_DIR, interval: int = 3):
        self.directory = directory
        self.interval = max(1, interval)
        self.processing: set[str] = set()
        self.completed: dict[str, tuple[int, int]] = {}
        self.retry_after: dict[str, float] = {}
        self.retry_delay = 30
        self.known_files: set[str] = set()

    @staticmethod
    def _signature(path: Path) -> tuple[int, int]:
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns

    def discover_files(self) -> list[Path]:
        self.directory.mkdir(parents=True, exist_ok=True)
        return sorted(
            (p for p in self.directory.iterdir()
             if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS),
            key=lambda p: p.name.lower(),
        )

    async def process_file(self, path: Path) -> None:
        key = str(path.resolve())
        if key in self.processing:
            return
        try:
            signature = self._signature(path)
        except OSError:
            logger.exception("Cannot stat incoming invoice %s", path)
            return
        if self.completed.get(key) == signature:
            return
        loop = asyncio.get_running_loop()
        if loop.time() < self.retry_after.get(key, 0):
            return

        self.processing.add(key)
        try:
            metadata = get_file_metadata(path)
            invoice_id = str(metadata.get("invoice_id") or uuid.uuid4())
            state = {
                "thread_id": invoice_id,
                "invoice_id": invoice_id,
                "file_path": str(path.resolve()),
                "file_name": path.name,
                "file_checksum": metadata.get("file_checksum"),
                "file_size": metadata.get("file_size"),
            }
            logger.info("Processing invoice file=%s checksum=%s", path.name, state["file_checksum"])
            # process_invoice is synchronous; run it off the event loop so health/API
            # requests continue to respond while OCR or an LLM call is in progress.
            result: Any = await asyncio.to_thread(process_invoice, state)
            if not isinstance(result, dict):
                raise RuntimeError(f"Workflow returned unexpected result: {type(result).__name__}")
            status = result.get("processing_status")
            persistence_status = result.get("persistence_status")
            if status == "failed" or persistence_status == "failed":
                errors = result.get("errors") or result.get("persistence_error") or "unknown workflow failure"
                logger.error("Invoice workflow failed file=%s errors=%s", path.name, errors)
                self.retry_after[key] = loop.time() + self.retry_delay
                return
            # Mark as done only if it has not changed during processing.
            self.completed[key] = self._signature(path)
            self.retry_after.pop(key, None)
            logger.info("Invoice workflow finished file=%s status=%s invoice_id=%s", path.name, status, result.get("invoice_id", invoice_id))
        except Exception:
            logger.exception("Invoice processing failed: %s", path.name)
            self.retry_after[key] = loop.time() + self.retry_delay
        finally:
            self.processing.discard(key)

    async def scan_once(self) -> None:
        files = self.discover_files()
        current_files = {str(path.resolve()): path for path in files}

        new_files = set(current_files) - self.known_files
        self.known_files = set(current_files)

        if new_files:
            logger.info(
                "Watcher found %d new invoice file(s) in %s",
                len(new_files),
                self.directory,
            )

        for file_key in sorted(new_files):
            path = current_files[file_key]
            await self.process_file(path)
            
    # async def scan_once(self) -> None:
    #     try:
    #         files = self.discover_files()
    #         if files:
    #             logger.info("Watcher found %d supported invoice file(s) in %s", len(files), self.directory)
    #         present = {str(p.resolve()) for p in files}
    #         # Forget removed/renamed files so a later re-upload is handled cleanly.
    #         for key in list(self.completed):
    #             if key not in present:
    #                 self.completed.pop(key, None)
    #                 self.retry_after.pop(key, None)
    #         for path in files:
    #             await self.process_file(path)
    #     except Exception:
    #         logger.exception("Watcher scan failed")

    async def run(self) -> None:
        logger.info("Invoice watcher started directory=%s interval=%ss", self.directory, self.interval)
        await self.scan_once()
        while True:
            try:
                await asyncio.sleep(self.interval)
                await self.scan_once()
            except asyncio.CancelledError:
                logger.info("Invoice watcher stopped")
                raise
            except Exception:
                logger.exception("Unexpected watcher loop failure")


watcher = InvoiceWatcher()
