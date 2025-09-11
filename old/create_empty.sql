-- Create students table
CREATE TABLE students (
    student_id CHAR(6) PRIMARY KEY, -- unique 6-digit student number
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    total_passes INT DEFAULT 0,
    total_time_out INT DEFAULT 0 -- store total minutes out of classroom
);

-- Create passes table
CREATE TABLE passes (
    pass_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id CHAR(6),
    pass_taken_at DATETIME NOT NULL, -- when pass was taken
    duration_minutes INT NOT NULL, -- intended time out
    returned BOOLEAN DEFAULT FALSE, -- whether student returned
    return_time DATETIME, -- actual return time (if returned)
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);
