#!/usr/bin/env python3
"""
Unit Test Suite for Shokitora SQLite Journal Engine
===================================================
"""

import os
import sys
import tempfile
import unittest
import sqlite3

# Add package root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shokitora.core.journal_db as jdb
from shokitora.core.journal_db import init_db, add_entry, update_entry, add_sprint, db_session


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

    def test_01_schema_initialization(self):
        """Verifies database tables and indexes are created properly."""
        with db_session() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]
            self.assertIn("journal", tables)
            self.assertIn("sprints", tables)
            self.assertIn("status_history", tables)

    def test_02_add_and_update_task(self):
        """Verifies task creation, sprint linking, and status transitions."""
        # Create a sprint first (task requires a sprint_id)
        add_sprint("Sprint 1", "2026-09-20", "2026-09-26", "Test Sprint Goal")

        # Add task
        add_entry(
            category="task",
            content="Implement Core Feature",
            status="OPEN",
            sprint_id=1,
            success="Pass 100% of tests"
        )


        with db_session() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, category, content, status FROM journal WHERE id=1")
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["content"], "Implement Core Feature")
            self.assertEqual(row["status"], "OPEN")

        # Update status to COMPLETED
        update_entry("1", status="COMPLETED", hours_logged=1.5)


        with db_session() as conn:
            cur = conn.cursor()
            cur.execute("SELECT status, hours_logged FROM journal WHERE id=1")
            row = cur.fetchone()
            self.assertEqual(row["status"], "COMPLETED")
            self.assertEqual(row["hours_logged"], 1.5)

            # Verify audit status history was recorded
            cur.execute("SELECT from_status, to_status FROM status_history WHERE entry_id=1 AND from_status IS NOT NULL")
            hist = cur.fetchone()
            self.assertIsNotNone(hist)
            self.assertEqual(hist["from_status"], "OPEN")
            self.assertEqual(hist["to_status"], "COMPLETED")



if __name__ == "__main__":
    unittest.main(verbosity=2)
