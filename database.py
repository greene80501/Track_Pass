# database.py
import sqlite3
from datetime import datetime

def init_database(cursor: sqlite3.Cursor, file_source: str = "./create_empty.sql") -> None:
    with open(file_source, 'r') as f:
        create_sql = f.read()
    try:
        cursor.executescript(create_sql)
        print("Database initialized.")
        
        # Initialize default settings if they don't exist
        init_default_settings(cursor)
        
    except Exception:
        print("Database already exists.")
        # Still try to add settings table if it doesn't exist
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL,
                    description TEXT
                )
            """)
            init_default_settings(cursor)
        except Exception as e:
            print(f"Error initializing settings: {e}")

def init_default_settings(cursor: sqlite3.Cursor) -> None:
    """Initialize default system settings."""
    default_settings = [
        ('max_students_out', '10', 'Maximum number of students allowed out at once'),
        ('default_pass_duration', '10', 'Default pass duration in minutes'),
        ('enable_capacity_limit', '1', 'Whether to enforce the maximum capacity limit (1=enabled, 0=disabled)')
    ]
    
    for key, value, description in default_settings:
        cursor.execute(
            "INSERT OR IGNORE INTO settings (setting_key, setting_value, description) VALUES (?, ?, ?)",
            (key, value, description)
        )

def get_setting(cursor: sqlite3.Cursor, setting_key: str, default_value: str = None) -> str:
    """Get a setting value from the database."""
    result = cursor.execute(
        "SELECT setting_value FROM settings WHERE setting_key = ?",
        (setting_key,)
    ).fetchone()
    
    if result:
        return result['setting_value']
    return default_value

def update_setting(cursor: sqlite3.Cursor, setting_key: str, setting_value: str) -> bool:
    """Update a setting in the database."""
    try:
        cursor.execute(
            "UPDATE settings SET setting_value = ? WHERE setting_key = ?",
            (setting_value, setting_key)
        )
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error updating setting {setting_key}: {e}")
        return False

def get_all_settings(cursor: sqlite3.Cursor) -> dict:
    """Get all settings as a dictionary."""
    rows = cursor.execute(
        "SELECT setting_key, setting_value, description FROM settings"
    ).fetchall()
    
    return {row['setting_key']: {
        'value': row['setting_value'],
        'description': row['description']
    } for row in rows}

def get_active_pass_count(cursor: sqlite3.Cursor) -> int:
    """Get the current number of active passes."""
    result = cursor.execute(
        "SELECT COUNT(*) as count FROM passes WHERE returned = 0"
    ).fetchone()
    
    return result['count'] if result else 0

def can_create_new_pass(cursor: sqlite3.Cursor) -> tuple[bool, str]:
    """
    Check if a new pass can be created based on capacity limits.
    Returns (can_create, reason_if_not)
    """
    # Check if capacity limit is enabled
    limit_enabled = get_setting(cursor, 'enable_capacity_limit', '1') == '1'
    
    if not limit_enabled:
        return True, ""
    
    # Get current active count and max limit
    active_count = get_active_pass_count(cursor)
    max_allowed = int(get_setting(cursor, 'max_students_out', '10'))
    
    if active_count >= max_allowed:
        return False, f"Maximum capacity reached ({active_count}/{max_allowed} students currently out)"
    
    return True, ""

def create_connection() -> sqlite3.Connection:
    con = sqlite3.connect("school_passes.db", check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def create_cursor(connection: sqlite3.Connection) -> sqlite3.Cursor:
    return connection.cursor()

def insert_student(cursor: sqlite3.Cursor, student_id: str, first_name: str, last_name: str,
                   total_passes: int = 0, total_time_out: int = 0) -> None:
    # Ensure student_id is treated as text, but validate its content if needed
    if not student_id.isdigit() or len(student_id) > 10: # More flexible length
         # We can choose to raise an error or just log a warning
         print(f"Warning: Student ID '{student_id}' may not be in the standard format.")
    cursor.execute(
        "INSERT INTO students (student_id, first_name, last_name, total_passes, total_time_out) "
        "VALUES (?, ?, ?, ?, ?)",
        (student_id, first_name, last_name, total_passes, total_time_out)
    )

def delete_all_students(cursor: sqlite3.Cursor) -> None:
    """
    Deletes all passes and all students from the database.
    This provides a clean slate for a new import.
    """
    # We must delete from 'passes' first because it has a foreign key
    # reference to the 'students' table.
    cursor.execute("DELETE FROM passes")
    cursor.execute("DELETE FROM students")
    print("All existing student and pass records have been deleted.")

def delete_student_by_id(cursor: sqlite3.Cursor, student_id: str) -> bool:
    """
    Deletes a specific student and all their passes.
    Returns True if student was found and deleted, False otherwise.
    """
    # First check if student exists
    student = cursor.execute(
        "SELECT student_id FROM students WHERE student_id = ?",
        (student_id,)
    ).fetchone()
    
    if not student:
        return False
    
    # Delete passes first (foreign key constraint)
    cursor.execute("DELETE FROM passes WHERE student_id = ?", (student_id,))
    
    # Then delete the student
    cursor.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
    
    return True

def get_student_by_id(cursor: sqlite3.Cursor, student_id: str) -> dict | None:
    row = cursor.execute(
        "SELECT student_id, first_name, last_name, total_passes, total_time_out "
        "FROM students WHERE student_id = ?",
        (student_id,)
    ).fetchone()
    if row is None:
        return None
    return {
        "student_id": row["student_id"],
        "Name": f"{row['first_name']} {row['last_name']}",
        "Number Of Passes": row["total_passes"],
        "Total Time Out": row["total_time_out"],
    }

def get_all_students(cursor: sqlite3.Cursor) -> list[dict]:
    """
    Returns all students in the database.
    """
    rows = cursor.execute(
        "SELECT student_id, first_name, last_name, total_passes, total_time_out "
        "FROM students ORDER BY last_name, first_name"
    ).fetchall()
    return [dict(row) for row in rows]

def create_pass_now(cursor: sqlite3.Cursor, student_id: str, intended_duration_minutes: int = None) -> tuple[int | None, str]:
    """
    Create a new pass if capacity allows.
    Returns (pass_id, error_message)
    """
    try:
        # Check capacity first
        can_create, reason = can_create_new_pass(cursor)
        if not can_create:
            return None, reason
        
        # Use default duration if not specified
        if intended_duration_minutes is None:
            intended_duration_minutes = int(get_setting(cursor, 'default_pass_duration', '10'))
        
        cursor.execute(
            "INSERT INTO passes (student_id, pass_taken_at, duration_minutes, returned) "
            "VALUES (?, ?, ?, 0)",
            (student_id, datetime.now().isoformat(sep=' ', timespec='seconds'), intended_duration_minutes)
        )
        return cursor.lastrowid, ""
    except Exception as e:
        return None, f"Unable to create new pass: {e}"

def return_pass_by_id(cursor: sqlite3.Cursor, pass_id: int) -> dict | None:
    """Marks a pass as returned and returns the pass details."""
    rt = datetime.now().isoformat(sep=' ', timespec='seconds')
    
    # First, get the pass details to calculate time out
    pass_row = cursor.execute(
        "SELECT student_id, pass_taken_at, duration_minutes FROM passes WHERE pass_id = ? AND returned = 0",
        (pass_id,)
    ).fetchone()

    if not pass_row:
        return None # Pass already returned or does not exist

    # Mark the pass as returned
    cursor.execute(
        "UPDATE passes SET returned = 1, return_time = ? WHERE pass_id = ?",
        (rt, pass_id)
    )
    
    # Update student aggregates
    student_id = pass_row['student_id']
    start_time = datetime.fromisoformat(pass_row['pass_taken_at'])
    end_time = datetime.fromisoformat(rt)
    time_out_seconds = int((end_time - start_time).total_seconds())

    cursor.execute(
        "UPDATE students SET total_time_out = total_time_out + ?, total_passes = total_passes + 1 WHERE student_id = ?",
        (time_out_seconds, student_id)
    )
    
    return dict(pass_row)

def return_active_pass_for_student(cursor: sqlite3.Cursor, student_id: str) -> dict | None:
    """Finds the single active pass for a student and marks it as returned."""
    # First, find the pass_id of the one pass that is not returned for this student
    active_pass_row = cursor.execute(
        "SELECT pass_id FROM passes WHERE student_id = ? AND returned = 0 ORDER BY pass_taken_at DESC LIMIT 1",
        (student_id,)
    ).fetchone()

    if not active_pass_row:
        return None # No active pass found for this student

    # Now that we have the pass_id, we can reuse our existing return logic
    pass_id_to_return = active_pass_row['pass_id']
    return return_pass_by_id(cursor, pass_id_to_return)

def get_active_passes(cursor: sqlite3.Cursor) -> list[dict]:
    """Gets all passes that have not been returned."""
    rows = cursor.execute(
        """
        SELECT p.pass_id, p.student_id, p.pass_taken_at, p.duration_minutes, s.first_name, s.last_name
        FROM passes p
        JOIN students s ON p.student_id = s.student_id
        WHERE p.returned = 0
        ORDER BY p.pass_taken_at ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]

def get_recent_passes_with_details(cursor: sqlite3.Cursor, limit: int = 50) -> list[dict]:
    """
    Gets recent passes with additional details for admin dashboard.
    """
    rows = cursor.execute(
        """
        SELECT 
            p.pass_id, 
            p.student_id,
            p.pass_taken_at, 
            p.return_time,
            p.duration_minutes, 
            p.returned,
            s.first_name, 
            s.last_name
        FROM passes p
        JOIN students s ON p.student_id = s.student_id
        ORDER BY p.pass_taken_at DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()
    
    passes = []
    now = datetime.now()
    
    for row in rows:
        pass_dict = dict(row)
        
        # Calculate time out information
        start_time = datetime.fromisoformat(row['pass_taken_at'])
        
        if row['returned']:
            # Completed pass - calculate actual time out
            end_time = datetime.fromisoformat(row['return_time'])
            actual_seconds = int((end_time - start_time).total_seconds())
            pass_dict['actual_time_out'] = f"{actual_seconds // 60}m {actual_seconds % 60}s"
        else:
            # Active pass - calculate current time out
            current_seconds = int((now - start_time).total_seconds())
            pass_dict['current_time_out'] = f"{current_seconds // 60}m {current_seconds % 60}s"
        
        passes.append(pass_dict)
    
    return passes

def add_or_update_students_from_csv_data(cursor: sqlite3.Cursor, students_data: list, update_existing: bool = False) -> dict:
    """
    Adds new students and optionally updates existing ones from CSV data.
    
    Args:
        cursor: Database cursor
        students_data: List of tuples [(student_id, first_name, last_name), ...]
        update_existing: Whether to update existing students' names
    
    Returns:
        dict: Summary with counts of added, updated, skipped, and errors
    """
    summary = {
        'added': 0,
        'updated': 0,
        'skipped': 0,
        'errors': [],
        'skipped_students': [],
        'updated_students': []
    }
    
    for student_id, first_name, last_name in students_data:
        try:
            # Check if student already exists
            existing_student = get_student_by_id(cursor, student_id)
            
            if existing_student:
                if update_existing:
                    # Update existing student
                    if update_existing_student(cursor, student_id, first_name, last_name):
                        summary['updated'] += 1
                        summary['updated_students'].append(f"{student_id} ({first_name} {last_name})")
                    else:
                        summary['errors'].append(f"Failed to update {student_id} ({first_name} {last_name})")
                else:
                    # Skip existing student
                    summary['skipped'] += 1
                    summary['skipped_students'].append(f"{student_id} ({first_name} {last_name})")
            else:
                # Add new student
                insert_student(cursor, student_id, first_name, last_name)
                summary['added'] += 1
                
        except Exception as e:
            summary['errors'].append(f"Error processing {student_id} ({first_name} {last_name}): {str(e)}")
    
    return summary

def update_existing_student(cursor: sqlite3.Cursor, student_id: str, first_name: str, last_name: str) -> bool:
    """
    Updates an existing student's name information.
    Returns True if student was found and updated, False otherwise.
    """
    try:
        # Check if student exists
        existing_student = get_student_by_id(cursor, student_id)
        if not existing_student:
            return False
        
        # Update the student's information
        cursor.execute(
            "UPDATE students SET first_name = ?, last_name = ? WHERE student_id = ?",
            (first_name, last_name, student_id)
        )
        return True
        
    except Exception as e:
        print(f"Error updating student {student_id}: {e}")
        return False

def save_data(connection: sqlite3.Connection) -> None:
    connection.commit()