CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    total_passes INTEGER DEFAULT 0,
    total_time_out INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS passes (
    pass_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    pass_taken_at TEXT NOT NULL,
    return_time TEXT,
    duration_minutes INTEGER NOT NULL,
    returned INTEGER DEFAULT 0,
    FOREIGN KEY (student_id) REFERENCES students (student_id)
);

CREATE TABLE IF NOT EXISTS settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    description TEXT
);