from __future__ import annotations

import os
import pytest
from pathlib import Path
from backend.database.database import DatabaseManager
from backend.database.repositories.kb_repository import KBRepository
from backend.knowledge.document_manager import DocumentManager
from backend.knowledge.knowledge_manager import KnowledgeManager
from backend.knowledge.loaders.base_loader import BaseDocumentLoader
from backend.context.context_builder import ContextBuilder
from backend.retrieval.retrieval_service import RetrievalService


class DummyLoader(BaseDocumentLoader):
    def supported_extensions(self) -> list[str]:
        return [".txt", ".pdf"]

    def load(self, file_path: Path) -> str:
        return "This is a dummy test document containing secret word antigravity and apples."


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_eggman_kb.sqlite3"
    db_mgr = DatabaseManager(database_path=db_file)
    yield db_mgr
    db_mgr.close()


def test_kb_repository_operations(temp_db):
    """Test standard database save, load, search, and delete operations on KBRepository."""
    repo = KBRepository(temp_db)
    
    # Save a document
    doc = repo.save_document(
        filename="test.pdf",
        file_type="pdf",
        file_size=1024,
        content="Antigravity is a concept of creating a place or object that is free from the force of gravity.",
        source_path="/path/to/test.pdf"
    )
    
    assert doc.id is not None
    assert doc.filename == "test.pdf"
    assert doc.file_type == "pdf"
    assert doc.file_size == 1024
    
    # Get all documents
    all_docs = repo.get_all_documents()
    assert len(all_docs) == 1
    assert all_docs[0].filename == "test.pdf"
    
    # Search documents matching keyword
    results = repo.search_documents(["Antigravity"])
    assert len(results) == 1
    assert results[0].filename == "test.pdf"
    
    # Search documents with no matches
    results_none = repo.search_documents(["NonexistentKeyword"])
    assert len(results_none) == 0

    # Delete document
    success = repo.delete_document(doc.id)
    assert success is True
    
    assert len(repo.get_all_documents()) == 0


def test_knowledge_manager_flow(temp_db, tmp_path):
    """Test full document manager + knowledge manager upload and search flow."""
    repo = KBRepository(temp_db)
    doc_mgr = DocumentManager()
    
    # Register dummy loader to avoid actual PDF binary reading during test
    dummy_loader = DummyLoader()
    doc_mgr.register_loader(dummy_loader)
    
    kb_mgr = KnowledgeManager(repo, doc_mgr)
    
    # Create a dummy file to upload
    temp_file = tmp_path / "secret_doc.txt"
    temp_file.write_text("dummy")
    
    # Upload document
    doc = kb_mgr.upload_document(temp_file)
    assert doc.filename == "secret_doc.txt"
    assert doc.file_type == "txt"
    
    # Search document contents
    search_results = kb_mgr.search("What is antigravity?")
    assert len(search_results) == 1
    assert "secret_doc.txt" in search_results[0]
    assert "antigravity" in search_results[0]
    
    # Test removal
    kb_mgr.remove_document(doc.id)
    assert len(kb_mgr.get_all_documents()) == 0


def test_context_builder_kb_injection(temp_db, tmp_path):
    """Test that ContextBuilder searches the KnowledgeManager and injects document context."""
    repo = KBRepository(temp_db)
    doc_mgr = DocumentManager()
    dummy_loader = DummyLoader()
    doc_mgr.register_loader(dummy_loader)
    kb_mgr = KnowledgeManager(repo, doc_mgr)
    
    # Add dummy document to KB
    temp_file = tmp_path / "apples.pdf"
    temp_file.write_text("dummy")
    kb_mgr.upload_document(temp_file)
    
    # Build context builder with our active kb_mgr
    cb = ContextBuilder(retrieval_service=None, knowledge_manager=kb_mgr)
    
    # Context query matching document content
    payload = cb.build_context(user_message="Tell me about apples")
    
    assert "Relevant Document Context:" in payload.system_prompt
    assert "apples.pdf" in payload.system_prompt
    assert "antigravity and apples" in payload.system_prompt
