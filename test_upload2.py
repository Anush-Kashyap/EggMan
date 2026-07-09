"""Verify background indexing error handling works."""
import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, ".")

from app.container import AppContainer
from backend.database.database import DatabaseManager
from backend.knowledge.loaders.base_loader import BaseDocumentLoader


class TxtLoader(BaseDocumentLoader):
    def supported_extensions(self):
        return [".txt", ".pdf"]
    def load(self, path):
        return "test paragraph about something important."
    def load_pages(self, path):
        return [(1, "test paragraph about something important.")]


c = AppContainer()
c.document_manager.register_loader(TxtLoader())

# Verify DB starts clean
db = DatabaseManager()
conn = db.get_connection()
conn.execute("DELETE FROM kb_documents")
conn.commit()
conn.close()

import tempfile
from pathlib import Path
tmp = Path(tempfile.mkstemp(suffix=".txt")[1])
tmp.write_text("test")
doc = c.knowledge_manager.upload_document(tmp)
print(f"Uploaded: id={doc.id} status={doc.status}")
tmp.unlink()

# Wait for indexing to complete (will fail with no Ollama)
for i in range(10):
    report = c.knowledge_manager.last_report
    if report:
        print(f"Report after {i+1}s: status={report.status} error={report.error}")
        break
    time.sleep(1)
else:
    print("Report never arrived - checking DB directly")

# Check DB status
db = DatabaseManager()
conn = db.get_connection()
rows = conn.execute("SELECT id, status, chunk_count FROM kb_documents").fetchall()
for r in rows:
    status = r["status"]
    chunks = r["chunk_count"]
    print(f"DB doc: id={r['id']} status={status} chunks={chunks}")
conn.close()
db.close()

print("DONE")