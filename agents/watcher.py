import os
import time
import logging
import threading
from pathlib import Path




from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler




from agents.main import app




logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)




INCOMING_DIR = Path(
   os.getenv("INCOMING_DIR", "/app/data/incoming")
)




SUPPORTED_EXTENSIONS = {
   ".pdf", ".docx", ".png", ".jpg", ".jpeg"
}




processing_lock = threading.Lock()
processing_files = set()








def process_file(file_path: Path):
   file_path = file_path.resolve()




   if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
       return




   with processing_lock:
       if str(file_path) in processing_files:
           return
       processing_files.add(str(file_path))




   try:
       # Wait until the file is completely written.
       previous_size = -1
       stable_checks = 0




       for _ in range(30):
           if not file_path.exists():
               return




           current_size = file_path.stat().st_size




           if current_size > 0 and current_size == previous_size:
               stable_checks += 1
               if stable_checks >= 2:
                   break
           else:
               stable_checks = 0




           previous_size = current_size
           time.sleep(1)
       else:
           logger.warning("File did not become stable: %s", file_path)
           return




       logger.info("Processing invoice: %s", file_path)




       result = app.invoke({
           "file_path": str(file_path),
           "file_type": file_path.suffix.lower().lstrip("."),
           "processing_status": "detected",
           "is_duplicate": False,
       })




       logger.info(
           "Workflow finished for %s; stage=%s",
           file_path,
           result.get("current_stage"),
       )




   except Exception:
       logger.exception("Failed to process %s", file_path)




   finally:
       with processing_lock:
           processing_files.discard(str(file_path))








def scan_existing_files():
   INCOMING_DIR.mkdir(parents=True, exist_ok=True)




   for file_path in sorted(INCOMING_DIR.iterdir()):
       if file_path.is_file():
           process_file(file_path)








class InvoiceHandler(FileSystemEventHandler):
   def on_created(self, event):
       if not event.is_directory:
           process_file(Path(event.src_path))




   def on_moved(self, event):
       if not event.is_directory:
           process_file(Path(event.dest_path))








def main():
   INCOMING_DIR.mkdir(parents=True, exist_ok=True)




   # Process files already present before watching for new ones.
   scan_existing_files()




   observer = Observer()
   observer.schedule(
       InvoiceHandler(),
       str(INCOMING_DIR),
       recursive=False,
   )
   observer.start()




   logger.info("Watching invoice folder: %s", INCOMING_DIR)




   try:
       while True:
           time.sleep(1)
   except KeyboardInterrupt:
       observer.stop()




   observer.join()

if __name__ == "__main__":
   main()
