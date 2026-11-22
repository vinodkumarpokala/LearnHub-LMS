import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("LMS_DB_PATH", os.path.join(APP_DIR, "lms.db"))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            instructor TEXT NOT NULL,
            description TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, course_id),
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        );
        """)
        count = db.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        if count == 0:
            db.executemany(
                "INSERT INTO courses(title, instructor, description) VALUES (?, ?, ?)",
                [
                    ("Linux Fundamentals", "Admin Team", "Learn Linux commands, files, processes and services."),
                    ("AWS Cloud Basics", "Cloud Team", "Understand EC2, security groups, networking and CloudWatch."),
                    ("Docker & Kubernetes", "Platform Team", "Learn containers, images, pods and deployments.")
                ]
            )
        count = db.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        if count == 0:
            db.executemany(
                "INSERT INTO students(name, email) VALUES (?, ?)",
                [
                    ("Aarav Kumar", "aarav@example.com"),
                    ("Diya Sharma", "diya@example.com")
                ]
            )


@app.context_processor
def inject_helpers():
    def get_students():
        with get_db() as db:
            return db.execute("SELECT * FROM students ORDER BY name").fetchall()
    return {"get_students": get_students}


@app.route("/")
def index():
    with get_db() as db:
        courses = db.execute("""
            SELECT c.*, COUNT(e.id) AS enrolled
            FROM courses c LEFT JOIN enrollments e ON e.course_id = c.id
            GROUP BY c.id ORDER BY c.id
        """).fetchall()
        students = db.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        enrollments = db.execute("SELECT COUNT(*) FROM enrollments").fetchone()[0]
    return render_template("index.html", courses=courses, students=students, enrollments=enrollments)


@app.route("/courses")
def courses():
    with get_db() as db:
        rows = db.execute("SELECT * FROM courses ORDER BY id DESC").fetchall()
    return render_template("courses.html", courses=rows)


@app.route("/courses/add", methods=["POST"])
def add_course():
    title = request.form.get("title", "").strip()
    instructor = request.form.get("instructor", "").strip()
    description = request.form.get("description", "").strip()
    if not all([title, instructor, description]):
        flash("Please complete all course fields.", "error")
        return redirect(url_for("courses"))
    with get_db() as db:
        db.execute(
            "INSERT INTO courses(title, instructor, description) VALUES (?, ?, ?)",
            (title, instructor, description)
        )
    flash("Course added successfully.", "success")
    return redirect(url_for("courses"))


@app.route("/students")
def students():
    with get_db() as db:
        rows = db.execute("SELECT * FROM students ORDER BY name").fetchall()
    return render_template("students.html", students=rows)


@app.route("/enroll", methods=["POST"])
def enroll():
    student_id = request.form.get("student_id", type=int)
    course_id = request.form.get("course_id", type=int)
    if not student_id or not course_id:
        flash("Choose a student and a course.", "error")
        return redirect(url_for("index"))
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO enrollments(student_id, course_id) VALUES (?, ?)",
                (student_id, course_id)
            )
        flash("Student enrolled successfully.", "success")
    except sqlite3.IntegrityError:
        flash("This student is already enrolled in that course.", "error")
    return redirect(url_for("index"))


@app.route("/health")
def health():
    try:
        with get_db() as db:
            db.execute("SELECT 1")
        return jsonify(status="healthy", database="connected"), 200
    except Exception:
        app.logger.exception("Health check failed")
        return jsonify(status="unhealthy"), 500


@app.route("/ready")
def ready():
    return jsonify(status="ready"), 200


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
