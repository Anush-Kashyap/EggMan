"""Test file upload and background indexing flow."""
import os, sys, tempfile, time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.container import AppContainer
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

tmp = Path(tempfile.mkstemp(suffix=".txt")[1])
tmp.write_text("test")
try:
    doc = c.knowledge_manager.upload_document(tmp)
    print(f"Uploaded doc_id={doc.id} status={doc.status}")
    time.sleep(0.5)

    from backend.database.database import DatabaseManager
    db = DatabaseManager()
    conn = db.get_connection()
    row = conn.execute(
        "SELECT id, status, chunk_count FROM kb_documents WHERE id = ?",
        (doc.id,),
    ).fetchone()
    if row:
        print(f"DB: id={row['id']} status={row['status']} chunks={row['chunk_count']}")
    conn.close()

    report = c.knowledge_manager.last_report
    print(f"last_report: {report}")
    if report:
        print(f"  status={report.status} chunks={report.chunk_count}")
        print(f"  parse_ms={report.parse_duration_ms:.1f}")
        print(f"  chunk_ms={report.chunk_duration_ms:.1f}")
        print(f"  embed_ms={report.embed_duration_ms:.1f}")
        print(f"  store_ms={report.store_duration_ms:.1f}")
finally:
    try:
        tmp.unlink()
    except:
        pass

print("\nNow testing Egg Inspector instantiation...")
try:
    from PySide6.QtWidgets import QApplication, QWidget
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.dialogs import EggInspectorWindow
    parent = QWidget()
    win = EggInspectorWindow(services=c, parent=parent)
    print(f"EggInspectorWindow created: {win is not None}")
    print(f"Tab count: {win.tabs.count()}")
    for i in range(win.tabs.count()):
        print(f"  Tab {i}: {win.tabs.tabText(i)}")
except Exception as e:
    import traceback
    traceback.print_exc()

print("DONE")