import sqlite3
import argparse
import sys
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.environ.get("SHOKITORA_DB_PATH", os.environ.get("JOURNAL_DB_PATH", "journal.db"))

@contextmanager
def db_session():
    db_dir = os.path.dirname(os.path.abspath(DB_PATH))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with db_session() as conn:
        # Journal Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'OPEN',
                due_date TEXT,
                parent_id INTEGER,
                sprint_id INTEGER,
                success_criteria TEXT,
                blocked_by INTEGER,
                doc_link TEXT,
                amount REAL,
                currency TEXT DEFAULT 'USD',
                hours_logged REAL DEFAULT 0.0,
                CHECK(category != 'task' OR sprint_id IS NOT NULL)
            )
        """)
        
        # Sprints Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sprints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                goal TEXT,
                status TEXT DEFAULT 'PLANNING',
                parent_id INTEGER
            )
        """)

        # Indexes for optimization
        conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_sprint ON journal(sprint_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_parent ON journal(parent_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_blocked ON journal(blocked_by)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sprints_parent ON sprints(parent_id)")

        # Status History Table for Tasks
        conn.execute("""
            CREATE TABLE IF NOT EXISTS status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT,
                FOREIGN KEY (entry_id) REFERENCES journal(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status_history_entry ON status_history(entry_id)")

        # Migrations for Journal Table (Safe additions)
        journal_cols = [
            ("status", "TEXT DEFAULT 'OPEN'"),
            ("due_date", "TEXT"),
            ("parent_id", "INTEGER"),
            ("sprint_id", "INTEGER"),
            ("success_criteria", "TEXT"),
            ("blocked_by", "INTEGER"),
            ("doc_link", "TEXT"),
            ("amount", "REAL"),
            ("currency", "TEXT DEFAULT 'USD'"),
            ("hours_logged", "REAL DEFAULT 0.0")
        ]
        for col_name, col_def in journal_cols:
            try:
                conn.execute(f"ALTER TABLE journal ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError: pass
        
        # Migrations for Sprints Table
        try:
            conn.execute("ALTER TABLE sprints ADD COLUMN parent_id INTEGER")
        except sqlite3.OperationalError: pass

        # Backfill existing tasks if status_history is empty
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM status_history")
        if cursor.fetchone()['cnt'] == 0:
            existing_tasks = conn.execute("SELECT id, timestamp, status FROM journal WHERE category = 'task'").fetchall()
            for task in existing_tasks:
                conn.execute("""
                    INSERT INTO status_history (entry_id, timestamp, from_status, to_status)
                    VALUES (?, ?, ?, ?)
                """, (task['id'], task['timestamp'], None, task['status']))
            if existing_tasks:
                print(f"Backfilled status history for {len(existing_tasks)} existing tasks.")
        
    print(f"Journal database initialized at {DB_PATH}")

def add_entry(category, content, status='OPEN', due_date=None, parent_id=None, sprint_id=None, success=None, blocked_by=None, doc_link=None, amount=None, currency='USD', hours_logged=0.0):
    if category == 'task' and sprint_id is None:
        print("Error: Sprint ID is required when adding a task.")
        sys.exit(1)
    timestamp = datetime.now().isoformat()
    with db_session() as conn:
        cursor = conn.execute("""
            INSERT INTO journal (timestamp, category, content, status, due_date, parent_id, sprint_id, success_criteria, blocked_by, doc_link, amount, currency, hours_logged) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, category, content, status, due_date, parent_id, sprint_id, success, blocked_by, doc_link, amount, currency, hours_logged))
        
        if category == 'task':
            entry_id = cursor.lastrowid
            conn.execute("""
                INSERT INTO status_history (entry_id, timestamp, from_status, to_status)
                VALUES (?, ?, ?, ?)
            """, (entry_id, timestamp, None, status))
            print(f"Logged initial status for task #{entry_id}: {status}")
            
    print(f"Successfully added {category} entry.")

def archive_entry(entry_id):
    with db_session() as conn:
        row = conn.execute("SELECT status, category FROM journal WHERE id = ?", (entry_id,)).fetchone()
        if row:
            old_status = row['status']
            category = row['category']
            conn.execute("UPDATE journal SET status = 'ARCHIVED' WHERE id = ?", (entry_id,))
            if category == 'task' and old_status != 'ARCHIVED':
                timestamp = datetime.now().isoformat()
                conn.execute("""
                    INSERT INTO status_history (entry_id, timestamp, from_status, to_status)
                    VALUES (?, ?, ?, ?)
                """, (entry_id, timestamp, old_status, 'ARCHIVED'))
                print(f"Logged status transition for task #{entry_id}: {old_status} -> ARCHIVED")
    print(f"Successfully archived entry #{entry_id}.")

def link_entries(child_id, parent_id):
    with db_session() as conn:
        conn.execute("UPDATE journal SET parent_id = ? WHERE id = ?", (parent_id, child_id))
    print(f"Successfully linked child #{child_id} to parent #{parent_id}.")

def list_entries(category=None, limit=10, status=None, parent_id=None, sprint_id=None):
    query = """
        SELECT j1.id, j1.timestamp, j1.category, j1.content, j1.status, j1.due_date, j1.parent_id, j1.sprint_id,
               j1.success_criteria, j1.blocked_by, j1.doc_link, j1.amount, j1.currency, j1.hours_logged,
               j2.category as parent_category, j2.content as parent_content,
               s.name as sprint_name
        FROM journal j1
        LEFT JOIN journal j2 ON j1.parent_id = j2.id
        LEFT JOIN sprints s ON j1.sprint_id = s.id
    """
    params = []
    where_clauses = []
    if category:
        where_clauses.append("j1.category = ?")
        params.append(category)
    if status:
        where_clauses.append("j1.status = ?")
        params.append(status)
    else:
        where_clauses.append("j1.status NOT IN ('ARCHIVED', 'OBSOLETE')")
    if parent_id:
        where_clauses.append("j1.parent_id = ?")
        params.append(parent_id)
    if sprint_id:
        where_clauses.append("j1.sprint_id = ?")
        params.append(sprint_id)
    
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
        
    query += " ORDER BY j1.timestamp DESC LIMIT ?"
    params.append(limit)
    
    with db_session() as conn:
        rows = conn.execute(query, params).fetchall()
        
        if not rows:
            print("No entries found.")
            return

        total_hours = 0.0
        for row in rows:
            due_str = f" [DUE: {row['due_date']}]" if row['due_date'] else ""
            status_str = f" [{row['status']}]" if row['status'] != 'OPEN' and row['category'] == 'task' else ""
            parent_info = f" (Parent #{row['parent_id']}: {row['parent_category'].upper()})" if row['parent_id'] else ""
            sprint_info = f" [Sprint: {row['sprint_name']}]" if row['sprint_id'] else ""
            blocked_info = f" [BLOCKED BY #{row['blocked_by']}]" if row['blocked_by'] else ""
            expense_info = f" [Amount: {row['amount']} {row['currency']}]" if row['amount'] is not None else ""
            hours_info = f" [Hours: {row['hours_logged']}]" if row['hours_logged'] is not None and row['hours_logged'] > 0 else ""
            doc_info = f"\n    └── Doc: {row['doc_link']}" if row['doc_link'] else ""
            success_info = f"\n    └── Success Criteria: {row['success_criteria']}" if row['success_criteria'] else ""
            
            if row['hours_logged'] is not None:
                total_hours += row['hours_logged']

            # Check for children
            children = conn.execute("SELECT id, category FROM journal WHERE parent_id = ?", (row['id'],)).fetchall()
            children_str = ""
            if children:
                child_list = ", ".join([f"#{c['id']} {c['category'].upper()}" for c in children])
                children_str = f"\n    └── Children: {child_list}"
                
            print(f"#{row['id']} [{row['timestamp']}] {row['category'].upper()}{status_str}: {row['content']}{due_str}{expense_info}{hours_info}{parent_info}{sprint_info}{blocked_info}{doc_info}{success_info}{children_str}")
            
        if total_hours > 0.0:
            print(f"\n⏱️ Total Hours Logged: {total_hours}h")


def update_entry(entry_ids, status=None, due_date=None, parent_id=None, sprint_id=None, success=None, blocked_by=None, doc_link=None, content=None, amount=None, currency=None, hours_logged=None):
    if isinstance(entry_ids, str):
        ids = [int(x.strip()) for x in entry_ids.split(",") if x.strip()]
    elif isinstance(entry_ids, int):
        ids = [entry_ids]
    else:
        ids = list(entry_ids)

    if len(ids) > 1:
        # Check if non-bulkable updates are requested
        if parent_id is not None or success is not None or blocked_by is not None or doc_link is not None or content is not None or amount is not None or currency is not None or hours_logged is not None:
            print("Error: Bulk updates are limited to changes in status, sprint, and due date.")
            sys.exit(1)

    updates = []
    params = []
    
    def add_update(col_name, value):
        if value is not None:
            updates.append(f"{col_name} = ?")
            if value == 'CLEAR':
                params.append(None)
            else:
                params.append(value)

    add_update("status", status)
    add_update("due_date", due_date)
    add_update("parent_id", parent_id)
    add_update("sprint_id", sprint_id)
    add_update("success_criteria", success)
    add_update("blocked_by", blocked_by)
    add_update("doc_link", doc_link)
    add_update("content", content)
    add_update("amount", amount)
    add_update("currency", currency)
    add_update("hours_logged", hours_logged)
    
    if not updates:
        print("No update parameters provided.")
        return

    with db_session() as conn:
        for entry_id in ids:
            old_status = None
            old_sprint_id = None
            category = None
            
            row = conn.execute("SELECT status, sprint_id, category FROM journal WHERE id = ?", (entry_id,)).fetchone()
            if row:
                old_status = row['status']
                old_sprint_id = row['sprint_id']
                category = row['category']
            
            # Execute update for this specific ID
            cur_params = params + [entry_id]
            query = f"UPDATE journal SET {', '.join(updates)} WHERE id = ?"
            conn.execute(query, cur_params)
            
            # Log status change if status was updated
            if status is not None and category == 'task' and old_status != status:
                timestamp = datetime.now().isoformat()
                conn.execute("""
                    INSERT INTO status_history (entry_id, timestamp, from_status, to_status)
                    VALUES (?, ?, ?, ?)
                """, (entry_id, timestamp, old_status, status))
                print(f"Logged status transition for task #{entry_id}: {old_status} -> {status}")
                
            # Log sprint change if sprint was updated
            if sprint_id is not None and category == 'task':
                new_sprint_id = None
                if sprint_id != 'CLEAR':
                    try:
                        new_sprint_id = int(sprint_id)
                    except (ValueError, TypeError):
                        new_sprint_id = sprint_id
                
                if old_sprint_id != new_sprint_id:
                    def get_sprint_name(s_id):
                        if s_id is None:  # pragma: no cover
                            return "None"
                        s_row = conn.execute("SELECT name FROM sprints WHERE id = ?", (s_id,)).fetchone()
                        return s_row['name'] if s_row else f"Sprint {s_id}"
                    
                    old_sprint_name = get_sprint_name(old_sprint_id)
                    new_sprint_name = get_sprint_name(new_sprint_id)
                    from_val = f"Sprint: {old_sprint_name}"
                    to_val = f"Sprint: {new_sprint_name}"
                    timestamp = datetime.now().isoformat()
                    conn.execute("""
                        INSERT INTO status_history (entry_id, timestamp, from_status, to_status)
                        VALUES (?, ?, ?, ?)
                    """, (entry_id, timestamp, from_val, to_val))
                    print(f"Logged sprint transition for task #{entry_id}: {from_val} -> {to_val}")
                
            print(f"Successfully updated entry {entry_id}.")

def add_sprint(name, start_date=None, end_date=None, goal=None, parent_id=None):
    with db_session() as conn:
        conn.execute("INSERT INTO sprints (name, start_date, end_date, goal, parent_id) VALUES (?, ?, ?, ?, ?)", 
                     (name, start_date, end_date, goal, parent_id))
    print(f"Successfully added sprint '{name}'.")

def update_sprint(sprint_id, name=None, start_date=None, end_date=None, goal=None, status=None, parent_id=None):
    updates = []
    params = []
    
    def add_update(col_name, value):
        if value is not None:
            updates.append(f"{col_name} = ?")
            if value == 'CLEAR':
                params.append(None)
            else:
                params.append(value)

    add_update("name", name)
    add_update("start_date", start_date)
    add_update("end_date", end_date)
    add_update("goal", goal)
    add_update("status", status)
    add_update("parent_id", parent_id)
    
    if not updates:
        print("No update parameters provided for sprint.")
        return

    params.append(sprint_id)
    query = f"UPDATE sprints SET {', '.join(updates)} WHERE id = ?"
    with db_session() as conn:
        conn.execute(query, params)
    print(f"Successfully updated sprint {sprint_id}.")

def int_or_clear(val):
    if not val or val.lower() in ('clear', 'none', 'null'):
        return 'CLEAR'
    try:
        return int(val)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{val}' is not a valid integer or 'clear'")

def str_or_clear(val):
    if not val or val.lower() in ('clear', 'none', 'null'):
        return 'CLEAR'
    return val

def float_or_clear(val):
    if not val or val.lower() in ('clear', 'none', 'null'):
        return 'CLEAR'
    try:
        return float(val)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{val}' is not a valid float or 'clear'")

def list_sprints(status=None):
    with db_session() as conn:
        query = """
            SELECT s1.id, s1.name, s1.start_date, s1.end_date, s1.goal, s1.status, s1.parent_id,
                   s2.name as parent_name
            FROM sprints s1
            LEFT JOIN sprints s2 ON s1.parent_id = s2.id
        """
        params = []
        if status:
            query += " WHERE s1.status = ?"
            params.append(status)
        
        query += " ORDER BY s1.start_date DESC"
        
        rows = conn.execute(query, params).fetchall()
        if not rows:
            print("No sprints found.")
            return

        print(f"{'ID':<4} | {'Name':<20} | {'Status':<10} | {'Start':<10} | {'End':<10} | {'Parent':<15} | Goal")
        print("-" * 100)
        for row in rows:
            parent_info = f"{row['parent_name']} (#{row['parent_id']})" if row['parent_id'] else ""
            print(f"{row['id']:<4} | {row['name']:<20} | {row['status']:<10} | {row['start_date'] or 'N/A':<10} | {row['end_date'] or 'N/A':<10} | {parent_info:<15} | {row['goal'] or ''}")

def list_active_sprint_tasks():
    with db_session() as conn:
        sprint = conn.execute("SELECT id, name, goal FROM sprints WHERE status = 'ACTIVE' LIMIT 1").fetchone()
        if not sprint:
            print("No active sprint found.")
            return
        
        print(f"\n🐯 ACTIVE SPRINT: {sprint['name']}")
        print(f"Goal: {sprint['goal']}\n")
    list_entries(category='task', sprint_id=sprint['id'], limit=100)

def list_kanban_board(sprint_id):
    with db_session() as conn:
        sprint = conn.execute("SELECT name, goal FROM sprints WHERE id = ?", (sprint_id,)).fetchone()
        if not sprint:
            print(f"Error: Sprint {sprint_id} not found.")
            return

        tasks = conn.execute("""
            SELECT id, content, status, blocked_by, hours_logged 
            FROM journal 
            WHERE sprint_id = ? AND category = 'task' AND status != 'OBSOLETE'
        """, (sprint_id,)).fetchall()

    columns = {"OPEN": [], "IN_PROGRESS": [], "COMPLETED": []}
    total_hours = 0.0
    for t in tasks:
        s = t['status'].upper() if t['status'] else "OPEN"
        if s in ['COMPLETED', 'DONE', 'FINISHED']:
            status = 'COMPLETED'
        elif s in ['IN_PROGRESS', 'ACTIVE', 'WORKING']:
            status = 'IN_PROGRESS'
        else:
            status = 'OPEN'
        columns[status].append(t)
        if t['hours_logged'] is not None:
            total_hours += t['hours_logged']

    print(f"\n🐯 KANBAN BOARD: {sprint['name']}")
    print(f"Goal: {sprint['goal']}\n")
    if total_hours > 0.0:
        print(f"⏱️ Total Hours Logged in Sprint: {total_hours}h\n")
    
    col_width = 45
    header = f"{'BACKLOG (OPEN)':<{col_width}} | {'ACTIVE (IN_PROGRESS)':<{col_width}} | {'DONE (COMPLETED)':<{col_width}}"
    print(header)
    print("-" * len(header))

    max_rows = max(len(columns["OPEN"]), len(columns["IN_PROGRESS"]), len(columns["COMPLETED"]), 1)
    
    for i in range(max_rows):
        row_str = ""
        for col in ["OPEN", "IN_PROGRESS", "COMPLETED"]:
            if i < len(columns[col]):
                t = columns[col][i]
                block_flag = " [!] " if t['blocked_by'] else " "
                hours_suffix = f" ({t['hours_logged']}h)" if t['hours_logged'] and t['hours_logged'] > 0 else ""
                task_txt = f"#{t['id']}{hours_suffix}{block_flag}{t['content']}"
                if len(task_txt) > col_width - 2:
                    task_txt = task_txt[:col_width-5] + "..."
                row_str += f"{task_txt:<{col_width}} | "
            else:
                row_str += f"{'':<{col_width}} | "
        print(row_str.rstrip(" | "))
    print("-" * len(header))
    print("[!] = Task is Blocked")

def show_task_history(task_id):
    with db_session() as conn:
        task = conn.execute("SELECT content FROM journal WHERE id = ? AND category = 'task'", (task_id,)).fetchone()
        if not task:
            print(f"Error: Task #{task_id} not found.")
            return
        
        print(f"\n📋 Status Transition History for Task #{task_id}: {task['content']}")
        print("-" * 80)
        
        history = conn.execute("""
            SELECT timestamp, from_status, to_status 
            FROM status_history 
            WHERE entry_id = ? 
            ORDER BY timestamp ASC
        """, (task_id,)).fetchall()
        
        if not history:
            print("No transition history recorded yet.")
            return
            
        for h in history:
            from_st = h['from_status'] if h['from_status'] else "None"
            to_st = h['to_status'] if h['to_status'] else "None"
            print(f"🕒 {h['timestamp']} | {from_st} ➔ {to_st}")
        print("-" * 80)

def main():
    parser = argparse.ArgumentParser(description="Journal Database Manager - Command Center v2")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Initialize the database")
    
    # New Hierarchical Aliases
    subparsers.add_parser("sprint:list", help="List all sprints (descending)")
    subparsers.add_parser("task:list", help="List tasks in the active sprint")
    subparsers.add_parser("ideas:list", help="List all recorded ideas")
    
    history_parser = subparsers.add_parser("task:history", help="Show status transition history for a task")
    history_parser.add_argument("task_id", type=int, help="Task ID")

    add_parser = subparsers.add_parser("add", help="Add a new entry")
    add_parser.add_argument("category", choices=["decision", "task", "idea", "learning", "expense"], help="Entry category")
    add_parser.add_argument("content", help="Entry content")
    add_parser.add_argument("--status", default="OPEN", help="Entry status (e.g., OPEN, IN_PROGRESS, COMPLETED)")
    add_parser.add_argument("--due", help="Due date (YYYY-MM-DD)")
    add_parser.add_argument("--parent", type=int, help="Parent entry ID")
    add_parser.add_argument("--sprint", type=int, help="Sprint ID")
    add_parser.add_argument("--success", help="Success criteria / Definition of Done")
    add_parser.add_argument("--blocked-by", type=int, help="ID of task blocking this one")
    add_parser.add_argument("--doc", help="Path to associated documentation file")
    add_parser.add_argument("--amount", type=float, help="Expense amount")
    add_parser.add_argument("--currency", default="USD", help="Expense currency")
    add_parser.add_argument("--hours", type=float, default=0.0, help="Work hours logged on the task")

    link_parser = subparsers.add_parser("link", help="Link a child entry to a parent")
    link_parser.add_argument("child_id", type=int, help="Child entry ID")
    link_parser.add_argument("parent_id", type=int, help="Parent entry ID")

    update_parser = subparsers.add_parser("update", help="Update an existing entry")
    update_parser.add_argument("entry_id", type=str, help="Entry ID(s) to update (comma-separated for bulk)")
    update_parser.add_argument("--status", help="New status")
    update_parser.add_argument("--due", type=str_or_clear, help="New due date (YYYY-MM-DD) or 'clear'")
    update_parser.add_argument("--parent", type=int_or_clear, help="New parent entry ID or 'clear'")
    update_parser.add_argument("--sprint", type=int_or_clear, help="New sprint ID or 'clear'")
    update_parser.add_argument("--success", type=str_or_clear, help="New success criteria or 'clear'")
    update_parser.add_argument("--blocked-by", type=int_or_clear, help="New blocker ID or 'clear'")
    update_parser.add_argument("--doc", type=str_or_clear, help="New documentation link or 'clear'")
    update_parser.add_argument("--content", help="New entry description content")
    update_parser.add_argument("--amount", type=float_or_clear, help="New expense amount or 'clear'")
    update_parser.add_argument("--currency", type=str_or_clear, help="New expense currency or 'clear'")
    update_parser.add_argument("--hours", type=float_or_clear, help="New logged work hours or 'clear'")

    archive_parser = subparsers.add_parser("archive", help="Archive an entry (soft-delete)")
    archive_parser.add_argument("id", type=int, help="Entry ID to archive")

    list_parser = subparsers.add_parser("list", help="List entries")
    list_parser.add_argument("--category", choices=["decision", "task", "idea", "learning", "expense"], help="Filter by category")
    list_parser.add_argument("--limit", type=int, default=10, help="Limit number of entries")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.add_argument("--parent", type=int, help="Filter by parent ID")
    list_parser.add_argument("--sprint", type=int, help="Filter by sprint ID")

    # Sprint Commands
    sprint_parser = subparsers.add_parser("sprint", help="Manage sprints")
    sprint_subparsers = sprint_parser.add_subparsers(dest="sprint_command")

    sprint_add_parser = sprint_subparsers.add_parser("add", help="Add a new sprint")
    sprint_add_parser.add_argument("name", help="Sprint name")
    sprint_add_parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    sprint_add_parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    sprint_add_parser.add_argument("--goal", help="Sprint goal")
    sprint_add_parser.add_argument("--parent", type=int, help="Parent sprint ID")

    sprint_update_parser = sprint_subparsers.add_parser("update", help="Update a sprint")
    sprint_update_parser.add_argument("id", type=int, help="Sprint ID")
    sprint_update_parser.add_argument("--name", help="New name")
    sprint_update_parser.add_argument("--start", type=str_or_clear, help="New start date (YYYY-MM-DD) or 'clear'")
    sprint_update_parser.add_argument("--end", type=str_or_clear, help="New end date (YYYY-MM-DD) or 'clear'")
    sprint_update_parser.add_argument("--goal", type=str_or_clear, help="New goal or 'clear'")
    sprint_update_parser.add_argument("--status", choices=["PLANNING", "ACTIVE", "COMPLETED"], help="New status")
    sprint_update_parser.add_argument("--parent", type=int_or_clear, help="New parent sprint ID or 'clear'")

    sprint_list_parser = sprint_subparsers.add_parser("list", help="List sprints")
    sprint_list_parser.add_argument("--status", choices=["PLANNING", "ACTIVE", "COMPLETED"], help="Filter by status")

    sprint_board_parser = sprint_subparsers.add_parser("board", help="View sprint kanban board")
    sprint_board_parser.add_argument("id", type=int, help="Sprint ID")

    args = parser.parse_args()

    if args.command == "init":
        init_db()
    elif args.command == "sprint:list":
        list_sprints()
    elif args.command == "task:list":
        list_active_sprint_tasks()
    elif args.command == "ideas:list":
        list_entries(category="idea", limit=50)
    elif args.command == "task:history":
        show_task_history(args.task_id)
    elif args.command == "add":
        add_entry(args.category, args.content, args.status, args.due, args.parent, args.sprint, args.success, args.blocked_by, args.doc, args.amount, args.currency, args.hours)
    elif args.command == "link":
        link_entries(args.child_id, args.parent_id)
    elif args.command == "update":
        update_entry(args.entry_id, args.status, args.due, args.parent, args.sprint, args.success, args.blocked_by, args.doc, args.content, args.amount, args.currency, args.hours)
    elif args.command == "archive":
        archive_entry(args.id)
    elif args.command == "list":
        list_entries(args.category, args.limit, args.status, args.parent, args.sprint)
    elif args.command == "sprint":
        if args.sprint_command == "add":
            add_sprint(args.name, args.start, args.end, args.goal, args.parent)
        elif args.sprint_command == "update":
            update_sprint(args.id, args.name, args.start, args.end, args.goal, args.status, args.parent)
        elif args.sprint_command == "list":
            list_sprints(args.status)
        elif args.sprint_command == "board":
            list_kanban_board(args.id)
        else:
            sprint_parser.print_help()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
