from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from agent.graph import process_invoice

logger = logging.getLogger(__name__)

INCOMING_DIR = Path("/app/data/incoming")

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
}


class InvoiceWatcher:

    def __init__(
        self,
        directory: Path = INCOMING_DIR,
        interval: int = 3,
    ):
        self.directory = directory
        self.interval = interval
        self.processing: set[str] = set()

    def discover_files(self) -> list[Path]:
        self.directory.mkdir(parents=True, exist_ok=True)

        return sorted(
            path
            for path in self.directory.iterdir()
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )

    async def process_file(self, path: Path) -> None:
        key = str(path.resolve())

        if key in self.processing:
            return

        self.processing.add(key)

        try:
            logger.info("Processing invoice: %s", path.name)

            result = process_invoice(path)

            if asyncio.iscoroutine(result):
                await result

            logger.info(
                "Invoice processed successfully: %s",
                path.name,
            )

        except Exception:
            logger.exception(
                "Invoice processing failed: %s",
                path.name,
            )

        finally:
            self.processing.discard(key)

    async def scan_once(self) -> None:
        files = self.discover_files()

        if files:
            logger.info(
                "Found %d invoice file(s)",
                len(files),
            )

        for path in files:
            await self.process_file(path)

    async def run(self) -> None:
        logger.info(
            "Invoice watcher started: %s",
            self.directory,
        )

        # Process files already present when the agent starts.
        await self.scan_once()

        while True:
            try:
                await asyncio.sleep(self.interval)
                await self.scan_once()

            except asyncio.CancelledError:
                logger.info("Invoice watcher stopped")
                raise

            except Exception:
                logger.exception("Watcher scan failed")


watcher = InvoiceWatcher()