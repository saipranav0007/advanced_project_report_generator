"""
Project Report Generator (Template-Based)
Flask backend - app.py

2nd Year B.Tech Mini Project -> Expanded Personal Version
Run with:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000
"""

import os
import re
import json
import webbrowser
import threading
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash,
    send_file, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from models import init_db, get_db, DB_PATH
from reportgen import generate_reports
import chatbot  # advanced rule-based AI Assistant logic

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.abspath(os.path.join(BASE_DIR, "../frontend/templates"))
STATIC_DIR = os.path.abspath(os.path.join(BASE_DIR, "../static"))

UPLOAD_DIR = os.path.join(STATIC_DIR, "images")
GENERATED_DIR = os.path.join(BASE_DIR, "reports", "generated")

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = "prg-dev-secret-key-change-in-production-2026"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB uploads

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

REPORT_FIELDS = [
    "project_title", "student_name", "roll_number", "department", "branch",
    "college", "guide_name", "academic_year", "project_type", "abstract",
    "introduction", "objectives", "problem_statement", "existing_system",
    "proposed_system", "methodology", "modules", "technologies",
    "advantages", "limitations", "future_scope", "conclusion", "references",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def current_user():
    if "user_id" not in session:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?",
                         (session["user_id"],)).fetchone()
    conn.close()
    return user


def login_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not user["is_admin"]:
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    unread_count = 0
    if "user_id" in session:
        conn = get_db()
        unread_count = conn.execute(
            "SELECT COUNT(*) c FROM notifications WHERE user_id = ? AND is_read = 0",
            (session["user_id"],)).fetchone()["c"]
        conn.close()
    return {
        "current_year": datetime.now().year,
        "logged_in_user": current_user() if "user_id" in session else None,
        "unread_notifications": unread_count,
    }


def safe_filename_base(title, report_id):
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_").lower() or "report"
    return f"{slug}_{report_id}"


def create_notification(conn, user_id, message, ntype="info"):
    conn.execute(
        "INSERT INTO notifications (user_id, message, type, is_read, created_at) "
        "VALUES (?, ?, ?, 0, ?)",
        (user_id, message, ntype, datetime.now().isoformat()))


def can_access_report(conn, report, user, need_edit=False):
    if report is None:
        return False
    if report["user_id"] == user["id"]:
        return True
    collab = conn.execute(
        "SELECT * FROM collaborators WHERE report_id = ? AND user_id = ?",
        (report["id"], user["id"])).fetchone()
    if not collab:
        return False
    if need_edit:
        return collab["role"] in ("owner", "editor")
    return True


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    conn = get_db()
    stats = {
        "reports": conn.execute("SELECT COUNT(*) c FROM reports").fetchone()["c"],
        "users": conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
        "templates": conn.execute("SELECT COUNT(*) c FROM templates").fetchone()["c"],
        "downloads": conn.execute("SELECT COUNT(*) c FROM downloads").fetchone()["c"],
    }
    conn.close()
    return render_template("index.html", stats=stats)


@app.route("/help")
def help_page():
    return render_template("help.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if len(name) < 2:
            errors.append("Please enter your full name.")
        if not EMAIL_RE.match(email):
            errors.append("Please enter a valid email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if password != confirm:
            errors.append("Passwords do not match.")

        conn = get_db()
        if not errors:
            existing = conn.execute("SELECT id FROM users WHERE email = ?",
                                     (email,)).fetchone()
            if existing:
                errors.append("An account with this email already exists.")

        if errors:
            conn.close()
            for e in errors:
                flash(e, "danger")
            return render_template("register.html", name=name, email=email)

        conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) "
            "VALUES (?, ?, ?, ?)",
            (name, email, generate_password_hash(password), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember")

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session.permanent = bool(remember)
            session["chat_history"] = []
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
        return render_template("login.html", email=email)

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    conn = get_db()
    total_reports = conn.execute(
        "SELECT COUNT(*) c FROM reports WHERE user_id = ? AND is_deleted = 0",
        (user["id"],)).fetchone()["c"]
    total_downloads = conn.execute(
        "SELECT COUNT(*) c FROM downloads WHERE user_id = ?", (user["id"],)).fetchone()["c"]
    total_templates = conn.execute("SELECT COUNT(*) c FROM templates").fetchone()["c"]
    total_drafts = conn.execute(
        "SELECT COUNT(*) c FROM drafts WHERE user_id = ?", (user["id"],)).fetchone()["c"]
    recent_reports = conn.execute(
        "SELECT * FROM reports WHERE user_id = ? AND is_deleted = 0 "
        "ORDER BY created_at DESC LIMIT 5",
        (user["id"],)).fetchall()
    conn.close()

    return render_template(
        "dashboard.html",
        total_reports=total_reports,
        total_downloads=total_downloads,
        total_templates=total_templates,
        total_drafts=total_drafts,
        recent_reports=recent_reports,
    )


# ---------------------------------------------------------------------------
# Templates gallery
# ---------------------------------------------------------------------------

@app.route("/templates")
@login_required
def templates_gallery():
    conn = get_db()
    templates = conn.execute(
        "SELECT * FROM templates WHERE is_active = 1 ORDER BY id").fetchall()
    conn.close()
    return render_template("templates.html", templates=templates)


# ---------------------------------------------------------------------------
# Create report / drafts
# ---------------------------------------------------------------------------

@app.route("/create-report", methods=["GET", "POST"])
@app.route("/create-report/<slug>", methods=["GET", "POST"])
@login_required
def create_report(slug="mini-project"):
    user = current_user()
    conn = get_db()
    template = conn.execute("SELECT * FROM templates WHERE slug = ?", (slug,)).fetchone()
    if not template:
        conn.close()
        abort(404)

    draft_data = {}
    draft_id = request.args.get("draft_id")
    if draft_id:
        draft = conn.execute(
            "SELECT * FROM drafts WHERE id = ? AND user_id = ?",
            (draft_id, user["id"])).fetchone()
        if draft:
            draft_data = json.loads(draft["data_json"])

    if request.method == "POST":
        form_data = {f: request.form.get(f, "").strip() for f in REPORT_FIELDS}
        action = request.form.get("action", "generate")

        if action == "save_draft":
            payload = json.dumps(form_data)
            if draft_id:
                conn.execute(
                    "UPDATE drafts SET data_json = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                    (payload, datetime.now().isoformat(), draft_id, user["id"]))
            else:
                conn.execute(
                    "INSERT INTO drafts (user_id, template_slug, data_json, updated_at) "
                    "VALUES (?, ?, ?, ?)",
                    (user["id"], slug, payload, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            flash("Draft saved successfully.", "success")
            return redirect(url_for("my_drafts"))

        errors = []
        if not form_data["project_title"]:
            errors.append("Project title is required.")
        if not form_data["student_name"]:
            errors.append("Student name is required.")
        if not form_data["abstract"]:
            errors.append("Abstract is required.")

        if errors:
            for e in errors:
                flash(e, "danger")
            conn.close()
            return render_template("create_report.html", template=template,
                                    templates=None, draft=form_data, draft_id=draft_id)

        if not form_data["project_type"]:
            form_data["project_type"] = template["name"]

        if action == "preview":
            conn.close()
            session["preview_data"] = form_data
            session["preview_slug"] = slug
            return redirect(url_for("preview_report"))

        cursor = conn.execute(
            "INSERT INTO reports (user_id, project_title, template_slug, data_json, "
            "created_at, is_deleted) VALUES (?, ?, ?, ?, ?, 0)",
            (user["id"], form_data["project_title"], slug, json.dumps(form_data),
             datetime.now().isoformat()))
        report_id = cursor.lastrowid

        if draft_id:
            conn.execute("DELETE FROM drafts WHERE id = ? AND user_id = ?",
                         (draft_id, user["id"]))

        create_notification(conn, user["id"],
                             f"Report \"{form_data['project_title']}\" was generated.",
                             "report")

        conn.commit()
        conn.close()
        flash("Report generated successfully!", "success")
        return redirect(url_for("preview_report", report_id=report_id))

    conn.close()
    return render_template("create_report.html", template=template,
                            draft=draft_data, draft_id=draft_id)


@app.route("/my-drafts")
@login_required
def my_drafts():
    user = current_user()
    conn = get_db()
    drafts = conn.execute(
        "SELECT d.*, t.name as template_name FROM drafts d "
        "LEFT JOIN templates t ON d.template_slug = t.slug "
        "WHERE d.user_id = ? ORDER BY d.updated_at DESC", (user["id"],)).fetchall()
    conn.close()
    parsed = []
    for d in drafts:
        data = json.loads(d["data_json"])
        parsed.append({
            "id": d["id"],
            "title": data.get("project_title") or "Untitled Draft",
            "template_name": d["template_name"] or d["template_slug"],
            "template_slug": d["template_slug"],
            "updated_at": d["updated_at"],
        })
    return render_template("my_drafts.html", drafts=parsed)


@app.route("/drafts/<int:draft_id>/delete", methods=["POST"])
@login_required
def delete_draft(draft_id):
    user = current_user()
    conn = get_db()
    conn.execute("DELETE FROM drafts WHERE id = ? AND user_id = ?", (draft_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Draft deleted.", "info")
    return redirect(url_for("my_drafts"))


# ---------------------------------------------------------------------------
# Preview / generate files
# ---------------------------------------------------------------------------

@app.route("/preview")
@app.route("/preview/<int:report_id>")
@login_required
def preview_report(report_id=None):
    user = current_user()
    conn = get_db()
    if report_id:
        report = conn.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if not report or not can_access_report(conn, report, user):
            conn.close()
            abort(404)
        data = json.loads(report["data_json"])
        conn.close()
        return render_template("preview.html", data=data, report_id=report_id)

    data = session.get("preview_data")
    conn.close()
    if not data:
        abort(404)
    return render_template("preview.html", data=data, report_id=None)


@app.route("/report/<int:report_id>/download/<file_type>")
@login_required
def download_report(report_id, file_type):
    if file_type not in ("pdf", "docx"):
        abort(400)
    user = current_user()
    conn = get_db()
    report = conn.execute(
        "SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not report or not can_access_report(conn, report, user):
        conn.close()
        abort(404)

    data = json.loads(report["data_json"])
    base = safe_filename_base(report["project_title"], report_id)
    pdf_path = os.path.join(GENERATED_DIR, f"{base}.pdf")
    docx_path = os.path.join(GENERATED_DIR, f"{base}.docx")

    if not (os.path.exists(pdf_path) and os.path.exists(docx_path)):
        generate_reports(data, base)

    target_path = pdf_path if file_type == "pdf" else docx_path
    download_name = f"{base}.{file_type}"

    conn.execute(
        "INSERT INTO downloads (user_id, report_id, file_type, file_path, downloaded_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (user["id"], report_id, file_type, target_path, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return send_file(target_path, as_attachment=True, download_name=download_name)


# ---------------------------------------------------------------------------
# My reports
# ---------------------------------------------------------------------------

@app.route("/my-reports")
@login_required
def my_reports():
    user = current_user()
    conn = get_db()
    search_q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "newest")

    query = ("SELECT r.*, t.name as template_name FROM reports r "
             "LEFT JOIN templates t ON r.template_slug = t.slug "
             "WHERE r.user_id = ? AND r.is_deleted = 0")
    params = [user["id"]]
    if search_q:
        query += " AND r.project_title LIKE ?"
        params.append(f"%{search_q}%")

    if sort == "oldest":
        query += " ORDER BY r.created_at ASC"
    elif sort == "title":
        query += " ORDER BY r.project_title ASC"
    else:
        query += " ORDER BY r.created_at DESC"

    reports = conn.execute(query, params).fetchall()
    templates = conn.execute("SELECT * FROM templates").fetchall()
    conn.close()
    return render_template("reports.html", reports=reports, templates=templates,
                            search=search_q, sort=sort)


@app.route("/report/<int:report_id>/delete", methods=["POST"])
@login_required
def delete_report(report_id):
    user = current_user()
    conn = get_db()
    conn.execute(
        "UPDATE reports SET is_deleted = 1, deleted_at = ? WHERE id = ? AND user_id = ?",
        (datetime.now().isoformat(), report_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Report moved to Trash.", "info")
    return redirect(url_for("my_reports"))


# ---------------------------------------------------------------------------
# Trash / Archive
# ---------------------------------------------------------------------------

@app.route("/trash")
@login_required
def trash():
    user = current_user()
    conn = get_db()
    trashed = conn.execute(
        "SELECT * FROM reports WHERE user_id = ? AND is_deleted = 1 "
        "ORDER BY deleted_at DESC", (user["id"],)).fetchall()
    conn.close()
    return render_template("trash.html", reports=trashed)


@app.route("/report/<int:report_id>/restore", methods=["POST"])
@login_required
def restore_report(report_id):
    user = current_user()
    conn = get_db()
    conn.execute(
        "UPDATE reports SET is_deleted = 0, deleted_at = NULL WHERE id = ? AND user_id = ?",
        (report_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Report restored.", "success")
    return redirect(url_for("trash"))


@app.route("/report/<int:report_id>/delete-permanently", methods=["POST"])
@login_required
def delete_permanently(report_id):
    user = current_user()
    conn = get_db()
    conn.execute("DELETE FROM reports WHERE id = ? AND user_id = ?", (report_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Report permanently deleted.", "info")
    return redirect(url_for("trash"))


@app.route("/trash/empty", methods=["POST"])
@login_required
def empty_trash():
    user = current_user()
    conn = get_db()
    conn.execute("DELETE FROM reports WHERE user_id = ? AND is_deleted = 1", (user["id"],))
    conn.commit()
    conn.close()
    flash("Trash emptied.", "info")
    return redirect(url_for("trash"))


# ---------------------------------------------------------------------------
# AI Assistant page + Team / Collaboration
# ---------------------------------------------------------------------------

@app.route("/ai-assistant")
@app.route("/ai-assistant/<int:report_id>")
@login_required
def ai_assistant_page(report_id=None):
    user = current_user()
    conn = get_db()
    report = None
    if report_id:
        report = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if not report or not can_access_report(conn, report, user):
            conn.close()
            abort(404)
    my_reports_list = conn.execute(
        "SELECT id, project_title FROM reports WHERE user_id = ? AND is_deleted = 0 "
        "ORDER BY created_at DESC", (user["id"],)).fetchall()
    conn.close()
    return render_template("ai_assistant.html", report=report, my_reports=my_reports_list)


@app.route("/collaboration")
@login_required
def collaboration_hub():
    user = current_user()
    conn = get_db()
    owned = conn.execute(
        "SELECT r.*, (SELECT COUNT(*) FROM collaborators c WHERE c.report_id = r.id) "
        "as collaborator_count FROM reports r "
        "WHERE r.user_id = ? AND r.is_deleted = 0 ORDER BY r.created_at DESC",
        (user["id"],)).fetchall()
    shared_with_me = conn.execute(
        "SELECT r.*, c.role, u.name as owner_name FROM collaborators c "
        "JOIN reports r ON c.report_id = r.id "
        "JOIN users u ON r.user_id = u.id "
        "WHERE c.user_id = ? AND r.is_deleted = 0 ORDER BY c.invited_at DESC",
        (user["id"],)).fetchall()
    conn.close()
    return render_template("collaboration.html", owned=owned, shared_with_me=shared_with_me)


@app.route("/report/<int:report_id>/share", methods=["GET", "POST"])
@login_required
def share_report(report_id):
    user = current_user()
    conn = get_db()
    report = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not report or report["user_id"] != user["id"]:
        conn.close()
        abort(404)

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "viewer")
        if role not in ("editor", "viewer"):
            role = "viewer"

        invitee = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not invitee:
            flash("No account found with that email.", "danger")
        elif invitee["id"] == user["id"]:
            flash("You already own this report.", "warning")
        else:
            existing = conn.execute(
                "SELECT * FROM collaborators WHERE report_id = ? AND user_id = ?",
                (report_id, invitee["id"])).fetchone()
            if existing:
                conn.execute("UPDATE collaborators SET role = ? WHERE id = ?",
                             (role, existing["id"]))
            else:
                conn.execute(
                    "INSERT INTO collaborators (report_id, user_id, role, invited_at) "
                    "VALUES (?, ?, ?, ?)",
                    (report_id, invitee["id"], role, datetime.now().isoformat()))
            create_notification(
                conn, invitee["id"],
                f"{user['name']} shared \"{report['project_title']}\" with you ({role}).",
                "share")
            conn.commit()
            flash(f"Shared with {email} as {role}.", "success")

    collaborators = conn.execute(
        "SELECT c.*, u.name, u.email FROM collaborators c "
        "JOIN users u ON c.user_id = u.id WHERE c.report_id = ?", (report_id,)).fetchall()
    conn.close()
    return render_template("share_report.html", report=report, collaborators=collaborators)


@app.route("/report/<int:report_id>/collaborators/<int:collab_id>/remove", methods=["POST"])
@login_required
def remove_collaborator(report_id, collab_id):
    user = current_user()
    conn = get_db()
    report = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not report or report["user_id"] != user["id"]:
        conn.close()
        abort(404)
    conn.execute("DELETE FROM collaborators WHERE id = ? AND report_id = ?",
                 (collab_id, report_id))
    conn.commit()
    conn.close()
    flash("Collaborator removed.", "info")
    return redirect(url_for("share_report", report_id=report_id))


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------

@app.route("/downloads")
@login_required
def downloads():
    user = current_user()
    conn = get_db()
    rows = conn.execute(
        "SELECT d.*, r.project_title FROM downloads d "
        "JOIN reports r ON d.report_id = r.id "
        "WHERE d.user_id = ? ORDER BY d.downloaded_at DESC", (user["id"],)).fetchall()
    conn.close()
    return render_template("downloads.html", downloads=rows)


@app.route("/downloads/<int:download_id>/delete", methods=["POST"])
@login_required
def delete_download(download_id):
    user = current_user()
    conn = get_db()
    conn.execute("DELETE FROM downloads WHERE id = ? AND user_id = ?", (download_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Removed from downloads history.", "info")
    return redirect(url_for("downloads"))


@app.route("/downloads/<int:download_id>/open")
@login_required
def open_download(download_id):
    user = current_user()
    conn = get_db()
    row = conn.execute("SELECT * FROM downloads WHERE id = ? AND user_id = ?",
                        (download_id, user["id"])).fetchone()
    conn.close()
    if not row or not os.path.exists(row["file_path"]):
        abort(404)
    return send_file(row["file_path"])


# ---------------------------------------------------------------------------
# Search (global)
# ---------------------------------------------------------------------------

@app.route("/search")
@login_required
def search():
    user = current_user()
    q = request.args.get("q", "").strip()
    results = {"reports": [], "drafts": [], "chat": []}

    if q:
        conn = get_db()
        like = f"%{q}%"
        results["reports"] = conn.execute(
            "SELECT * FROM reports WHERE user_id = ? AND is_deleted = 0 "
            "AND project_title LIKE ? ORDER BY created_at DESC",
            (user["id"], like)).fetchall()

        draft_rows = conn.execute(
            "SELECT * FROM drafts WHERE user_id = ? AND data_json LIKE ? "
            "ORDER BY updated_at DESC", (user["id"], like)).fetchall()
        parsed_drafts = []
        for d in draft_rows:
            data = json.loads(d["data_json"])
            parsed_drafts.append({
                "id": d["id"],
                "title": data.get("project_title") or "Untitled Draft",
                "updated_at": d["updated_at"],
            })
        results["drafts"] = parsed_drafts

        results["chat"] = conn.execute(
            "SELECT * FROM chat_messages WHERE user_id = ? AND message LIKE ? "
            "ORDER BY created_at DESC LIMIT 20", (user["id"], like)).fetchall()
        conn.close()

    return render_template("search.html", q=q, results=results)


# ---------------------------------------------------------------------------
# Analytics / Insights
# ---------------------------------------------------------------------------

@app.route("/analytics")
@login_required
def analytics():
    user = current_user()
    conn = get_db()

    by_category = conn.execute(
        "SELECT t.name, COUNT(*) c FROM reports r "
        "JOIN templates t ON r.template_slug = t.slug "
        "WHERE r.user_id = ? AND r.is_deleted = 0 GROUP BY t.name",
        (user["id"],)).fetchall()

    by_format = conn.execute(
        "SELECT file_type, COUNT(*) c FROM downloads WHERE user_id = ? GROUP BY file_type",
        (user["id"],)).fetchall()

    over_time = conn.execute(
        "SELECT substr(created_at, 1, 10) as day, COUNT(*) c FROM reports "
        "WHERE user_id = ? AND is_deleted = 0 GROUP BY day ORDER BY day",
        (user["id"],)).fetchall()

    chat_count = conn.execute(
        "SELECT COUNT(*) c FROM chat_messages WHERE user_id = ?",
        (user["id"],)).fetchone()["c"]

    conn.close()
    return render_template(
        "analytics.html",
        by_category=by_category,
        by_format=by_format,
        over_time=over_time,
        chat_count=chat_count,
    )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@app.route("/notifications")
@login_required
def notifications():
    user = current_user()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
        (user["id"],)).fetchall()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user["id"],))
    conn.commit()
    conn.close()
    return render_template("notifications.html", notifications=rows)


@app.route("/notifications/<int:notif_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notif_id):
    user = current_user()
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
                 (notif_id, user["id"]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Profile / Settings
# ---------------------------------------------------------------------------

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    conn = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        department = request.form.get("department", "").strip()
        college = request.form.get("college", "").strip()
        photo_file = request.files.get("photo")

        photo_filename = user["photo"]
        if photo_file and photo_file.filename:
            ext = os.path.splitext(photo_file.filename)[1].lower()
            if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                photo_filename = secure_filename(f"user_{user['id']}{ext}")
                photo_file.save(os.path.join(UPLOAD_DIR, photo_filename))

        conn.execute(
            "UPDATE users SET name = ?, department = ?, college = ?, photo = ? WHERE id = ?",
            (name, department, college, photo_filename, user["id"]))
        conn.commit()
        flash("Profile updated successfully.", "success")

    conn.close()
    user = current_user()
    return render_template("profile.html", user=user)


@app.route("/profile/change-password", methods=["POST"])
@login_required
def change_password():
    user = current_user()
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_new_password", "")

    if not check_password_hash(user["password_hash"], current):
        flash("Current password is incorrect.", "danger")
    elif len(new) < 6:
        flash("New password must be at least 6 characters.", "danger")
    elif new != confirm:
        flash("New passwords do not match.", "danger")
    else:
        conn = get_db()
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                     (generate_password_hash(new), user["id"]))
        conn.commit()
        conn.close()
        flash("Password changed successfully.", "success")

    return redirect(url_for("profile"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = current_user()
    if request.method == "POST":
        dark_mode = 1 if request.form.get("dark_mode") else 0
        notifications_pref = 1 if request.form.get("notifications") else 0
        conn = get_db()
        conn.execute("UPDATE users SET dark_mode = ?, notifications = ? WHERE id = ?",
                     (dark_mode, notifications_pref, user["id"]))
        conn.commit()
        conn.close()
        flash("Settings updated.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", user=user)


@app.route("/api/toggle-theme", methods=["POST"])
@login_required
def toggle_theme():
    user = current_user()
    new_val = 0 if user["dark_mode"] else 1
    conn = get_db()
    conn.execute("UPDATE users SET dark_mode = ? WHERE id = ?", (new_val, user["id"]))
    conn.commit()
    conn.close()
    return jsonify({"dark_mode": new_val})


# ---------------------------------------------------------------------------
# AI Assistant chat API
# ---------------------------------------------------------------------------

@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    user = current_user()
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    report_id = payload.get("report_id")

    if not message:
        return jsonify({"error": "Empty message"}), 400

    report_context = None
    if report_id:
        conn = get_db()
        report = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        conn.close()
        if report:
            report_context = {
                "title": report["project_title"],
                "category": report["template_slug"],
            }

    history = session.get("chat_history", [])
    reply = chatbot.get_reply(message, history=history, report_context=report_context)

    history.append({"role": "user", "text": message})
    history.append({"role": "bot", "text": reply})
    session["chat_history"] = history[-10:]

    conn = get_db()
    conn.execute(
        "INSERT INTO chat_messages (user_id, report_id, role, message, created_at) "
        "VALUES (?, ?, 'user', ?, ?)",
        (user["id"], report_id, message, datetime.now().isoformat()))
    conn.execute(
        "INSERT INTO chat_messages (user_id, report_id, role, message, created_at) "
        "VALUES (?, ?, 'bot', ?, ?)",
        (user["id"], report_id, reply, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify({"reply": reply})


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    conn = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    reports = conn.execute(
        "SELECT r.*, u.name as user_name FROM reports r "
        "JOIN users u ON r.user_id = u.id ORDER BY r.created_at DESC").fetchall()
    templates = conn.execute("SELECT * FROM templates ORDER BY id").fetchall()
    conn.close()
    return render_template("admin.html", users=users, reports=reports, templates=templates)


@app.route("/admin/report/<int:report_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_delete_report(report_id):
    conn = get_db()
    conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()
    flash("Report deleted by admin.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/template/<int:template_id>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_template(template_id):
    conn = get_db()
    tpl = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
    if tpl:
        conn.execute("UPDATE templates SET is_active = ? WHERE id = ?",
                     (0 if tpl["is_active"] else 1, template_id))
        conn.commit()
    conn.close()
    flash("Template status updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_delete_user(user_id):
    admin = current_user()
    if user_id == admin["id"]:
        flash("You cannot delete your own admin account.", "danger")
        return redirect(url_for("admin_dashboard"))
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash("User deleted by admin.", "info")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(413)
def too_large(e):
    flash("Uploaded file is too large (max 5MB).", "danger")
    return redirect(request.referrer or url_for("dashboard"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")


if __name__ == "__main__":
    init_db(app)
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Timer(1.25, open_browser).start()
    app.run(debug=True, port=5000)
