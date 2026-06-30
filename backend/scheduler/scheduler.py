from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, List, Optional
import re
from backend.database.repositories.task_repository import TaskRepository, ScheduledTask

logger = logging.getLogger("eggman")


class Scheduler:
    """Task scheduler that parses natural language and executes recurring or one-off tasks."""

    def __init__(self, task_repository: TaskRepository, on_trigger: Optional[Callable[[str], None]] = None) -> None:
        self._repository = task_repository
        self._on_trigger = on_trigger
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_run: dict[int, str] = {}  # task_id -> date string last triggered to avoid duplicate runs
        self.start()

    def set_trigger_callback(self, callback: Callable[[str], None]) -> None:
        """Set a callback invoked on the scheduler thread when a task triggers."""
        self._on_trigger = callback

    def start(self) -> None:
        """Start the background checker thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="SchedulerThread", daemon=True)
        self._thread.start()
        logger.info("Task Scheduler started")

    def stop(self) -> None:
        """Stop the background thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("Task Scheduler stopped")

    def parse_and_schedule(self, nl_text: str) -> str:
        """Parse natural language command and save to repository."""
        logger.info("Slash command executed: /schedule %s", nl_text)
        
        text_lower = nl_text.lower().strip()
        title = nl_text
        scheduled_time = ""
        repeat_status = "Once"

        # 1. every [weekday] at [time] [task]
        match = re.match(r"every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+(\d+(?::\d+)?\s*(?:am|pm)?)\s+(.*)", nl_text, re.IGNORECASE)
        if match:
            day = match.group(1).capitalize()
            time_str = match.group(2).strip()
            task = match.group(3).strip()
            title = task
            scheduled_time = time_str
            repeat_status = f"Every {day}"

        # 2. every day at [time] [task] or daily at [time] [task]
        else:
            match = re.match(r"(?:every\s+day|daily)\s+at\s+(\d+(?::\d+)?\s*(?:am|pm)?)\s+(.*)", nl_text, re.IGNORECASE)
            if match:
                time_str = match.group(1).strip()
                task = match.group(2).strip()
                title = task
                scheduled_time = time_str
                repeat_status = "Daily"
            
            # 3. tomorrow at [time] [task]
            else:
                match = re.match(r"tomorrow\s+at\s+(\d+(?::\d+)?\s*(?:am|pm)?)\s+(.*)", nl_text, re.IGNORECASE)
                if match:
                    time_str = match.group(1).strip()
                    task = match.group(2).strip()
                    title = task
                    tomorrow = datetime.now() + timedelta(days=1)
                    tomorrow_date = tomorrow.strftime("%Y-%m-%d")
                    scheduled_time = f"{tomorrow_date} {time_str}"
                    repeat_status = "Once"
                
                # 4. remind me to [task] in [num] seconds
                else:
                    match = re.search(r"(?:remind\s+me\s+to\s+)?(.+?)\s+in\s+(\d+)\s+seconds?", nl_text, re.IGNORECASE)
                    if match:
                        task = match.group(1).strip()
                        seconds = int(match.group(2))
                        run_time = datetime.now() + timedelta(seconds=seconds)
                        title = task
                        scheduled_time = run_time.strftime("%Y-%m-%d %H:%M:%S")
                        repeat_status = "Once"
                    else:
                        # 5. remind me to [task] in [num] minutes
                        match = re.search(r"(?:remind\s+me\s+to\s+)?(.+?)\s+in\s+(\d+)\s+minutes?", nl_text, re.IGNORECASE)
                        if match:
                            task = match.group(1).strip()
                            minutes = int(match.group(2))
                            run_time = datetime.now() + timedelta(minutes=minutes)
                            title = task
                            scheduled_time = run_time.strftime("%Y-%m-%d %H:%M:%S")
                            repeat_status = "Once"
                        else:
                            # 6. remind me to [task] in [num] hours
                            match = re.search(r"(?:remind\s+me\s+to\s+)?(.+?)\s+in\s+(\d+)\s+hours?", nl_text, re.IGNORECASE)
                            if match:
                                task = match.group(1).strip()
                                hours = int(match.group(2))
                                run_time = datetime.now() + timedelta(hours=hours)
                                title = task
                                scheduled_time = run_time.strftime("%Y-%m-%d %H:%M:%S")
                                repeat_status = "Once"
                            else:
                                # Fallback default
                                title = nl_text
                                scheduled_time = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
                                repeat_status = "Once"

        # Save to database
        task_obj = self._repository.save_task(title, scheduled_time, repeat_status)
        logger.info("Schedule created: ID=%s, Title=%s, Time=%s, Repeat=%s", task_obj.id, title, scheduled_time, repeat_status)
        
        return f"📅 Task scheduled: '{title}' at {scheduled_time} ({repeat_status})"

    def _run_loop(self) -> None:
        """Background loop to check for triggered tasks."""
        while not self._stop_event.is_set():
            try:
                tasks = self._repository.get_all_tasks()
                now = datetime.now()
                today_str = now.strftime("%Y-%m-%d")
                weekday_str = now.strftime("%A")  # e.g., "Monday"
                
                for task in tasks:
                    triggered = False
                    
                    if task.repeat_status == "Once":
                        # Check if scheduled time has passed
                        try:
                            dt = None
                            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M %p", "%Y-%m-%d %H:%M", "%Y-%m-%d %I %p", "%Y-%m-%d %H:%M:%S.%f"):
                                try:
                                    dt = datetime.strptime(task.scheduled_time, fmt)
                                    break
                                except ValueError:
                                    continue
                            
                            # Fallback if tomorrow pattern like "2026-07-01 8 PM"
                            if dt is None:
                                match_pm = re.search(r"(\d+)\s*(pm|am)", task.scheduled_time, re.IGNORECASE)
                                if match_pm:
                                    hr = int(match_pm.group(1))
                                    meridiem = match_pm.group(2).lower()
                                    if meridiem == "pm" and hr < 12:
                                        hr += 12
                                    elif meridiem == "am" and hr == 12:
                                        hr = 0
                                    
                                    match_date = re.match(r"(\d{4}-\d{2}-\d{2})", task.scheduled_time)
                                    if match_date:
                                        dt = datetime.strptime(f"{match_date.group(1)} {hr:02d}:00:00", "%Y-%m-%d %H:%M:%S")

                            if dt and now >= dt:
                                triggered = True
                        except Exception as e:
                            logger.error("Error parsing scheduled time for task %s: %s", task.id, e)
                    
                    elif task.repeat_status == "Daily":
                        # Compare hour and minute
                        try:
                            target_hr, target_min = self._parse_time_str(task.scheduled_time)
                            if now.hour == target_hr and now.minute == target_min:
                                if self._last_run.get(task.id) != today_str:
                                    triggered = True
                                    self._last_run[task.id] = today_str
                        except Exception as e:
                            logger.error("Error parsing time for task %s: %s", task.id, e)
                            
                    elif task.repeat_status.startswith("Every "):
                        # Compare weekday, hour, and minute
                        target_day = task.repeat_status.split(" ", 1)[1]
                        if weekday_str.lower() == target_day.lower():
                            try:
                                target_hr, target_min = self._parse_time_str(task.scheduled_time)
                                if now.hour == target_hr and now.minute == target_min:
                                    if self._last_run.get(task.id) != today_str:
                                        triggered = True
                                        self._last_run[task.id] = today_str
                            except Exception as e:
                                logger.error("Error parsing time for task %s: %s", task.id, e)

                    if triggered:
                        logger.info("Schedule triggered: '%s' (%s)", task.title, task.repeat_status)
                        
                        # Notify the UI
                        if self._on_trigger:
                            try:
                                self._on_trigger(f"⏰ Reminder: {task.title}")
                            except Exception as cb_err:
                                logger.error("Trigger callback failed: %s", cb_err)
                        
                        # If Once, delete it
                        if task.repeat_status == "Once":
                            self._repository.delete_task(task.id)

            except Exception as e:
                logger.error("Error in scheduler loop: %s", e)
            
            # Check every 2 seconds for responsive reminders
            time.sleep(2)

    def _parse_time_str(self, time_str: str) -> tuple[int, int]:
        """Parses time string like '9 AM', '7:30 PM', '14:00' to (hour, minute)."""
        time_str = time_str.lower().strip()
        match = re.match(r"(\d+)(?::(\d+))?\s*(am|pm)?", time_str)
        if not match:
            raise ValueError(f"Invalid time string: {time_str}")
        
        hr = int(match.group(1))
        mn = int(match.group(2)) if match.group(2) else 0
        meridiem = match.group(3)
        
        if meridiem == "pm" and hr < 12:
            hr += 12
        elif meridiem == "am" and hr == 12:
            hr = 0
            
        return hr, mn
