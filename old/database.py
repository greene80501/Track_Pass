# database.py
import sqlite3
from datetime import datetime

def init_database(cursor: sqlite3.Cursor, file_source: str = "./create_empty.sql") -> None:
    with open(file_source, 'r') as f:
        create_sql = f.read()
    try:
        cursor.executescript(create_sql)
    except Exception:
        print("Database already exists.")

def create_connection() -> sqlite3.Connection:
    # Enable row access by name
    con = sqlite3.connect("school_passes.db")
    con.row_factory = sqlite3.Row
    return con

def create_cursor(connection: sqlite3.Connection) -> sqlite3.Cursor:
    return connection.cursor()

def insert_student(cursor: sqlite3.Cursor, student_id: str, first_name: str, last_name: str,
                   total_passes: int = 0, total_time_out: int = 0) -> None:
    if len(student_id) != 6:
        raise ValueError(f"Student ID should be 6 characters long, not {len(student_id)}")
    cursor.execute(
        "INSERT INTO students (student_id, first_name, last_name, total_passes, total_time_out) "
        "VALUES (?, ?, ?, ?, ?)",
        (student_id, first_name, last_name, total_passes, total_time_out)
    )

def add_to_student_time_out(cursor: sqlite3.Cursor, student_id: str, time_addition_seconds: int) -> None:
    if len(student_id) != 6:
        raise ValueError(f"Student ID should be 6 characters long, not {len(student_id)}")
    cursor.execute(
        "UPDATE students SET total_time_out = total_time_out + ? WHERE student_id = ?",
        (time_addition_seconds, student_id)
    )

def increment_student_pass_number(cursor: sqlite3.Cursor, student_id: str) -> None:
    if len(student_id) != 6:
        raise ValueError(f"Student ID should be 6 characters long, not {len(student_id)}")
    cursor.execute(
        "UPDATE students SET total_passes = total_passes + 1 WHERE student_id = ?",
        (student_id,)
    )

def get_student_by_id(cursor: sqlite3.Cursor, student_id: str) -> dict | None:
    row = cursor.execute(
        "SELECT student_id, first_name, last_name, total_passes, total_time_out "
        "FROM students WHERE student_id = ?",
        (student_id,)
    ).fetchone()
    if row is None:
        return None
    return {
        "Name": f"{row['first_name']} {row['last_name']}",
        "Number Of Passes": row["total_passes"],
        "Total Time Out": row["total_time_out"],
    }

def get_number_of_overtime_passes_by_student_id(cursor: sqlite3.Cursor, student_id: str) -> int:
    # OT = returned and (return_time - pass_taken_at) > duration_minutes
    row = cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM passes
        WHERE student_id = ?
          AND returned = 1
          AND (
              (julianday(return_time) - julianday(pass_taken_at)) * 24.0 * 60.0
          ) > duration_minutes
        """,
        (student_id,)
    ).fetchone()
    return row["cnt"] if row else 0

def create_pass_now(cursor: sqlite3.Cursor, student_id: str, intended_duration_minutes: int = 10) -> int | None:
    if len(student_id) != 6:
        raise ValueError(f"Student ID should be 6 characters long, not {len(student_id)}")
    try:
        cursor.execute(
            "INSERT INTO passes (student_id, pass_taken_at, duration_minutes, returned) "
            "VALUES (?, ?, ?, 0)",
            (student_id, datetime.now().isoformat(sep=' ', timespec='seconds'), intended_duration_minutes)
        )
        return cursor.lastrowid
    except Exception as e:
        print(f"Unable to create new pass: {e}")
        return None

def populate_pass(cursor: sqlite3.Cursor, pass_id: int, returned: bool = True,
                  return_time: datetime | None = None) -> None:
    rt = (return_time or datetime.now()).isoformat(sep=' ', timespec='seconds')
    cursor.execute(
        "UPDATE passes SET returned = ?, return_time = ? WHERE pass_id = ?",
        (1 if returned else 0, rt, pass_id)
    )

def get_passes_for_student(cursor: sqlite3.Cursor, student_id: str) -> list[dict]:
    rows = cursor.execute(
        "SELECT pass_id, pass_taken_at, return_time, duration_minutes, returned "
        "FROM passes WHERE student_id = ? ORDER BY pass_taken_at ASC",
        (student_id,)
    ).fetchall()
    # Convert to simple dicts if you like
    return [dict(r) for r in rows]

def save_data(connection: sqlite3.Connection) -> None:
    connection.commit()
