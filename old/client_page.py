from flask import Flask, request, redirect, url_for, render_template_string, session, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import csv
import database

app = Flask(__name__)

# Secret key for sessions (use a strong random value in production!)
app.secret_key = "supersecretkey"

# Upload configuration
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"csv"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# CSV file storing usernames and password hashes
USER_FILE = "users.csv"


# --- Utility functions ---
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_users():
    """Load users from CSV into a dictionary {username: password_hash}"""
    users = {}
    if os.path.exists(USER_FILE):
        with open(USER_FILE, newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) == 2:
                    users[row[0]] = row[1]
    return users


def add_user(username, password):
    """Add a new user with hashed password to the CSV"""
    password_hash = generate_password_hash(password)
    with open(USER_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([username, password_hash])


# --- Routes ---
@app.route("/")
def home():
    if "username" in session:
        return f"Hello {session['username']}! <br><a href='/upload'>Upload File</a><br><a href='/logout'>Logout</a>"
    return "You are not logged in. <br><a href='/login'>Login</a>"


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        users = load_users()

        if username in users and check_password_hash(users[username], password):
            session["username"] = username
            flash("Login successful!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials", "error")

    return render_template_string("""
        <h2>Login</h2>
        <form method="post">
            <input type="text" name="username" placeholder="Username" required><br>
            <input type="password" name="password" placeholder="Password" required><br>
            <input type="submit" value="Login">
        </form>
    """)


@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/upload", methods=["GET", "POST"])
def upload_file():
    # Enum
    student_number = 0
    student_first_name = 1
    student_last_name = 2

    if "username" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part", "error")
            return redirect(request.url)
        file = request.files["file"]
        if file.filename == "":
            flash("No selected file", "error")
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)
            flash(f"File {filename} uploaded successfully! Starting parse...", "success")

            with open(os.path.join(app.config["UPLOAD_FOLDER"], filename), 'r') as Scsv:
                content = Scsv.read()
           
            err_students = []
            data_con = database.create_connection()
            data_cur = database.create_cursor(data_con)
            content = content.split('\n')
            for index,line in enumerate(content):
                content[index] = line.split(',')

                try:
                    database.insert_student(data_cur, content[index][student_number], content[index][student_first_name], content[index][student_last_name])
                except Exception as e:
                    if len(content) >= 1:
                        err_students.append(f"{content[index][student_number]}: {e}")
                    else:
                        err_students.append([f"Unexpected empty line {index}"])

            print(f"{len(content)-len(err_students)} of {len(content)} entries added with {len(err_students)} error(s).\n{('\n'.join(err_students)) if len(err_students) != 0 else ''}")
            database.save_data(data_con)

            #return redirect(url_for("home"))

    return render_template_string("""
        <h2>Upload File</h2>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="file" required><br>
            <input type="submit" value="Upload">
        </form>
        <br>
        <a href="/">Back to Home</a>
    """)


if __name__ == "__main__":
    # If no users.csv exists, create one with a default admin user
    if not os.path.exists(USER_FILE):
        add_user("admin", "password123")  # Change this!
        print("Created default user: admin / password123")

    app.run(debug=True)

