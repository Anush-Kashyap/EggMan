from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from backend.database.database import DatabaseManager
from backend.memory.models import MemoryCategory, MemoryRecord
from backend.memory.memory_repository import MemoryRepository
from backend.memory.memory_manager import MemoryManager
from backend.memory.memory_classifier import MemoryClassifier
from backend.memory.memory_importance import ImportanceScorer
from backend.memory.memory_conflict_resolver import ConflictResolver
from backend.memory.memory_expiration import ExpirationManager
from backend.memory.memory_ranker import MemoryRanker
from backend.memory.memory_retriever import MemoryRetriever


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_eggman_memory.sqlite3"
    db_mgr = DatabaseManager(database_path=db_file)
    yield db_mgr
    db_mgr.close()


def test_classifier():
    classifier = MemoryClassifier()
    assert classifier.classify("I prefer Python over C++") == MemoryCategory.PREFERENCE
    assert classifier.classify("I'm building a desktop assistant named Eggman") == MemoryCategory.PROJECT
    assert classifier.classify("I want to learn Rust programming") == MemoryCategory.GOAL
    assert classifier.classify("I know Python and Javascript") == MemoryCategory.SKILL
    assert classifier.classify("I study every morning at 6 AM") == MemoryCategory.HABIT
    assert classifier.classify("My birthday is on November 15") == MemoryCategory.PERSONAL_FACT
    assert classifier.classify("I am sick today with a fever") == MemoryCategory.TEMPORARY
    assert classifier.classify("This is just standard fact information") == MemoryCategory.PERMANENT


def test_importance_scorer():
    scorer = ImportanceScorer()
    
    # Category base values check
    pf_score = scorer.score(MemoryCategory.PERSONAL_FACT, "name", "My name is Anush", "explicit")
    temp_score = scorer.score(MemoryCategory.TEMPORARY, "state", "I'm travelling today", "explicit")
    assert pf_score > temp_score

    # Emphasis keyword bonus
    norm_score = scorer.score(MemoryCategory.PROJECT, "project", "I am building Eggman", "explicit")
    emph_score = scorer.score(MemoryCategory.PROJECT, "project", "I am building Eggman which is extremely important to me", "explicit")
    assert emph_score > norm_score


def test_conflict_resolver(temp_db):
    repo = MemoryRepository(temp_db)
    resolver = ConflictResolver(repo)

    # Save initial preference
    rec1 = MemoryRecord(
        category=MemoryCategory.PREFERENCE,
        key="preference",
        value="I prefer PyCharm as my IDE",
        source="explicit",
    )
    repo.save_memory(rec1)

    # Save conflicting preference
    rec2 = MemoryRecord(
        category=MemoryCategory.PREFERENCE,
        key="preference",
        value="I switched to VS Code now",
        source="explicit",
    )
    resolver.resolve(rec2)
    repo.save_memory(rec2)

    # Old memory should be marked inactive, and new memory should supersede it
    m1 = repo.get_memory(rec1.id)
    m2 = repo.get_memory(rec2.id)

    assert m1.active is False
    assert m2.active is True
    assert m2.supersedes == m1.id


def test_expiration_manager(temp_db):
    repo = MemoryRepository(temp_db)
    expiration = ExpirationManager(repo, default_ttl_hours=48)

    rec1 = MemoryRecord(
        category=MemoryCategory.TEMPORARY,
        key="state",
        value="I am sick today",
        source="explicit",
    )
    expiration.set_expiration(rec1)
    repo.save_memory(rec1)
    
    assert rec1.expires_at is not None
    
    # Test lazy expiration sweep
    # Manually expire it by setting expires_at to the past
    rec1.expires_at = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    repo.update_memory(rec1)

    expiration.check_and_expire_lazy()

    m1 = repo.get_memory(rec1.id)
    assert m1.active is False


def test_memory_ranker():
    ranker = MemoryRanker()
    m1 = MemoryRecord(
        category=MemoryCategory.SKILL,
        key="skill",
        value="I am learning Rust",
        importance=80,
        confidence=0.9,
    )
    m2 = MemoryRecord(
        category=MemoryCategory.HABIT,
        key="habit",
        value="I drink coffee in the morning",
        importance=30,
        confidence=0.8,
    )

    ranked = ranker.rank("I want to learn Rust", [m1, m2])
    assert ranked[0].value == "I am learning Rust"
