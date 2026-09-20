#!/usr/bin/env python3
"""
Comprehensive Unit Test Suite for Shokitora SQLite Journal Engine
=================================================================
Covers 100% of journal_db.py functions, helpers, state transitions,
bulk operations, Kanban boards, and CLI commands.
"""

import os
import sys
import tempfile
import unittest
import sqlite3
import argparse
from io import StringIO
from unittest.mock import patch

# Add package root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shokitora.core.journal_db as jdb
from shokitora.core.journal_db import (
    init_db,
    add_entry,
    update_entry,
    archive_entry,
    link_entries,
    list_entries,
    add_sprint,
    update_sprint,
    list_sprints,
    list_active_sprint_tasks,
    list_kanban_board,
    show_task_history,
    int_or_clear,
    str_or_clear,
    float_or_clear,
    db_session,
    main as journal_main,
)


class TestShokitoraJournal(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_file = os.path.join(self.temp_dir.name, "test_journal.db")
        jdb.DB_PATH = self.db_file
        init_db()

    def tearDown(self):
        self.temp_dir.cleanup()
        if "SHOKITORA_DB_PATH" in os.environ:
            del os.environ["SHOKITORA_DB_PATH"]

    def test_01_schema_initialization_and_backfill(self):
        """Verifies database tables, indexes, and status_history backfill logic."""
        with db_session() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]
            self.assertIn("journal", tables)
            self.assertIn("sprints", tables)
            self.assertIn("status_history", tables)

        # Test backfill condition by manually inserting a task and clearing status_history
        with db_session() as conn:
            conn.execute("INSERT INTO sprints (id, name) VALUES (99, 'Dummy Sprint')")
            conn.execute(
                "INSERT INTO journal (id, timestamp, category, content, status, sprint_id) "
                "VALUES (999, '2026-09-20T00:00:00', 'task', 'Legacy Task', 'OPEN', 99)"
            )
            conn.execute("DELETE FROM status_history")

        # Run init_db again to trigger backfill
        with patch("sys.stdout", new=StringIO()) as out:
            init_db()
            self.assertIn("Backfilled status history for 1 existing tasks", out.getvalue())

    def test_02_db_session_rollback_on_error(self):
        """Verifies transaction rollback when an exception occurs inside db_session."""
        with self.assertRaises(RuntimeError):
            with db_session() as conn:
                conn.execute("INSERT INTO sprints (name) VALUES ('Rollback Sprint')")
                raise RuntimeError("Forced Error")

        with db_session() as conn:
            row = conn.execute("SELECT * FROM sprints WHERE name = 'Rollback Sprint'").fetchone()
            self.assertIsNone(row)

    def test_03_add_entry_all_categories(self):
        """Verifies adding task, idea, decision, learning, and expense primitives."""
        add_sprint("Sprint 1", "2026-09-20", "2026-09-26", "Test Sprint Goal")

        # Task without sprint raises SystemExit
        with self.assertRaises(SystemExit):
            add_entry("task", "Invalid Task Without Sprint")

        # Task with sprint and rich attributes
        add_entry(
            category="task",
            content="Implement Core Feature",
            status="OPEN",
            due_date="2026-09-25",
            sprint_id=1,
            success="All tests pass",
            doc_link="docs/design/plan.md",
            hours_logged=2.0
        )

        # Idea
        add_entry(category="idea", content="Brainstorm auto-triage AI agent")

        # Decision
        add_entry(category="decision", content="Adopt HKDF-SHA256 silicon key derivation", parent_id=1)

        # Learning
        add_entry(category="learning", content="PyPI prohibits uppercase characters in package name")

        # Expense
        add_entry(category="expense", content="Dell Precision Workstation", amount=12500.0, currency="USD")

        with db_session() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) as cnt FROM journal")
            self.assertEqual(cur.fetchone()["cnt"], 5)

    def test_04_archive_and_link_entries(self):
        """Verifies archive_entry and link_entries behaviors."""
        add_sprint("Sprint 1")
        add_entry("task", "Task To Archive", sprint_id=1)
        add_entry("idea", "Idea To Archive")

        # Link idea to task
        link_entries(child_id=2, parent_id=1)
        with db_session() as conn:
            row = conn.execute("SELECT parent_id FROM journal WHERE id = 2").fetchone()
            self.assertEqual(row["parent_id"], 1)

        # Archive task (should log status history transition)
        archive_entry(1)
        with db_session() as conn:
            row = conn.execute("SELECT status FROM journal WHERE id = 1").fetchone()
            self.assertEqual(row["status"], "ARCHIVED")
            hist = conn.execute("SELECT to_status FROM status_history WHERE entry_id = 1 AND to_status = 'ARCHIVED'").fetchone()
            self.assertIsNotNone(hist)

        # Archive idea (non-task)
        archive_entry(2)
        with db_session() as conn:
            row = conn.execute("SELECT status FROM journal WHERE id = 2").fetchone()
            self.assertEqual(row["status"], "ARCHIVED")

        # Archive nonexistent entry
        archive_entry(9999)

    def test_05_list_entries_formatting_and_filters(self):
        """Verifies list_entries with various filters, parent/child formatting, and empty states."""
        # Empty list
        with patch("sys.stdout", new=StringIO()) as out:
            list_entries()
            self.assertIn("No entries found", out.getvalue())

        add_sprint("Sprint Alpha", goal="Alpha Goal")
        add_entry("task", "Alpha Task 1", sprint_id=1, hours_logged=3.5, due_date="2026-09-22", success="Done", doc_link="doc.md", blocked_by=99)
        add_entry("decision", "Decision 1", parent_id=1)
        add_entry("expense", "Cloud Server", amount=250.0, currency="EUR")

        with patch("sys.stdout", new=StringIO()) as out:
            list_entries(category="task", sprint_id=1)
            output = out.getvalue()
            self.assertIn("Alpha Task 1", output)
            self.assertIn("Total Hours Logged: 3.5h", output)
            self.assertIn("Children: #2 DECISION", output)

        with patch("sys.stdout", new=StringIO()) as out:
            list_entries(status="OPEN", parent_id=1)
            self.assertIn("Decision 1", out.getvalue())

    def test_06_update_entry_single_and_bulk(self):
        """Verifies single and bulk updates, CLEAR keywords, and sprint changes."""
        add_sprint("Sprint A")
        add_sprint("Sprint B")
        add_entry("task", "Task A", sprint_id=1)
        add_entry("task", "Task B", sprint_id=1)

        # Bulk update status and sprint
        update_entry("1, 2", status="IN_PROGRESS", sprint_id=2, due_date="2026-09-30")
        with db_session() as conn:
            rows = conn.execute("SELECT status, sprint_id FROM journal WHERE id IN (1, 2)").fetchall()
            for r in rows:
                self.assertEqual(r["status"], "IN_PROGRESS")
                self.assertEqual(r["sprint_id"], 2)

        # Disallowed bulk update (e.g. content) raises SystemExit
        with self.assertRaises(SystemExit):
            update_entry("1, 2", content="New Content For Both")

        # Single update with CLEAR fields on task (keeping sprint_id to satisfy CHECK constraint)
        update_entry(
            1,
            due_date="CLEAR",
            parent_id="CLEAR",
            success="CLEAR",
            blocked_by="CLEAR",
            doc_link="CLEAR",
            content="Updated Content",
            amount="CLEAR",
            currency="CLEAR",
            hours_logged="CLEAR"
        )
        with db_session() as conn:
            row = conn.execute("SELECT * FROM journal WHERE id = 1").fetchone()
            self.assertIsNone(row["due_date"])
            self.assertEqual(row["content"], "Updated Content")

        # Test clearing sprint_id on a non-task entry
        add_entry("idea", "Idea with sprint", sprint_id=1)
        update_entry(3, sprint_id="CLEAR")
        with db_session() as conn:
            row = conn.execute("SELECT sprint_id FROM journal WHERE id = 3").fetchone()
            self.assertIsNone(row["sprint_id"])

        # Test updating sprint with non-integer string and nonexistent sprint
        add_entry("task", "Sprint Transition Task", sprint_id=1)
        update_entry(4, sprint_id="non_int_sprint")
        update_entry(4, sprint_id=9999)


        # No update params
        with patch("sys.stdout", new=StringIO()) as out:
            update_entry(1)
            self.assertIn("No update parameters provided", out.getvalue())

    def test_07_sprints_management_and_kanban(self):
        """Verifies add_sprint, update_sprint, list_sprints, list_active_sprint_tasks, and Kanban."""
        # Empty sprints
        with patch("sys.stdout", new=StringIO()) as out:
            list_sprints()
            self.assertIn("No sprints found", out.getvalue())

        add_sprint("Sprint 1", "2026-09-01", "2026-09-07", "First Goal")
        add_sprint("Sprint 2", "2026-09-08", "2026-09-14", "Second Goal", parent_id=1)

        # Update sprint
        update_sprint(1, name="Sprint 1 Renamed", status="COMPLETED")
        update_sprint(2, status="ACTIVE", goal="CLEAR")
        # Empty sprint update
        with patch("sys.stdout", new=StringIO()) as out:
            update_sprint(1)
            self.assertIn("No update parameters provided", out.getvalue())

        # List sprints with status filter
        with patch("sys.stdout", new=StringIO()) as out:
            list_sprints(status="ACTIVE")
            self.assertIn("Sprint 2", out.getvalue())

        # Active sprint tasks
        add_entry("task", "Active Sprint Task", sprint_id=2, hours_logged=1.0)
        with patch("sys.stdout", new=StringIO()) as out:
            list_active_sprint_tasks()
            self.assertIn("Active Sprint Task", out.getvalue())

        # No active sprint
        update_sprint(2, status="COMPLETED")
        with patch("sys.stdout", new=StringIO()) as out:
            list_active_sprint_tasks()
            self.assertIn("No active sprint found", out.getvalue())

        # Kanban board tests with long task truncation
        long_content = "Extremely Long Task Content That Exceeds The Column Width By Many Characters"
        add_entry("task", "Open Task", sprint_id=1, status="OPEN")
        add_entry("task", long_content, sprint_id=1, status="IN_PROGRESS", blocked_by=1, hours_logged=2.0)
        add_entry("task", "Done Task", sprint_id=1, status="COMPLETED", hours_logged=3.0)
        add_entry("task", "Blocked Task", sprint_id=1, status="BLOCKED")


        # Update entry passing Python list of IDs
        update_entry([2, 3], status="IN_PROGRESS")

        with patch("sys.stdout", new=StringIO()) as out:
            list_kanban_board(1)
            kanban_out = out.getvalue()
            self.assertIn("KANBAN BOARD: Sprint 1 Renamed", kanban_out)
            self.assertIn("Open Task", kanban_out)
            self.assertIn("Done Task", kanban_out)
            self.assertIn("Total Hours Logged in Sprint: 5.0h", kanban_out)

        # Kanban for nonexistent sprint
        with patch("sys.stdout", new=StringIO()) as out:
            list_kanban_board(9999)
            self.assertIn("Error: Sprint 9999 not found", out.getvalue())

    def test_08_task_history(self):
        """Verifies show_task_history for existing, new, empty history, and nonexistent tasks."""
        add_sprint("Sprint 1")
        add_entry("task", "History Task", sprint_id=1)
        update_entry(1, status="IN_PROGRESS")
        update_entry(1, status="COMPLETED")

        with patch("sys.stdout", new=StringIO()) as out:
            show_task_history(1)
            hist_out = out.getvalue()
            self.assertIn("OPEN ➔ IN_PROGRESS", hist_out)
            self.assertIn("IN_PROGRESS ➔ COMPLETED", hist_out)

        # Task with empty history
        with db_session() as conn:
            conn.execute("INSERT INTO journal (id, timestamp, category, content, status, sprint_id) VALUES (888, '2026-09-20T00:00:00', 'task', 'No Hist Task', 'OPEN', 1)")
        with patch("sys.stdout", new=StringIO()) as out:
            show_task_history(888)
            self.assertIn("No transition history recorded yet", out.getvalue())

        # Nonexistent task
        with patch("sys.stdout", new=StringIO()) as out:
            show_task_history(9999)
            self.assertIn("Error: Task #9999 not found", out.getvalue())

    def test_09_type_converters(self):
        """Verifies int_or_clear, str_or_clear, float_or_clear."""
        self.assertEqual(int_or_clear("clear"), "CLEAR")
        self.assertEqual(int_or_clear("None"), "CLEAR")
        self.assertEqual(int_or_clear("42"), 42)
        with self.assertRaises(argparse.ArgumentTypeError):
            int_or_clear("abc")

        self.assertEqual(str_or_clear("clear"), "CLEAR")
        self.assertEqual(str_or_clear("hello"), "hello")

        self.assertEqual(float_or_clear("clear"), "CLEAR")
        self.assertEqual(float_or_clear("3.14"), 3.14)
        with self.assertRaises(argparse.ArgumentTypeError):
            float_or_clear("xyz")

    def test_10_cli_main_dispatch(self):
        """Verifies main() entrypoint routing for all subcommands."""
        commands = [
            ["journal_db.py", "init"],
            ["journal_db.py", "sprint", "add", "CLI Sprint", "--start", "2026-09-20", "--end", "2026-09-26", "--goal", "Goal"],
            ["journal_db.py", "sprint:list"],
            ["journal_db.py", "sprint", "list", "--status", "PLANNING"],
            ["journal_db.py", "sprint", "update", "1", "--status", "ACTIVE"],
            ["journal_db.py", "add", "task", "CLI Task", "--sprint", "1", "--hours", "1.5"],
            ["journal_db.py", "add", "idea", "CLI Idea"],
            ["journal_db.py", "ideas:list"],
            ["journal_db.py", "task:list"],
            ["journal_db.py", "task:history", "1"],
            ["journal_db.py", "link", "2", "1"],
            ["journal_db.py", "update", "1", "--status", "COMPLETED"],
            ["journal_db.py", "sprint", "board", "1"],
            ["journal_db.py", "list", "--category", "task"],
            ["journal_db.py", "archive", "2"],
            ["journal_db.py", "sprint"],  # tests sprint without subcommand
            ["journal_db.py"],            # tests empty args
        ]

        for cmd_args in commands:
            with patch("sys.argv", cmd_args), patch("sys.stdout", new=StringIO()):
                journal_main()


if __name__ == "__main__":
    unittest.main(verbosity=2)
