
from pathlib import Path
from uuid import UUID
from tempfile import TemporaryDirectory
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, render_template, request

# Load project environment variables
load_dotenv(
    dotenv_path=Path(__file__).resolve().parent.parent / ".env"
)

# Import existing backend modules
if __package__:
    from .task import Task
    from .account import Account
    from .announcement import Announcement
    from .assignment import Assignment
    from .history import History
else:
    from task import Task
    from account import Account
    from announcement import Announcement
    from assignment import Assignment
    from history import History

SITE_DIR = Path(__file__).resolve().parent.parent / "Frontend" / "cic-site"
app = Flask(
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
MEMBER_TEMPLATES = {
    "member": "member.html",
    "tasks": "task.html",
    "history": "history.html",
    "history-admin": "history-admin.html",
    "announcement": "announcement.html",
    "member_donate": "member_donate.html",
    "account": "unavailable.html",
    "services": "unavailable.html",
    "faq": "unavailable.html",
    "admin": None,
}
UNAVAILABLE_PAGES = {
    "account": ("Account Settings", "Account settings are not available on the website yet."),
    "services": ("Services", "Online service requests are not available yet."),
    "faq": ("FAQ / Help", "The FAQ is not available yet."),
}


def bearer_token():
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


@app.before_request
def require_api_token():
    # Reject missing credentials before constructing a Supabase client.
    public_endpoints = {"health", "login", "register", "current_user", "logout", "reset_password"}
    if (
        request.path.startswith("/api/")
        and request.endpoint is not None
        and request.endpoint not in public_endpoints
        and request.method != "OPTIONS"
        and not bearer_token()
    ):
        return jsonify({"error": "Unauthorized"}), 401


@app.after_request
def normalize_api_response(response):
    if request.path.startswith("/api/"):
        if response.is_json:
            data = response.get_json()
            if isinstance(data, dict):
                data["ok"] = response.status_code < 400
                response.set_data(app.json.dumps(data))
        response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(HTTPException)
def api_http_error(error):
    response = error.get_response()
    if request.path.startswith("/api/"):
        # Preserve HTTP headers such as Allow on 405 responses.
        response.set_data(app.json.dumps({"ok": False, "error": error.description}))
        response.content_type = "application/json"
    return response

# ==================================================
# SHARED AUTHENTICATION
# ==================================================

def authenticate(manager, required_role=None):
    """
    Verify the user's access token and identity.

    required_role:
        None        - any authenticated user
        "admin"     - CIC administrator
        "volunteer" - volunteer only

    Returns:
        (user_id, None) on success
        (None, error_response) on failure
    """

    token = bearer_token()

    if not token:
        return None, (
            jsonify({"error": "Unauthorized"}), 401
        )

    # Verify token through Supabase Auth
    try:
        response = manager.supabase.auth.get_user(token)

        if response.user is None:
            return None, (
                jsonify({"error": "Invalid token"}), 401
            )

        user_id = str(response.user.id)

        # Each route creates a fresh manager. Bind both database requests and
        # the lazily created Storage client to this user's JWT for RLS.
        manager.supabase.options.headers["Authorization"] = f"Bearer {token}"
        manager.supabase.postgrest.auth(token)

    except Exception:
        return None, (
            jsonify({"error": "Invalid or expired token"}), 401
        )

    # Check user role if required
    if required_role is not None:
        try:
            profile = (
                manager.supabase.table("profiles")
                .select("role")
                .eq("id", user_id)
                .single()
                .execute()
            )

        except Exception:
            app.logger.exception("Could not check profile role")

            return None, (
                jsonify({"error": "Could not verify user role"}), 500
            )

        if (
            not profile.data
            or profile.data.get("role") != required_role
        ):
            return None, (
                jsonify({
                    "error": f"{required_role.title()} access required"
                }), 403
            )

    return user_id, None


def authenticate_profile(manager):
    """Verify a token and require a recognized CIC profile."""
    user_id, error = authenticate(manager)
    if error is not None:
        return None, None, error

    profiles = (manager.supabase.table("profiles").select("role")
                .eq("id", user_id).limit(1).execute().data)
    role = profiles[0].get("role") if profiles else None
    if role not in {"admin", "volunteer"}:
        return None, None, (jsonify({"error": "Account profile is unavailable"}), 403)
    return user_id, role, None


# ==================================================
# SHARED VALIDATION
# ==================================================

def valid_uuid(value):
    """Return True if the value is a valid UUID."""
    try:
        UUID(value)
        return True

    except (ValueError, TypeError, AttributeError):
        return False


def read_text_fields(allowed, *, required=(), allow_blank=()):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Invalid JSON body")
    if data.keys() - set(allowed):
        abort(400, description=f"Only these fields can be sent: {', '.join(allowed)}")
    for field in required:
        if field not in data:
            abort(400, description=f"{field} is required")
    if not data:
        abort(400, description="No fields provided")
    fields = {}
    for field, value in data.items():
        if not isinstance(value, str):
            abort(400, description=f"{field} must be a string")
        value = value.strip()
        if not value and field not in allow_blank:
            abort(400, description=f"{field} cannot be empty")
        fields[field] = value
    return fields


# ==================================================
# HOME
# ==================================================

@app.route("/", methods=["GET"])
@app.route("/index.html", methods=["GET"])
@app.route("/home.html", methods=["GET"])
def home():
    return render_template("home.html")


@app.route("/about", methods=["GET"])
def about():
    return render_template("about.html")


@app.route("/<name>.html", methods=["GET"])
def page(name):
    if name not in {"about", "donate", "volunteer"}:
        abort(404)
    return render_template(f"{name}.html")


@app.route("/donate", methods=["GET"])
def donate_page():
    return render_template("donate.html")


@app.route("/volunteer", methods=["GET"])
def volunteer_page():
    return render_template("volunteer.html")


@app.route("/member", methods=["GET"])
@app.route("/member.html", methods=["GET"])
def member_dashboard():
    return render_template("member-loader.html", page_name="member")


@app.route("/tasks", methods=["GET"])
@app.route("/task.html", methods=["GET"])
def tasks_page():
    return render_template("member-loader.html", page_name="tasks")


@app.route("/account")
@app.route("/account.html")
@app.route("/services")
@app.route("/services.html")
@app.route("/faq")
@app.route("/faq.html")
def unavailable_member_page():
    page_name = request.path.removeprefix("/").removesuffix(".html")
    return render_template("member-loader.html", page_name=page_name)


@app.route("/admin", methods=["GET"])
def admin_dashboard():
    return render_template("member-loader.html", page_name="admin")


@app.route("/announcements", methods=["GET"])
@app.route("/announcement", methods=["GET"])
@app.route("/announcement.html", methods=["GET"])
def announcements_page():
    return render_template("member-loader.html", page_name="announcement")


@app.route("/member_donate", methods=["GET"])
@app.route("/member_donate.html", methods=["GET"])
def member_donate_page():
    return render_template("member-loader.html", page_name="member_donate")


@app.route("/history", methods=["GET"])
@app.route("/history.html", methods=["GET"])
def member_history():
    return render_template("member-loader.html", page_name="history")


@app.route("/admin/history", methods=["GET"])
@app.route("/history-admin", methods=["GET"])
@app.route("/history-admin.html", methods=["GET"])
def admin_history():
    return render_template("member-loader.html", page_name="history-admin")


def completed_history_rows(manager, user_id):
    assignments = manager.service_history(user_id)
    if assignments is None:
        raise RuntimeError("Could not load task history")
    rows = []
    for assignment in assignments:
        if assignment["status"] != "completed":
            continue
        task = assignment.get("tasks") or {}
        date = (assignment.get("reviewed_at") or assignment.get("submitted_at")
                or assignment.get("assigned_at") or "")
        rows.append({
            "date": date[:10],
            "title": task.get("title") or "",
            "status": assignment["status"],
            "hours": float(task.get("estimated_hours") or 0),
            "member_id": assignment["volunteer_id"],
        })
    return rows


@app.route("/api/pages/<page_name>", methods=["GET"])
def get_member_page(page_name):
    # Only completed, explicitly listed templates can be requested. The existing
    # API token guard rejects missing bearer tokens before client construction.
    if page_name not in MEMBER_TEMPLATES:
        abort(404)
    manager = History() if page_name in {"history", "history-admin"} else Account()
    required_role = "admin" if page_name in {"admin", "history-admin"} else None
    user_id, error = authenticate(manager, required_role=required_role)
    if error is not None:
        return error

    try:
        if required_role:
            role = required_role
        else:
            profile = manager.supabase.table("profiles").select("role").eq("id", user_id).single().execute()
            role = profile.data.get("role") if profile.data else None
        if role not in {"admin", "volunteer"}:
            return jsonify({"error": "Account profile is unavailable"}), 403
        if page_name == "admin" or (role == "admin" and page_name in {"member", "history"}):
            return jsonify({"redirect": "/admin/history"}), 200

        context = {}
        if page_name in UNAVAILABLE_PAGES:
            heading, message = UNAVAILABLE_PAGES[page_name]
            context = {"heading": heading, "message": message,
                       "dashboard_endpoint": "admin_history" if role == "admin" else "member_dashboard"}
        elif page_name == "tasks":
            context = {"can_pick_tasks": role == "volunteer"}
        elif page_name == "history":
            rows = completed_history_rows(manager, user_id)
            context = {"member_tasks": rows, "total_hours": round(sum(row["hours"] for row in rows), 2)}
        elif page_name == "history-admin":
            rows = completed_history_rows(manager, user_id)
            profiles = {}
            if rows:
                result = (manager.supabase.table("profiles").select("id, first_name, last_name, email")
                          .in_("id", list({row["member_id"] for row in rows})).execute())
                profiles = {profile["id"]: profile for profile in result.data}
            for row in rows:
                profile = profiles.get(row["member_id"], {})
                name = " ".join(filter(None, (profile.get("first_name"), profile.get("last_name")))).strip()
                row["member"] = name or profile.get("email") or row["member_id"]
            context = {"all_tasks": rows}
        return jsonify({"html": render_template(MEMBER_TEMPLATES[page_name], **context)}), 200
    except Exception:
        app.logger.exception("Could not load member page")
        return jsonify({"error": "Could not load page"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "message": "IT391 Backend is running!"
    }), 200


# ==================================================
# ACCOUNT - LOGIN
# ==================================================

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    email = data.get("email")
    password = data.get("password")

    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({
            "error": "Email and password are required"
        }), 400

    if not email.strip() or not password.strip():
        return jsonify({
            "error": "Email and password cannot be empty"
        }), 400

    # Call existing Account.login()
    success, role, session = Account().login(
        email, password
    )

    if not success or session is None:
        return jsonify({"error": "Login failed"}), 401

    return jsonify({
        "message": "Login successful",
        "role": role,
        "access_token": session.access_token
    }), 200


# ==================================================
# ACCOUNT - REGISTRATION (TEMPORARILY PAUSED)
# ==================================================

@app.route("/api/register", methods=["POST"])
@app.route("/api/signup", methods=["POST"])
def register():
    """
    Registration is temporarily paused until CIC's
    admin enrollment and Auth/Profile synchronization
    requirements are confirmed.
    """

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    required = [
        data.get("email"),
        data.get("password"),
        data.get("first_name"),
        data.get("last_name")
    ]

    if any(
        not isinstance(value, str) or not value.strip()
        for value in required
    ):
        return jsonify({
            "error": (
                "Email, password, first name "
                "and last name are required"
            )
        }), 400

    if not isinstance(data.get("phone", ""), str):
        return jsonify({
            "error": "Phone number must be a string"
        }), 400

    # return jsonify({
    #     "error": (
    #         "Registration temporarily unavailable "
    #         "pending Auth/Profile setup"
    #     )
    # }), 503
    if len(data["password"]) < 8:
        return jsonify({
            "error": "Password must be at least 8 characters"
        }), 400

    success = Account().create_account(
        email=data["email"],
        password=data["password"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        phone=data.get("phone", "")
    )

    if not success:
        return jsonify({
            "error": "Registration failed"
        }), 500

    return jsonify({
        "message": (
            "Registration request accepted. "
            "Please check your email to confirm your account."
        )
    }), 201

@app.route("/api/me", methods=["GET"])
def current_user():
    if "Authorization" not in request.headers:
        return jsonify({"logged_in": False}), 200

    if not bearer_token():
        return jsonify({"error": "Unauthorized"}), 401

    manager = Account()
    user_id, error = authenticate(manager)
    if error is not None:
        return error

    try:
        profile = (
            manager.supabase.table("profiles")
            .select("role")
            .eq("id", user_id)
            .single()
            .execute()
        )
        if not profile.data or profile.data.get("role") not in {"admin", "volunteer"}:
            return jsonify({"error": "Account profile is unavailable"}), 403
        return jsonify({
            "logged_in": True,
            "user_id": user_id,
            "role": profile.data["role"],
        }), 200
    except Exception:
        app.logger.exception("Failed to retrieve current user profile")
        return jsonify({"error": "Failed to retrieve profile"}), 500


@app.route("/api/logout", methods=["POST"])
def logout():
    # Access tokens are owned by the caller. The shared browser client clears
    # sessionStorage; this endpoint does not revoke an already issued JWT.
    return jsonify({"message": "Clear the client access token to complete logout"}), 200


@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400
    email = data.get("email")
    if not isinstance(email, str) or not email.strip():
        return jsonify({"error": "Email is required"}), 400

    try:
        Account().reset_password(email.strip())
    except Exception:
        app.logger.exception("Password reset request failed")
    # Do not disclose whether an email address has an account.
    return jsonify({"message": "If the account exists, a reset link will be sent"}), 200


@app.patch("/api/profile")
def update_profile_api():
    try:
        manager = Account()
        user_id, _, error = authenticate_profile(manager)
        if error is not None:
            return error

        fields = read_text_fields(("first_name", "last_name", "phone"), allow_blank=("phone",))
        updated = manager.update_profile(user_id, **fields)
        if not updated:
            return jsonify({"error": "Failed to update profile"}), 500
        profile = {key: updated[0].get(key) for key in ("id", "email", "first_name", "last_name", "phone")}
        return jsonify({"profile": profile}), 200
    except HTTPException:
        raise
    except Exception:
        app.logger.exception("Failed to update profile")
        return jsonify({"error": "Failed to update profile"}), 500


# ==================================================
# TASKS - LIST
# ==================================================

@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    manager = Task()

    user_id, error = authenticate(manager)

    if error is not None:
        return error

    try:
        tasks = manager.list_task(user_id)

        if tasks is None:
            return jsonify({
                "error": "Failed to load tasks"
            }), 500

        return jsonify({"tasks": tasks}), 200

    except Exception:
        app.logger.exception("Failed to load tasks")

        return jsonify({
            "error": "Failed to load tasks"
        }), 500


@app.post("/api/tasks")
def create_task_api():
    try:
        manager = Task()
        user_id, error = authenticate(manager, required_role="admin")
        if error is not None:
            return error

        fields = read_text_fields(("title", "description"), required=("title",), allow_blank=("description",))
        task = manager.create_task(user_id, **fields)
        if not task:
            return jsonify({"error": "Failed to create task"}), 500
        return jsonify({"task": task}), 201
    except HTTPException:
        raise
    except Exception:
        app.logger.exception("Failed to create task")
        return jsonify({"error": "Failed to create task"}), 500


@app.route("/api/tasks/<task_id>", methods=["GET", "PUT", "PATCH", "DELETE"])
def task_detail_api(task_id):
    try:
        manager = Task()
        read_only = request.method in {"GET", "HEAD"}
        if read_only:
            user_id, role, error = authenticate_profile(manager)
        else:
            user_id, error = authenticate(manager, required_role="admin")
        if error is not None:
            return error
        if not valid_uuid(task_id):
            return jsonify({"error": "Invalid task ID"}), 400
        task_id = str(UUID(task_id))

        if read_only:
            task = manager.task_info(task_id, open_only=(role == "volunteer"))
        elif request.method == "DELETE":
            deleted = manager.delete_task(user_id, task_id)
            if deleted is None:
                return jsonify({"error": "Task not found"}), 404
            if not deleted:
                return jsonify({"error": "Failed to delete task"}), 500
            return jsonify({"message": "Task deleted successfully"}), 200
        else:
            fields = read_text_fields(("title", "description"), allow_blank=("description",))
            task = manager.edit_task(user_id, task_id, **fields)

        if task is None:
            return jsonify({"error": "Task not found"}), 404
        if not task:
            return jsonify({"error": "Failed to update task"}), 500
        return jsonify({"task": task}), 200
    except HTTPException:
        raise
    except Exception:
        app.logger.exception("Could not process task request")
        return jsonify({"error": "Could not process task request"}), 500


# ==================================================
# SERVICE HISTORY AND ESTIMATED VOLUNTEER HOURS
# ==================================================

@app.get("/api/history")
@app.get("/api/hours")
def service_records_api():
    hours_only = request.path == "/api/hours"
    try:
        manager = History()
        user_id, role, error = authenticate_profile(manager)
        if error is not None:
            return error

        volunteer_id = request.args.get("volunteer_id")
        if volunteer_id is not None:
            if not valid_uuid(volunteer_id):
                return jsonify({"error": "Invalid volunteer ID"}), 400
            volunteer_id = str(UUID(volunteer_id))
        if role == "volunteer":
            if volunteer_id is not None and volunteer_id != user_id:
                return jsonify({"error": "Volunteers can only view their own records"}), 403
            volunteer_id = user_id
        elif hours_only and volunteer_id is None:
            return jsonify({"error": "volunteer_id is required for admin hour lookups"}), 400

        if hours_only:
            result = manager.track_volunteer_hours(user_id, volunteer_id=volunteer_id)
            if result is not None:
                return jsonify(result), 200
        else:
            result = manager.service_history(user_id, volunteer_id=volunteer_id)
            if result is not None:
                return jsonify({"history": result}), 200
    except Exception:
        app.logger.exception("Failed to load service records")
    return jsonify({"error": "Failed to load service records"}), 500


# ==================================================
# ANNOUNCEMENTS - LIST
# ==================================================

@app.route("/api/announcements", methods=["GET"])
def get_announcements():
    manager = Announcement()

    _, error = authenticate(manager)

    if error is not None:
        return error

    try:
        announcements = manager.list_announcements()

        if announcements is None:
            return jsonify({
                "error": "Failed to retrieve announcements"
            }), 500

        return jsonify({"announcements": announcements}), 200

    except Exception:
        app.logger.exception("Failed to retrieve announcements")

        return jsonify({
            "error": "Internal server error"
        }), 500


# ==================================================
# ANNOUNCEMENTS - CREATE
# ==================================================

@app.route("/api/announcements", methods=["POST"])
def create_announcement_api():
    manager = Announcement()

    user_id, error = authenticate(
        manager,
        required_role="admin"
    )

    if error is not None:
        return error

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    title = data.get("title")
    content = data.get("content")

    if (
        not isinstance(title, str)
        or not title.strip()
        or not isinstance(content, str)
        or not content.strip()
    ):
        return jsonify({
            "error": "Title and content are required"
        }), 400

    try:
        success = manager.create_announcement(
            user_id, title, content
        )

        if not success:
            return jsonify({
                "error": "Failed to create announcement"
            }), 500

        return jsonify({
            "message": "Announcement created successfully"
        }), 201

    except Exception:
        app.logger.exception("Failed to create announcement")

        return jsonify({
            "error": "Failed to create announcement"
        }), 500


# ==================================================
# ANNOUNCEMENTS - EDIT
# ==================================================

@app.route(
    "/api/announcements/<announcement_id>",
    methods=["PUT"]
)
def edit_announcement_api(announcement_id):
    manager = Announcement()

    user_id, error = authenticate(
        manager,
        required_role="admin"
    )

    if error is not None:
        return error

    if not valid_uuid(announcement_id):
        return jsonify({
            "error": "Invalid announcement ID"
        }), 400

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    title = data.get("title")
    content = data.get("content")

    if title is None and content is None:
        return jsonify({"error": "Nothing to update"}), 400

    if any(
        value is not None
        and (not isinstance(value, str) or not value.strip())
        for value in (title, content)
    ):
        return jsonify({
            "error": "Invalid title or content"
        }), 400

    try:
        existing = (
            manager.supabase.table("announcements")
            .select("announcement_id")
            .eq("announcement_id", announcement_id)
            .limit(1)
            .execute()
        )

        if not existing.data:
            return jsonify({
                "error": "Announcement not found"
            }), 404

        success = manager.edit_announcement(
            user_id, announcement_id, title, content
        )

        if not success:
            return jsonify({
                "error": "Update failed"
            }), 500

        return jsonify({
            "message": "Announcement updated successfully"
        }), 200

    except Exception:
        app.logger.exception("Failed to update announcement")

        return jsonify({
            "error": "Internal server error"
        }), 500


# ==================================================
# ANNOUNCEMENTS - DELETE (HARD DELETE)
# ==================================================

@app.route(
    "/api/announcements/<announcement_id>",
    methods=["DELETE"]
)
def delete_announcement_api(announcement_id):
    manager = Announcement()

    user_id, error = authenticate(
        manager,
        required_role="admin"
    )

    if error is not None:
        return error

    if not valid_uuid(announcement_id):
        return jsonify({
            "error": "Invalid announcement ID"
        }), 400

    try:
        existing = (
            manager.supabase.table("announcements")
            .select("announcement_id")
            .eq("announcement_id", announcement_id)
            .limit(1)
            .execute()
        )

        if not existing.data:
            return jsonify({
                "error": "Announcement not found"
            }), 404

        success = manager.delete_announcement(
            user_id, announcement_id
        )

        if not success:
            return jsonify({
                "error": "Failed to delete announcement"
            }), 500

        return jsonify({
            "message": "Announcement deleted successfully"
        }), 200

    except Exception:
        app.logger.exception("Failed to delete announcement")

        return jsonify({
            "error": "Internal server error"
        }), 500


# ==================================================
# ASSIGNMENTS - PICK TASK
# ==================================================

@app.route("/api/tasks/<task_id>/pick", methods=["POST"])
def pick_task_api(task_id):
    manager = Assignment()

    user_id, error = authenticate(
        manager,
        required_role="volunteer"
    )

    if error is not None:
        return error

    if not valid_uuid(task_id):
        return jsonify({
            "error": "Invalid task ID"
        }), 400

    try:
        result = manager.pick_task(user_id, task_id)

        if not result:
            return jsonify({
                "error": "Unable to pick task"
            }), 400

        return jsonify({
            "message": "Task picked successfully",
            "assignment": result
        }), 201

    except Exception:
        app.logger.exception("Could not pick task")

        return jsonify({
            "error": "Internal server error"
        }), 500


# ==================================================
# ASSIGNMENTS - CANCEL TASK
# ==================================================

@app.route("/api/tasks/<task_id>/cancel", methods=["POST"])
def cancel_task_api(task_id):
    manager = Assignment()

    user_id, error = authenticate(
        manager,
        required_role="volunteer"
    )

    if error is not None:
        return error

    if not valid_uuid(task_id):
        return jsonify({
            "error": "Invalid task ID"
        }), 400

    try:
        result = manager.cancel_task(user_id, task_id)

        if result is None:
            return jsonify({
                "error": "Unable to cancel assignment"
            }), 409

        return jsonify(result), 200

    except Exception:
        app.logger.exception("Could not cancel task")

        return jsonify({
            "error": "Internal server error"
        }), 500


# ==========================================
# ASSIGNMENTS - TRACK TASK STATUS
# ==========================================

@app.route("/api/assignments/status", methods=["GET"])
def track_task_status_api():
    manager = Assignment()

    user_id, error = authenticate(manager)

    if error is not None:
        return error

    try:
        assignments = manager.track_task_status(user_id)

        if assignments is None:
            return jsonify({
                "error": "Failed to retrieve assignment status"
            }), 500

        return jsonify({
            "assignments": assignments
        }), 200

    except Exception:
        app.logger.exception("Failed to track task status")

        return jsonify({
            "error": "Internal server error"
        }), 500


# ASSIGNMENTS - SUBMIT TASK

@app.route("/api/tasks/<task_id>/submit", methods=["POST"])
def submit_task_api(task_id):
    manager = Assignment()

    user_id, error = authenticate(
        manager,
        required_role="volunteer"
    )

    if error is not None:
        return error

    if not valid_uuid(task_id):
        return jsonify({"error": "Invalid task ID"}), 400

    try:
        result = manager.submit_task(user_id, task_id)

        if not result:
            return jsonify({
                "error": "Unable to submit task"
            }), 409

        return jsonify({
            "message": "Task submitted for admin review",
            "assignment": result
        }), 200

    except Exception:
        app.logger.exception("Submit task failed")
        return jsonify({
            "error": "Internal server error"
        }), 500

# ==========================================
# ASSIGNMENTS - UPLOAD PHOTO
# ==========================================

@app.route("/api/tasks/<task_id>/photo", methods=["POST"])
def upload_photo_api(task_id):
    manager = Assignment()

    user_id, error = authenticate(
        manager,
        required_role="volunteer"
    )

    if error is not None:
        return error

    if not valid_uuid(task_id):
        return jsonify({"error": "Invalid task ID"}), 400

    # Get photo from frontend
    photo = request.files.get("photo")

    if photo is None or not photo.filename:
        return jsonify({"error": "Photo is required"}), 400

    # Validate file type
    filename = secure_filename(photo.filename)
    allowed = {".jpg", ".jpeg", ".png", ".webp"}

    if Path(filename).suffix.lower() not in allowed:
        return jsonify({
            "error": "Only JPG, PNG and WEBP images are allowed"
        }), 400

    try:
        # A missing/finished assignment is a client-side workflow conflict,
        # rather than a Storage failure. RLS and the user ID scope this lookup.
        active = (
            manager.supabase.table("assignments")
            .select("id")
            .eq("task_id", task_id)
            .eq("volunteer_id", user_id)
            .eq("status", "assigned")
            .limit(1)
            .execute()
        )
        if not active.data:
            return jsonify({"error": "An active assignment is required to upload a photo"}), 409

        # Temporarily save the uploaded photo
        with TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / filename
            photo.save(file_path)

            # Call teammate's existing method
            photo_path = manager.upload_photo(
                user_id,
                task_id,
                str(file_path)
            )

        if not photo_path:
            return jsonify({
                "error": "Photo upload failed"
            }), 500

        return jsonify({
            "message": "Photo uploaded successfully",
            "photo_path": photo_path
        }), 200

    except Exception:
        app.logger.exception("Photo upload error")
        return jsonify({
            "error": "Internal server error"
        }), 500

# ==========================================
# ASSIGNMENTS - ADMIN VERIFICATION
# ==========================================

@app.route(
    "/api/assignments/<assignment_id>/verify",
    methods=["POST"]
)
def verify_delivery_api(assignment_id):
    manager = Assignment()

    # 1. Verify admin identity
    admin_id, error = authenticate(
        manager,
        required_role="admin"
    )

    if error is not None:
        return error

    # 2. Validate assignment ID
    if not valid_uuid(assignment_id):
        return jsonify({
            "error": "Invalid assignment ID"
        }), 400

    # 3. Get admin's decision
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Invalid JSON body"
        }), 400

    approved = data.get("approved")

    if not isinstance(approved, bool):
        return jsonify({
            "error": "Approved must be true or false"
        }), 400

    # 4. Call teammate's verification method
    try:
        result = manager.verify_delivery(
            admin_id,
            assignment_id,
            approved
        )

        if not result:
            return jsonify({
                "error": "Unable to verify assignment"
            }), 409

        return jsonify({
            "message": (
                "Assignment approved"
                if approved
                else "Assignment rejected"
            ),
            "assignment": result
        }), 200

    except Exception:
        app.logger.exception(
            "Assignment verification failed"
        )

        return jsonify({
            "error": "Internal server error"
        }), 500

# ==================================================
# RUN FLASK
# ==================================================

if __name__ == "__main__":
    app.run(debug=True, port=5050)
