from __future__ import annotations

import os
import sqlite3
import pytest
from datetime import datetime, timedelta
from backend.database.database import DatabaseManager
from backend.database.repositories.task_repository import TaskRepository
from backend.scheduler.scheduler import Scheduler


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_eggman.sqlite3"
    db_mgr = DatabaseManager(database_path=db_file)
    yield db_mgr
    db_mgr.close()


def test_task_repository_operations(temp_db):
    """Test standard database save, load, and delete operations on TaskRepository."""
    repo = TaskRepository(temp_db)
    
    # Save tasks
    t1 = repo.save_task("Drink water", "30 minutes", "Once")
    t2 = repo.save_task("Study DSA", "7 AM", "Every Monday")
    
    assert t1.id is not None
    assert t1.title == "Drink water"
    assert t1.repeat_status == "Once"
    
    # Get all tasks
    all_tasks = repo.get_all_tasks()
    assert len(all_tasks) == 2
    assert all_tasks[0].title == "Study DSA"  # Ordered by DESC id
    assert all_tasks[1].title == "Drink water"

    # Delete task
    repo.delete_task(t1.id)
    all_tasks_after = repo.get_all_tasks()
    assert len(all_tasks_after) == 1
    assert all_tasks_after[0].title == "Study DSA"


def test_scheduler_nl_parsing(temp_db):
    """Test natural language command parsing under Scheduler."""
    repo = TaskRepository(temp_db)
    scheduler = Scheduler(repo)
    
    # Clean scheduler thread to avoid background logging during test
    scheduler.stop()

    # 1. Remind me to drink water in 30 minutes
    msg = scheduler.parse_and_schedule("Remind me to drink water in 30 minutes")
    assert "Task scheduled: 'drink water'" in msg
    
    # 2. Tomorrow at 8 PM call mom
    msg2 = scheduler.parse_and_schedule("Tomorrow at 8 PM call mom")
    assert "Task scheduled: 'call mom'" in msg2
    
    # 3. Every Monday at 7 AM study DSA
    msg3 = scheduler.parse_and_schedule("Every Monday at 7 AM study DSA")
    assert "Task scheduled: 'study DSA'" in msg3
    assert "Every Monday" in msg3

    # 4. Every day at 9 AM ask me about today's goals
    msg4 = scheduler.parse_and_schedule("Every day at 9 AM ask me about today's goals")
    assert "Task scheduled: 'ask me about today's goals'" in msg4
    assert "Daily" in msg4

    # Verify storage count
    tasks = repo.get_all_tasks()
    assert len(tasks) == 4
