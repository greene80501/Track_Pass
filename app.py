# app.py
from flask import Flask, request, redirect, url_for, render_template, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import os
import csv
import database
import printer_handler
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "a-very-secret-and-secure-key-for-kiosk"

# --- Database Setup ---
db_con = database.create_connection()
db_cur = database.create_cursor(db_con)
database.init_database(db_cur)
# --------------------

# --- Admin User File ---
USER_FILE = "users.csv"
if not os.path.exists(USER_FILE):
    with open(USER_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        # Default password is "password123"
        hashed_pw = generate_password_hash("password123")
        writer.writerow(["admin", hashed_pw])
        print("Created default user: admin / password123")
# --------------------

### KIOSK ROUTES ###

@app.route("/")
def kiosk_home():
    """Renders the main kiosk interface."""
    return render_template("kiosk.html")

@app.route("/start_pass", methods=["POST"])
def start_pass():
    """Handles the creation of a new pass."""
    student_id = request.form.get("student_id")
    if not student_id or not student_id.isdigit():
        return jsonify({"success": False, "message": "Invalid Student ID format. Must be numeric."}), 400

    student = database.get_student_by_id(db_cur, student_id)
    if not student:
        return jsonify({"success": False, "message": "Student ID not found."}), 404

    pass_id = database.create_pass_now(db_cur, student_id, intended_duration_minutes=10)
    database.save_data(db_con)

    if pass_id:
        # Call the printer handler to print the slip
        printer_handler.print_pass_slip(
            student_name=student["Name"],
            student_id=student_id,
            pass_id=pass_id,
            duration_minutes=10
        )
        return jsonify({"success": True, "message": f"Pass #{pass_id} started for {student['Name']}."})
    else:
        return jsonify({"success": False, "message": "Failed to create pass in database."}), 500

@app.route("/return_pass", methods=["POST"])
def return_pass():
    """Endpoint for the scanner handler to return a pass by PASS ID."""
    pass_id = request.form.get("pass_id")
    if not pass_id or not pass_id.isdigit():
        return "Invalid Pass ID format.", 400
    
    returned_pass = database.return_pass_by_id(db_cur, int(pass_id))
    database.save_data(db_con)
    
    if returned_pass:
        return f"Pass {pass_id} returned successfully.", 200
    else:
        return f"Pass {pass_id} not found or already returned.", 404

@app.route("/return_by_student_id", methods=["POST"])
def return_by_student_id():
    """Handles returning from a pass by typing in a STUDENT ID."""
    student_id = request.form.get("student_id")
    if not student_id or not student_id.isdigit():
        return jsonify({"success": False, "message": "Invalid Student ID format. Must be numeric."}), 400

    student = database.get_student_by_id(db_cur, student_id)
    if not student:
        return jsonify({"success": False, "message": "Student ID not found."}), 404

    returned_pass = database.return_active_pass_for_student(db_cur, student_id)
    database.save_data(db_con)

    if returned_pass:
        return jsonify({"success": True, "message": f"Welcome back, {student['Name']}!"})
    else:
        return jsonify({"success": False, "message": "No active pass found to return."}), 404


### API FOR DYNAMIC UI ###
@app.route("/api/active_passes")
def get_active_passes_api():
    """Provides a JSON list of active passes for the kiosk UI."""
    active_passes = database.get_active_passes(db_cur)
    
    now = datetime.now()
    for p in active_passes:
        taken_at = datetime.fromisoformat(p["pass_taken_at"])
        end_time = taken_at + timedelta(minutes=p["duration_minutes"])
        time_remaining = int((end_time - now).total_seconds())
        p["time_remaining"] = time_remaining
        p["full_name"] = f"{p['first_name']} {p['last_name']}"

    return jsonify(active_passes)


### ADMIN ROUTES ###

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        users = {}
        with open(USER_FILE, newline="") as f:
            reader = csv.reader(f)
            users = {row[0]: row[1] for row in reader if len(row) == 2}

        if username in users and check_password_hash(users[username], password):
            session["admin_user"] = username
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials.", "error")
    
    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin_user" not in session:
        return redirect(url_for("admin_login"))
    
    try:
        # Get all students for the view
        students = database.get_all_students(db_cur)
        
        # Get recent pass history with additional details
        passes = database.get_recent_passes_with_details(db_cur, limit=100)
        
        # Get system settings
        settings = database.get_all_settings(db_cur)
        
        # Get current capacity info
        active_count = database.get_active_pass_count(db_cur)
        max_capacity = int(database.get_setting(db_cur, 'max_students_out', '10'))
        
        return render_template("admin_dashboard.html", 
                             students=students, 
                             passes=passes, 
                             settings=settings,
                             active_count=active_count,
                             max_capacity=max_capacity)
    except Exception as e:
        print(f"Error in admin_dashboard: {e}")
        return render_template("admin_dashboard.html", students=[], passes=[], settings={})


@app.route("/admin/update_settings", methods=["POST"])
def admin_update_settings():
    if "admin_user" not in session:
        return redirect(url_for("admin_login"))
    
    try:
        max_students = request.form.get("max_students_out", "10").strip()
        default_duration = request.form.get("default_pass_duration", "10").strip()
        enable_limit = "1" if request.form.get("enable_capacity_limit") == "on" else "0"
        
        # Validate inputs
        if not max_students.isdigit() or int(max_students) < 1 or int(max_students) > 100:
            flash("Maximum students must be a number between 1 and 100.", "error")
            return redirect(url_for("admin_dashboard"))
        
        if not default_duration.isdigit() or int(default_duration) < 1 or int(default_duration) > 60:
            flash("Default duration must be a number between 1 and 60 minutes.", "error")
            return redirect(url_for("admin_dashboard"))
        
        # Update settings
        database.update_setting(db_cur, "max_students_out", max_students)
        database.update_setting(db_cur, "default_pass_duration", default_duration)
        database.update_setting(db_cur, "enable_capacity_limit", enable_limit)
        
        database.save_data(db_con)
        
        capacity_status = "enabled" if enable_limit == "1" else "disabled"
        flash(f"Settings updated: Max capacity {max_students}, Default duration {default_duration} minutes, Capacity limit {capacity_status}.", "success")
        
    except Exception as e:
        flash(f"Error updating settings: {e}", "error")
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/add_student", methods=["POST"])
def admin_add_student():
    if "admin_user" not in session:
        return redirect(url_for("admin_login"))
    
    student_number = request.form.get("student_number", "").strip()
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    
    if not student_number or not first_name or not last_name:
        flash("All fields are required.", "error")
        return redirect(url_for("admin_dashboard"))
    
    if not student_number.isdigit():
        flash("Student number must be numeric.", "error")
        return redirect(url_for("admin_dashboard"))
    
    # Check if student already exists
    existing_student = database.get_student_by_id(db_cur, student_number)
    if existing_student:
        flash(f"Student with ID {student_number} already exists.", "error")
        return redirect(url_for("admin_dashboard"))
    
    try:
        database.insert_student(db_cur, student_number, first_name, last_name)
        database.save_data(db_con)
        flash(f"Successfully added {first_name} {last_name} (ID: {student_number}).", "success")
    except Exception as e:
        flash(f"Error adding student: {e}", "error")
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete_student", methods=["POST"])
def admin_delete_student():
    if "admin_user" not in session:
        return redirect(url_for("admin_login"))
    
    student_id = request.form.get("student_id")
    if not student_id:
        flash("Invalid student ID.", "error")
        return redirect(url_for("admin_dashboard"))
    
    try:
        # Try enhanced function first
        if hasattr(database, 'delete_student_by_id'):
            success = database.delete_student_by_id(db_cur, student_id)
            database.save_data(db_con)
            
            if success:
                flash(f"Successfully deleted student {student_id} and all their pass history.", "success")
            else:
                flash(f"Student {student_id} not found.", "error")
        else:
            # Fallback to basic deletion
            flash("Delete function not available in current database version.", "error")
    except Exception as e:
        flash(f"Error deleting student: {e}", "error")
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/force_return", methods=["POST"])
def admin_force_return():
    if "admin_user" not in session:
        return redirect(url_for("admin_login"))
    
    pass_id = request.form.get("pass_id")
    if not pass_id or not pass_id.isdigit():
        flash("Invalid pass ID.", "error")
        return redirect(url_for("admin_dashboard"))
    
    try:
        returned_pass = database.return_pass_by_id(db_cur, int(pass_id))
        database.save_data(db_con)
        
        if returned_pass:
            flash(f"Successfully force-returned pass {pass_id}.", "success")
        else:
            flash(f"Pass {pass_id} not found or already returned.", "error")
    except Exception as e:
        flash(f"Error returning pass: {e}", "error")
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/upload", methods=["POST"])
def admin_upload():
    if "admin_user" not in session:
        return redirect(url_for("admin_login"))
    
    if "file" not in request.files or request.files["file"].filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("admin_dashboard"))
    
    file = request.files["file"]
    if not file.filename.lower().endswith(".csv"):
        flash("Invalid file type. Please upload a CSV.", "error")
        return redirect(url_for("admin_dashboard"))

    # Check if user wants to update existing students
    update_existing = request.form.get("update_existing") == "on"

    try:
        # Process the CSV file
        content = file.stream.read().decode("utf-8")
        reader = csv.reader(content.splitlines())
        
        # Find the correct columns from the header
        header = next(reader)
        try:
            header_map = {h.strip().lower(): i for i, h in enumerate(header)}
            
            # Look for Student Number column
            id_col = None
            for key in ['student number', 'student_number', 'studentnumber', 'id']:
                if key in header_map:
                    id_col = header_map[key]
                    break
            
            # Look for First Name column  
            first_name_col = None
            for key in ['first name', 'first_name', 'firstname']:
                if key in header_map:
                    first_name_col = header_map[key]
                    break
                    
            # Look for Last Name column
            last_name_col = None
            for key in ['last name', 'last_name', 'lastname']:
                if key in header_map:
                    last_name_col = header_map[key]
                    break
            
            if id_col is None or first_name_col is None or last_name_col is None:
                missing = []
                if id_col is None: missing.append("Student Number")
                if first_name_col is None: missing.append("First Name") 
                if last_name_col is None: missing.append("Last Name")
                flash(f"Missing required columns: {', '.join(missing)}. Found columns: {', '.join(header)}", "error")
                return redirect(url_for("admin_dashboard"))
                
        except (StopIteration) as e:
            flash(f"Error reading CSV header: {e}", "error")
            return redirect(url_for("admin_dashboard"))

        # Collect student data for processing
        students_data = []
        row_errors = []
        
        for i, row in enumerate(reader, start=2):
            if len(row) > max(id_col, first_name_col, last_name_col):
                student_id = row[id_col].strip()
                first_name = row[first_name_col].strip()
                last_name = row[last_name_col].strip()

                if not student_id or not first_name or not last_name:
                    row_errors.append(f"Row {i}: missing required data")
                    continue

                if not student_id.isdigit():
                    row_errors.append(f"Row {i}: student ID '{student_id}' must be numeric")
                    continue

                students_data.append((student_id, first_name, last_name))
            else:
                row_errors.append(f"Row {i}: not enough columns")

        if not students_data:
            flash("No valid student data found in the CSV file.", "error")
            return redirect(url_for("admin_dashboard"))

        # Process the students using the new additive function
        summary = database.add_or_update_students_from_csv_data(
            db_cur, students_data, update_existing
        )
        
        # Save changes
        database.save_data(db_con)
        
        # Prepare success message
        messages = []
        if summary['added'] > 0:
            messages.append(f"Added {summary['added']} new students")
        if summary['updated'] > 0:
            messages.append(f"Updated {summary['updated']} existing students")
        if summary['skipped'] > 0:
            messages.append(f"Skipped {summary['skipped']} existing students")
        
        if messages:
            flash(f"CSV processed successfully: {', '.join(messages)}.", "success")
        
        # Show detailed information if there were skipped students
        if summary['skipped_students'] and not update_existing:
            flash(f"Skipped existing students: {', '.join(summary['skipped_students'][:5])}" + 
                  (f" and {len(summary['skipped_students']) - 5} more" if len(summary['skipped_students']) > 5 else ""), 
                  "warning")
        
        # Show updated students if any
        if summary['updated_students']:
            flash(f"Updated students: {', '.join(summary['updated_students'][:5])}" + 
                  (f" and {len(summary['updated_students']) - 5} more" if len(summary['updated_students']) > 5 else ""), 
                  "success")
        
        # Show row errors if any
        if row_errors:
            flash("Some rows could not be processed:", "warning")
            for error in row_errors[:5]:  # Show first 5 errors
                flash(error, "error")
            if len(row_errors) > 5:
                flash(f"... and {len(row_errors) - 5} more errors", "error")
        
        # Show processing errors if any
        if summary['errors']:
            flash("Some students could not be processed:", "warning")
            for error in summary['errors'][:5]:  # Show first 5 errors
                flash(error, "error")
            if len(summary['errors']) > 5:
                flash(f"... and {len(summary['errors']) - 5} more errors", "error")

    except Exception as e:
        flash(f"A critical error occurred while processing the file: {e}", "error")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/force_return_all", methods=["POST"])
def admin_force_return_all():
    if "admin_user" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    try:
        # Get all active passes
        active_passes = database.get_active_passes(db_cur)
        
        if not active_passes:
            return jsonify({"success": True, "message": "No active passes to return."})
        
        returned_count = 0
        errors = []
        
        for pass_info in active_passes:
            try:
                returned_pass = database.return_pass_by_id(db_cur, pass_info['pass_id'])
                if returned_pass:
                    returned_count += 1
                else:
                    errors.append(f"Failed to return pass {pass_info['pass_id']}")
            except Exception as e:
                errors.append(f"Error returning pass {pass_info['pass_id']}: {str(e)}")
        
        database.save_data(db_con)
        
        if returned_count > 0:
            message = f"Successfully returned {returned_count} active passes."
            if errors:
                message += f" {len(errors)} errors occurred."
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "message": "No passes were returned successfully."})
            
    except Exception as e:
        return jsonify({"success": False, "message": f"Error during bulk return: {str(e)}"})


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_user", None)
    return redirect(url_for("admin_login"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)