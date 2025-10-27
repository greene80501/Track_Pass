# app.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
from datetime import datetime
import database
import printer_handler

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this!

# Create connection once
db_con = database.create_connection()
db_cur = database.create_cursor(db_con)
database.init_database(db_cur)
database.save_data(db_con)

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('kiosk.html')

@app.route('/start_pass', methods=['POST'])
def start_pass():
    student_id = request.form.get('student_id', '').strip()
    
    if not student_id:
        return jsonify({'success': False, 'message': 'Please enter a Student ID'})
    
    # Create new cursor for this request
    cur = database.create_cursor(db_con)
    student = database.get_student_by_id(cur, student_id)
    
    if not student:
        return jsonify({'success': False, 'message': f'Student ID {student_id} not found in system'})
    
    pass_id, error = database.create_pass_now(cur, student_id)
    
    if error:
        return jsonify({'success': False, 'message': error})
    
    database.save_data(db_con)
    
    try:
        printer_handler.print_pass_slip(
            student_name=student['Name'],
            student_id=student_id,
            pass_id=pass_id,
            duration_minutes=10
        )
    except Exception as e:
        print(f"[WARN] Printer error: {e}")
    
    return jsonify({'success': True, 'message': f'{student["Name"]} signed out successfully!'})

@app.route('/return_by_student_id', methods=['POST'])
def return_by_student_id():
    student_id = request.form.get('student_id', '').strip()
    
    if not student_id:
        return jsonify({'success': False, 'message': 'Please enter a Student ID'})
    
    # Create new cursor for this request
    cur = database.create_cursor(db_con)
    student = database.get_student_by_id(cur, student_id)
    
    if not student:
        return jsonify({'success': False, 'message': f'Student ID {student_id} not found'})
    
    result = database.return_active_pass_for_student(cur, student_id)
    
    if result is None:
        return jsonify({'success': False, 'message': f'{student["Name"]} has no active pass'})
    
    database.save_data(db_con)
    return jsonify({'success': True, 'message': f'{student["Name"]} signed in successfully!'})

@app.route('/api/active_passes')
def get_active_passes_api():
    # Create new cursor for this request
    cur = database.create_cursor(db_con)
    active_passes = database.get_active_passes(cur)
    
    passes_with_time = []
    now = datetime.now()
    
    for p in active_passes:
        start_time = datetime.fromisoformat(p['pass_taken_at'])
        elapsed_seconds = int((now - start_time).total_seconds())
        duration_seconds = p['duration_minutes'] * 60
        time_remaining = duration_seconds - elapsed_seconds
        
        passes_with_time.append({
            'pass_id': p['pass_id'],
            'student_id': p['student_id'],
            'full_name': f"{p['first_name']} {p['last_name']}",
            'time_remaining': time_remaining
        })
    
    # Get capacity info
    max_students = int(database.get_setting(cur, 'max_students_out', '10'))
    capacity_enabled = database.get_setting(cur, 'enable_capacity_limit', '1') == '1'
    
    return jsonify({
        'passes': passes_with_time,
        'capacity': {
            'current': len(active_passes),
            'max': max_students,
            'enabled': capacity_enabled
        }
    })

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    # Create new cursor for this request
    cur = database.create_cursor(db_con)
    students = database.get_all_students(cur)
    passes = database.get_recent_passes_with_details(cur, limit=100)
    settings = database.get_all_settings(cur)
    
    return render_template('admin.html', students=students, passes=passes, settings=settings)

@app.route('/admin/add_student', methods=['POST'])
@login_required
def add_student():
    student_id = request.form.get('student_id', '').strip()
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    
    if not all([student_id, first_name, last_name]):
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    # Create new cursor for this request
    cur = database.create_cursor(db_con)
    
    try:
        database.insert_student(cur, student_id, first_name, last_name)
        database.save_data(db_con)
        return jsonify({'success': True, 'message': f'Added {first_name} {last_name}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/admin/delete_student', methods=['POST'])
@login_required
def delete_student():
    student_id = request.form.get('student_id', '').strip()
    
    if not student_id:
        return jsonify({'success': False, 'message': 'Student ID required'})
    
    # Create new cursor for this request
    cur = database.create_cursor(db_con)
    
    if database.delete_student_by_id(cur, student_id):
        database.save_data(db_con)
        return jsonify({'success': True, 'message': 'Student deleted'})
    else:
        return jsonify({'success': False, 'message': 'Student not found'})

@app.route('/admin/return_pass', methods=['POST'])
@login_required
def admin_return_pass():
    pass_id = request.form.get('pass_id', '').strip()
    
    if not pass_id:
        return jsonify({'success': False, 'message': 'Pass ID required'})
    
    # Create new cursor for this request
    cur = database.create_cursor(db_con)
    result = database.return_pass_by_id(cur, int(pass_id))
    
    if result:
        database.save_data(db_con)
        return jsonify({'success': True, 'message': 'Pass returned'})
    else:
        return jsonify({'success': False, 'message': 'Pass not found or already returned'})

@app.route('/admin/update_setting', methods=['POST'])
@login_required
def update_setting():
    setting_key = request.form.get('setting_key', '').strip()
    setting_value = request.form.get('setting_value', '').strip()
    
    if not setting_key or not setting_value:
        return jsonify({'success': False, 'message': 'Invalid input'})
    
    # Create new cursor for this request
    cur = database.create_cursor(db_con)
    
    if database.update_setting(cur, setting_key, setting_value):
        database.save_data(db_con)
        return jsonify({'success': True, 'message': 'Setting updated'})
    else:
        return jsonify({'success': False, 'message': 'Setting not found'})

@app.route('/admin/import_csv', methods=['POST'])
@login_required
def import_csv():
    if 'csv_file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})
    
    file = request.files['csv_file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if not file.filename.endswith('.csv'):
        return jsonify({'success': False, 'message': 'File must be CSV'})
    
    try:
        import csv
        content = file.read().decode('utf-8')
        csv_reader = csv.DictReader(content.splitlines())
        
        students_data = []
        for row in csv_reader:
            student_id = row.get('student_id', '').strip()
            first_name = row.get('first_name', '').strip()
            last_name = row.get('last_name', '').strip()
            
            if student_id and first_name and last_name:
                students_data.append((student_id, first_name, last_name))
        
        if not students_data:
            return jsonify({'success': False, 'message': 'No valid data found in CSV'})
        
        # Create new cursor for this request
        cur = database.create_cursor(db_con)
        update_existing = request.form.get('update_existing') == 'true'
        summary = database.add_or_update_students_from_csv_data(cur, students_data, update_existing)
        database.save_data(db_con)
        
        message = f"Added: {summary['added']}, Updated: {summary['updated']}, Skipped: {summary['skipped']}"
        if summary['errors']:
            message += f", Errors: {len(summary['errors'])}"
        
        return jsonify({'success': True, 'message': message, 'summary': summary})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing file: {str(e)}'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
