from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
import mysql.connector
import smtplib, random, json, os, time, string, secrets
from email.message import EmailMessage
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "xaqt_wqzq_fqpb_ojnx"

# =========================
# UPLOAD FOLDERS
# =========================
UPLOAD_FOLDER = os.path.join('static', 'uploads')
CHAT_UPLOAD_FOLDER = os.path.join('static', 'chat_uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHAT_UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CHAT_UPLOAD_FOLDER'] = CHAT_UPLOAD_FOLDER

# =========================
# EMAIL CONFIGURATION
# =========================
EMAIL_ADDRESS = "tsada967@gmail.com"
EMAIL_PASSWORD = "xaqt wqzq fqpb ojnx"

def send_email(to_email, subject, body):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg.set_content(body)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)
    print("✅ Email sent to:", to_email)

# =========================
# DATABASE HELPERS
# =========================
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="sada123456@$",
        database="lost_found"
    )

def query_db(query, params=(), one=False):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # 🔥 FIX: force params to tuple ALWAYS
    if params is None:
        params = ()
    else:
        params = tuple(params)

    cursor.execute(query, params)
    result = cursor.fetchall()

    cursor.close()
    db.close()

    return (result[0] if result else None) if one else result

def execute_db(query, params=()):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(query, params)
    db.commit()
    cursor.close()
    db.close()
# =========================
# PASSWORD GENERATOR
# =========================
def generate_strong_password(length=12):
    characters = string.ascii_letters + string.digits + "!@#$%^&*()"
    return ''.join(secrets.choice(characters) for _ in range(length))


##Login Required Decorator
from functools import wraps
from flask import session, redirect, url_for

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):

        # ❌ Not logged in
        if "user_id" not in session:
            return redirect(url_for("login"))

        # 🔥 NEW: approval check
        user = query_db(
            "SELECT status FROM users WHERE id=%s",
            (session["user_id"],),
            one=True
        )

        # ❌ Not approved
        if not user or user["status"] != "approved":
            return redirect(url_for("pending"))

        # ✅ Allowed
        return f(*args, **kwargs)

    return wrapper

def get_user_by_id(user_id):
    return query_db(
        "SELECT * FROM users WHERE id = %s",
        (user_id,),
        one=True
    )
    
def calculate_completion(user):
    fields = ["name", "email", "profile_image"]

    filled = 0
    for field in fields:
        if user and user.get(field):
            filled += 1

    return int((filled / len(fields)) * 100)

def clean_items(items):
    for item in items:
        if not item.get('image'):
            item['image'] = 'default.png'   # fallback image
    return items

def get_block_status(user_id, other_user_id):

    block = query_db("""
        SELECT blocker_id, blocked_id
        FROM user_blocks
        WHERE (blocker_id=%s AND blocked_id=%s)
           OR (blocker_id=%s AND blocked_id=%s)
    """, (user_id, other_user_id, other_user_id, user_id))

    blocked_by_me = False
    blocked_by_other = False

    for b in block:
        if b["blocker_id"] == user_id:
            blocked_by_me = True
        if b["blocker_id"] == other_user_id:
            blocked_by_other = True

    return {
        "blocked_by_me": blocked_by_me,
        "blocked_by_other": blocked_by_other
    }
    
    
    
@app.context_processor
def inject_user():
    if "user_id" in session:
        user = query_db(
            "SELECT id, name, profile_image FROM users WHERE id=%s",
            (session["user_id"],),
            one=True
        )
    else:
        user = None

    return dict(user=user)
# =========================
# =========================
# INDEX / DASHBOARD
# =========================
@app.route("/")
def index():

    user = None

    if "user_id" in session:
        user = query_db("""
            SELECT id, name, profile_image
            FROM users
            WHERE id = %s
        """, (session["user_id"],), one=True)

    resolved_items = query_db("""
    SELECT 
        id,
        title,
        image,
        recovery_note AS note,
        recovered_at AS time,
        'recovered' AS type
    FROM lost_items
    WHERE status = 'recovered' AND recovered_at IS NOT NULL

    UNION ALL

    SELECT 
        id,
        title,
        image,
        return_note AS note,
        returned_at AS time,
        'returned' AS type
    FROM found_items
    WHERE status = 'returned' AND returned_at IS NOT NULL

    ORDER BY time DESC
""")

    return render_template(
        "index.html",
        resolved_items=resolved_items,
        user=user
    )
# =========================
# FAQ PAGE
# =========================
@app.route('/faq')
def faq():
    return render_template('faq.html')


# =========================
# PRIVACY POLICY PAGE
# =========================
@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')


# PROFILE IMAGE UPLOAD
# =========================
@app.route('/upload-profile', methods=['POST'])
@login_required
def upload_profile():

    user = query_db(
        "SELECT status FROM users WHERE id=%s",
        (session["user_id"],),
        one=True
    )

    if not user or user["status"] != "approved":
        return redirect('/')

    file = request.files.get('profile_image')

    if not file or file.filename == '':
        return redirect(request.referrer or '/profile')

    filename = f"user_{session['user_id']}_{secure_filename(file.filename)}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    execute_db(
        "UPDATE users SET profile_image=%s WHERE id=%s",
        (filename, session['user_id'])
    )

    return redirect(request.referrer or '/profile')

@app.route("/profile")
@login_required
def profile():
    user = get_user_by_id(session["user_id"])
    completion = calculate_completion(user)

    return render_template("profile.html", user=user, completion=completion)

@app.route("/update-profile", methods=["POST"])
@login_required
def update_profile():
    user_id = session["user_id"]

    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    department = request.form.get("department")
    address = request.form.get("address")
    bio = request.form.get("bio")

    execute_db("""
        UPDATE users 
        SET name=%s, email=%s, phone=%s, department=%s, address=%s, bio=%s
        WHERE id=%s
    """, (name, email, phone, department, address, bio, user_id))

    # 🔥 GO TO INDEX PAGE
    return redirect("/")

# =========================
# =========================
# SIGNUP
# =========================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        student_card = request.files.get("student_card")

        # ❌ File check
        if not student_card or student_card.filename == "":
            flash("Please upload your student card.", "error")
            return redirect(url_for("signup"))

        # ❌ Email exists check
        if query_db("SELECT * FROM users WHERE email=%s", (email,), one=True):
            flash("Email already exists!", "error")
            return redirect(url_for("signup"))

        # ✅ Save student card
        filename = f"card_{secure_filename(student_card.filename)}"
        student_card.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        # 🔐 Generate OTP + password
        suggested_password = generate_strong_password()
        otp = str(random.randint(100000, 999999))

        # 💾 Save temp data in session
        session['signup_name'] = name
        session['signup_email'] = email
        session['signup_file'] = filename
        session['signup_otp'] = otp

        # 📧 Send email
        send_email(
            email,
            "Lost & Found - Enter Your Password",
            f"Hello {name},\n\n"
            f"Suggested Password: {suggested_password}\n"
            f"Your OTP is: {otp}\n\n"
            f"Enter OTP and set your password to complete signup."
        )

        # 👉 Move to password + OTP page
        return redirect(url_for("set_password"))

    return render_template("signup.html")
# =========================
# SET PASSWORD
# =========================
@app.route("/set-password", methods=["GET", "POST"])
def set_password():

    if 'signup_otp' not in session:
        return redirect("/signup")

    if request.method == "POST":
        otp_input = request.form.get("otp")

        if otp_input != session.get('signup_otp'):
            flash("Invalid OTP", "error")
            return render_template("set_password.html")

        # ✅ OTP correct → move to password page
        session['otp_verified'] = True
        return redirect(url_for("create_password"))

    return render_template("set_password.html")
# =========================
@app.route("/create_password", methods=["GET", "POST"])
def create_password():

    if not session.get("otp_verified"):
        return redirect("/signup")

    if request.method == "POST":
        password = request.form.get("password")

        if not password or len(password) < 6:
            flash("Password must be at least 6 characters", "error")
            return render_template("create_password.html")

        hashed_password = generate_password_hash(password)

        execute_db(
            "INSERT INTO users (name, email, password, student_card, status, is_verified) "
            "VALUES (%s, %s, %s, %s, 'pending', 0)",
            (
                session['signup_name'],
                session['signup_email'],
                hashed_password,
                session['signup_file']
            )
        )

        user = query_db(
            "SELECT id FROM users WHERE email=%s",
            (session['signup_email'],),
            one=True
        )

        session["user_id"] = user["id"]

        session.pop('signup_name', None)
        session.pop('signup_email', None)
        session.pop('signup_file', None)
        session.pop('signup_otp', None)
        session.pop('otp_verified', None)

        flash("Account created successfully!", "success")
        return redirect("/")

    # ✅ THIS LINE FIXED
    return render_template("create_password.html")
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        email = request.form["email"].strip().lower()
        password = request.form["password"].strip()

        user = query_db(
            "SELECT * FROM users WHERE email=%s",
            (email,),
            one=True
        )

        if not user:
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        if not check_password_hash(user['password'], password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        if user['is_verified'] != 1:
            session['verify_email'] = email
            return redirect(url_for("verify_email"))

        if user['status'] != 'approved':
            session["user_id"] = user["id"]
            return redirect("/pending")

        session["user_id"] = user["id"]
        session["username"] = user["name"]

        return redirect(url_for("index"))

    return render_template("login.html")

# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# =========================
# FORGOT / RESET PASSWORD
# =========================
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]
        user = query_db("SELECT * FROM users WHERE email=%s", (email,), one=True)
        if user:
            otp = str(random.randint(100000, 999999))
            execute_db("UPDATE users SET otp=%s WHERE email=%s", (otp, email))
            send_email(email, "Password Reset OTP - Lost & Found", f"Hello {user['name']},\nYour OTP is: {otp}")
            session['reset_email'] = email
            flash("OTP sent to your email.", "info")
            return redirect(url_for("verify_otp"))
        else:
            flash("Email not found.", "error")
    return render_template("forgot_password.html")

@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if 'reset_email' not in session:
        return redirect(url_for("forgot_password"))
    email = session['reset_email']
    if request.method == "POST":
        otp = request.form["otp"]
        user = query_db("SELECT * FROM users WHERE email=%s AND otp=%s", (email, otp), one=True)
        if user:
            session['change_pass_email'] = email
            execute_db("UPDATE users SET otp=NULL WHERE email=%s", (email,))
            return redirect(url_for("reset_password"))
        else:
            flash("Invalid OTP.", "error")
    return render_template("verify_otp.html")

@app.route("/resend-otp", methods=["GET", "POST"])
def resend_otp():
    if 'reset_email' not in session:
        return redirect(url_for("forgot_password"))

    email = session['reset_email']

    if request.method == "POST":
        # Generate a new 6-digit OTP
        import random
        otp = f"{random.randint(0, 999999):06}"
        
        # Save it to database
        execute_db("UPDATE users SET otp=%s WHERE email=%s", (otp, email))
        
        # Send OTP via email (use your mail sending function)
        send_email(email, "Your OTP Code", f"Your new OTP is: {otp}")

        flash("A new OTP has been sent to your email.", "success")
        return redirect(url_for("verify_otp"))

    return render_template("resend_otp.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if 'change_pass_email' not in session:
        return redirect(url_for("index"))  # no pending reset, go to index

    email = session['change_pass_email']

    if request.method == "POST":
        password = request.form["password"]
        hashed_password = generate_password_hash(password)

        # Update password in database
        execute_db(
            "UPDATE users SET password=%s WHERE email=%s",
            (hashed_password, email)
        )

        # Fetch the user to log in
        user = query_db("SELECT * FROM users WHERE email=%s", (email,), one=True)
        if user:
            session['user_id'] = user['id']  # log the user in
            # Optional: session['email'] = user['email']

        session.pop('change_pass_email')  # remove temp reset marker
        flash("Password reset successfully! You are now logged in.", "success")
        return redirect(url_for("index"))

    return render_template("reset_password.html")

@app.route("/skip-reset")
def skip_reset():
    # Check if there is a pending password reset session
    if 'change_pass_email' in session:
        email = session['change_pass_email']
        # Fetch user by email
        user = query_db("SELECT * FROM users WHERE email=%s", (email,), one=True)
        if user:
            session['user_id'] = user['id']  # log the user in
            # Optional: store more info if exists, e.g., session['email'] = user['email']
        session.pop('change_pass_email')  # remove temporary reset marker
    return redirect(url_for("index"))

@app.route("/pending")
def pending():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = query_db(
        "SELECT status FROM users WHERE id=%s",
        (session["user_id"],),
        one=True
    )

    if not user:
        session.clear()
        return redirect(url_for("login"))

    # ✅ if approved → no pending page
    if user["status"] == "approved":
        return redirect(url_for("index"))

    return render_template("pending.html")
@app.route("/force-home")
def force_home():
    return redirect(url_for("index"))

@app.route("/check-status")
def check_status():
    if "user_id" not in session:
        return {"status": "guest"}

    user = query_db(
        "SELECT status FROM users WHERE id=%s",
        (session["user_id"],),
        one=True
    )

    if not user:
        return {"status": "unknown"}

    return {"status": user["status"]}
# =========================
# REPORT LOST / FOUND
# =========================
@app.route('/report-lost', methods=['GET', 'POST'])
def report_lost():
    # 🔐 Login check
    if 'user_id' not in session:
        return redirect('/login')

    # 🔥 Check user approval status
    user = query_db(
        "SELECT status FROM users WHERE id=%s",
        (session['user_id'],),
        one=True
    )

    if not user or user['status'] != 'approved':
        return redirect('/pending')

    # ✅ POST request
    if request.method == 'POST':
        title = request.form['title']
        category = request.form['category']
        location = request.form['location']
        lost_date = request.form['lost_date']
        description = request.form['description']

        image = request.files.get('image')
        filename = None

        # 📸 Image handling
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        # 💾 Insert into DB
        execute_db("""
            INSERT INTO lost_items 
            (user_id, title, category, location, lost_date, description, image)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            session['user_id'],
            title,
            category,
            location,
            lost_date,
            description,
            filename
        ))

        
        return redirect('/')

    return render_template('report_lost.html')
from datetime import datetime, timedelta
from flask import session

@app.route("/view-lost")
def view_lost():
    user_id = session.get("user_id")
    q = request.args.get("q", "").strip()

    query = """
        SELECT lost_items.*, users.name AS username, users.profile_image
        FROM lost_items
        JOIN users ON lost_items.user_id = users.id
        WHERE lost_items.status = 'lost'
    """

    values = []

    if q:
        search = f"%{q}%"
        query += """
            AND (
                LOWER(users.name) LIKE LOWER(%s) OR
                LOWER(lost_items.title) LIKE LOWER(%s) OR
                LOWER(lost_items.category) LIKE LOWER(%s) OR
                LOWER(lost_items.location) LIKE LOWER(%s) OR
                LOWER(lost_items.description) LIKE LOWER(%s) OR
                DATE_FORMAT(lost_items.lost_date, '%%Y-%%m-%%d') LIKE %s
            )
        """
        values.extend([search, search, search, search, search, search])

    query += " ORDER BY lost_items.created_at DESC"

    items = query_db(query, tuple(values))

    return render_template(
        "view_lost.html",
        items=items,
        current_user_id=user_id,
        search=q
    )
    
@app.route("/view-lost-data")
def view_lost_data():
    q = request.args.get("q", "").strip()

    query = """
        SELECT lost_items.*, users.name AS username, users.profile_image, users.email
        FROM lost_items
        JOIN users ON lost_items.user_id = users.id
        WHERE lost_items.status = 'lost'
    """

    values = []

    if q:
        search = f"%{q}%"

        query += """
            AND (
                LOWER(users.name) LIKE LOWER(%s) OR
                LOWER(lost_items.title) LIKE LOWER(%s) OR
                LOWER(lost_items.category) LIKE LOWER(%s) OR
                LOWER(lost_items.location) LIKE LOWER(%s) OR
                LOWER(lost_items.description) LIKE LOWER(%s) OR

                CAST(lost_items.lost_date AS CHAR) LIKE %s
            )
        """

        values.extend([search, search, search, search, search, search])

    query += " ORDER BY lost_items.created_at DESC"

    items = query_db(query, tuple(values))

    return render_template(
        "partials/lost_items_cards.html",
        items=items
    )
    
@app.route("/chat/<int:other_user_id>")
def chat(other_user_id):

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    
    execute_db("""
        UPDATE messages
        SET is_read = 1
        WHERE sender_id = %s
          AND receiver_id = %s
          AND is_read = 0
    """, (other_user_id, user_id))

    if user_id == other_user_id:
        return redirect("/")

    partner = query_db(
        "SELECT id, name, profile_image FROM users WHERE id=%s",
        (other_user_id,),
        one=True
    )

    if not partner:
        return "User not found", 404

    block_status = get_block_status(user_id, other_user_id)

    # 🔥 FIX: FILTER DELETED MESSAGES HERE
    messages = query_db("""
        SELECT * FROM messages
        WHERE
            (
                (sender_id=%s AND receiver_id=%s)
                OR
                (sender_id=%s AND receiver_id=%s)
            )
            AND (
                deleted_by_user IS NULL
                OR JSON_CONTAINS(deleted_by_user, %s) = 0
            )
        ORDER BY created_at ASC
    """, (
        user_id, other_user_id,
        other_user_id, user_id,
        str(user_id)
    ))

    chat_disabled = block_status["blocked_by_me"] or block_status["blocked_by_other"]

    return render_template(
        "chat.html",
        partner=partner,
        messages=messages,
        blocked_by_me=block_status["blocked_by_me"],
        blocked_by_other=block_status["blocked_by_other"],
        chat_disabled=chat_disabled
    )
    
@app.route("/send-message/<int:receiver_id>", methods=["POST"])
def send_message(receiver_id):

    if "user_id" not in session:
        return jsonify({"success": False}), 401

    sender_id = session["user_id"]

    message = request.form.get("message", "")
    image = request.files.get("image")

    print("MESSAGE =", message)
    print("IMAGE =", image)

    filename = None

    if image and image.filename != "":
        from werkzeug.utils import secure_filename
        import os

        filename = secure_filename(image.filename)

        save_path = os.path.join(
            app.config["CHAT_UPLOAD_FOLDER"],
            filename
        )

        print("SAVE PATH =", save_path)

        image.save(save_path)

    execute_db("""
        INSERT INTO messages(sender_id, receiver_id, message, image)
        VALUES(%s,%s,%s,%s)
    """, (sender_id, receiver_id, message, filename))

    return jsonify({
        "success": True,
        "image": filename
    })
    
@app.route("/fetch-new-messages/<int:other_user_id>/<int:last_id>")
def fetch_new_messages(other_user_id, last_id):

    if "user_id" not in session:
        return jsonify({"messages": []})

    user_id = session["user_id"]

    messages = query_db("""
        SELECT *
        FROM messages
        WHERE
        (
            (sender_id=%s AND receiver_id=%s)
            OR
            (sender_id=%s AND receiver_id=%s)
        )
        AND id > %s
        ORDER BY id ASC
    """, (
        user_id, other_user_id,
        other_user_id, user_id,
        last_id
    ))

    return jsonify({"messages": messages})
# =========================
# INBOX
# =========================
@app.route("/inbox")
def inbox():
    if "user_id" not in session:
        return redirect("/login")

    # 🔥 NEW: approval check
    user = query_db(
        "SELECT status FROM users WHERE id=%s",
        (session["user_id"],),
        one=True
    )
    if not user or user["status"] != "approved":
        return redirect("/pending")

    user_id = session["user_id"]

    chat_users = query_db("""
        SELECT 
            u.id, u.name, u.profile_image,
            COUNT(CASE WHEN m.is_read=0 THEN 1 END) AS unread_count,
            MAX(m.created_at) AS last_message_time
        FROM users u
        JOIN messages m ON (u.id = m.sender_id OR u.id = m.receiver_id)
        WHERE u.id != %s
          AND (m.sender_id=%s OR m.receiver_id=%s)
          AND (m.deleted_by_user IS NULL OR JSON_CONTAINS(m.deleted_by_user, %s) = 0)
        GROUP BY u.id
        ORDER BY last_message_time DESC
    """, (user_id, user_id, user_id, json.dumps(user_id)))

    return render_template("inbox.html", chat_users=chat_users)


# =========================
# DELETE MESSAGES
# =========================
@app.route("/delete-messages", methods=["POST"])
def delete_messages():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Unauthorized"})

    user_id = session["user_id"]

    data = request.get_json(silent=True) or {}
    message_ids = data.get("message_ids", [])

    if not message_ids:
        return jsonify({"success": False, "error": "No messages selected"})

    message_ids = list(map(int, message_ids))

    for msg_id in message_ids:

        row = query_db(
            "SELECT deleted_by_user FROM messages WHERE id=%s",
            (msg_id,),
            one=True
        )

        if not row:
            continue

        deleted_list = []

        if row["deleted_by_user"]:
            deleted_list = json.loads(row["deleted_by_user"])

        # add current user only
        if user_id not in deleted_list:
            deleted_list.append(user_id)

        execute_db(
            "UPDATE messages SET deleted_by_user=%s WHERE id=%s",
            (json.dumps(deleted_list), msg_id)
        )

    return jsonify({"success": True})
# =========================
# DELETE CHAT WITH A USER
# =========================
@app.route("/delete-chat", methods=["POST"])
def delete_chat():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"})

    user_id = session["user_id"]
    other_user_id = request.get_json().get("other_user_id")

    if not other_user_id:
        return jsonify({"success": False, "error": "No user specified"})

    messages = query_db("""
        SELECT id, deleted_by_user
        FROM messages
        WHERE (sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s)
    """, (user_id, other_user_id, other_user_id, user_id))

    for msg in messages:
        deleted_list = json.loads(msg["deleted_by_user"]) if msg["deleted_by_user"] else []
        if user_id not in deleted_list:
            deleted_list.append(user_id)
        execute_db("UPDATE messages SET deleted_by_user=%s WHERE id=%s", (json.dumps(deleted_list), msg["id"]))

    return jsonify({"success": True})

# =========================
# DELETE MULTIPLE CHATS
# =========================
@app.route("/delete-chats", methods=["POST"])
def delete_chats():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"})

    user_id = session["user_id"]
    chat_ids = request.get_json().get("chat_ids", [])

    for other_user_id in chat_ids:
        messages = query_db("""
            SELECT id, deleted_by_user
            FROM messages
            WHERE (sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s)
        """, (user_id, other_user_id, other_user_id, user_id))

        for msg in messages:
            deleted_list = json.loads(msg["deleted_by_user"]) if msg["deleted_by_user"] else []
            if user_id not in deleted_list:
                deleted_list.append(user_id)
            execute_db("UPDATE messages SET deleted_by_user=%s WHERE id=%s", (json.dumps(deleted_list), msg["id"]))

    return jsonify({"success": True})

# =========================
@app.route("/fetch-inbox")
def fetch_inbox():
    if "user_id" not in session:
        return jsonify({"chat_users": []})

    user_id = session["user_id"]

    chat_users = query_db("""
        SELECT 
            u.id,
            u.name,
            u.profile_image,

            -- 🔥 ONLY unread for CURRENT USER as RECEIVER
            COUNT(
                CASE 
                    WHEN m.is_read = 0 AND m.receiver_id = %s 
                    THEN 1 
                END
            ) AS unread_count,

            MAX(m.created_at) AS last_message_time

        FROM users u
        JOIN messages m 
            ON (u.id = m.sender_id OR u.id = m.receiver_id)

        WHERE u.id != %s
          AND (m.sender_id = %s OR m.receiver_id = %s)
          AND (m.deleted_by_user IS NULL 
               OR JSON_CONTAINS(m.deleted_by_user, %s) = 0)

        GROUP BY u.id
        ORDER BY last_message_time DESC
    """, (
        user_id,
        user_id,
        user_id,
        user_id,
        json.dumps(user_id)
    ))

    for u in chat_users:
        u["profile_image"] = (
            url_for("static", filename="uploads/" + u["profile_image"])
            if u["profile_image"] else None
        )

    return jsonify({"chat_users": chat_users})


@app.route("/fetch-messages/<int:other_user_id>")
def fetch_messages(other_user_id):
    if "user_id" not in session:
        return jsonify({"messages": []})

    user_id = session["user_id"]

    messages = query_db("""
        SELECT * FROM messages
        WHERE
            (
                (sender_id=%s AND receiver_id=%s)
                OR
                (sender_id=%s AND receiver_id=%s)
            )
            AND (
                deleted_by_user IS NULL
                OR JSON_CONTAINS(deleted_by_user, %s) = 0
            )
        ORDER BY created_at
    """, (
        user_id, other_user_id,
        other_user_id, user_id,
        str(user_id)
    ))

    formatted = []
    for msg in messages:
        formatted.append({
            "id": msg["id"],
            "sender_id": msg["sender_id"],
            "message": msg["message"],
            "image": ("/static/chat_uploads/" + msg["image"]) if msg["image"] else None,
            "created_at": msg["created_at"].strftime("%I:%M %p")
        })

    return jsonify({"messages": formatted})

@app.route("/chat/block/<int:user_id>", methods=["POST"])
def chat_block_user(user_id):

    if "user_id" not in session:
        return redirect("/login")

    current_user = session["user_id"]

    existing = query_db("""
        SELECT id FROM user_blocks
        WHERE blocker_id=%s AND blocked_id=%s
    """, (current_user, user_id), one=True)

    if existing:
        # 🔄 UNBLOCK
        execute_db("""
            DELETE FROM user_blocks
            WHERE blocker_id=%s AND blocked_id=%s
        """, (current_user, user_id))
    else:
        # 🚫 BLOCK
        execute_db("""
            INSERT INTO user_blocks (blocker_id, blocked_id)
            VALUES (%s, %s)
        """, (current_user, user_id))

    return redirect(request.referrer or f"/user/{user_id}")

@app.route("/chat/unblock/<int:user_id>", methods=["POST"])
def chat_unblock_user(user_id):
    if "user_id" not in session:
        return redirect("/login")

    current_user = session["user_id"]

    execute_db("""
        DELETE FROM user_blocks
        WHERE blocker_id=%s AND blocked_id=%s
    """, (current_user, user_id))

    return redirect(request.referrer or "/")

# ✅ USER PROFILE
@app.route("/user/<int:user_id>")
def public_profile(user_id):

    if "user_id" not in session:
        return redirect("/login")

    # ❌ BLOCK: agar user apni profile open kare
    if session["user_id"] == user_id:
        return redirect(url_for("profile"))  # ya "/" ya blank page

    user = query_db("""
        SELECT id, name, email, phone, profile_image, bio, address, department
        FROM users
        WHERE id=%s
    """, (user_id,), one=True)

    if not user:
        return "User not found", 404

    # safe image
    user["profile_image_url"] = (
        url_for("static", filename="uploads/" + user["profile_image"])
        if user.get("profile_image")
        else url_for("static", filename="images/default_user.png")
    )

    block_status = get_block_status(session["user_id"], user_id)

    return render_template(
        "user_public_profile.html",
        user=user,
        blocked_by_me=block_status["blocked_by_me"],
        blocked_by_other=block_status["blocked_by_other"],
        show_block_button=True
    )
    
#report found
@app.route('/report-found', methods=['GET', 'POST'])
def report_found():
    # 🔐 Login check
    if 'user_id' not in session:
        return redirect('/login')

    # 🔥 Approval check (MOST IMPORTANT)
    user = query_db(
        "SELECT status FROM users WHERE id=%s",
        (session['user_id'],),
        one=True
    )

    if not user or user['status'] != 'approved':
        return redirect('/pending')

    # ✅ Handle form
    if request.method == 'POST':
        title = request.form['title']
        category = request.form['category']
        location = request.form['location']
        found_date = request.form['found_date']
        description = request.form['description']

        image = request.files.get('image')
        filename = None

        # 📸 Safe image upload
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        # 💾 Insert into DB
        execute_db("""
            INSERT INTO found_items 
            (user_id, title, category, location, found_date, description, image)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            session['user_id'],
            title,
            category,
            location,
            found_date,
            description,
            filename
        ))

        
        return redirect('/')

    return render_template('report_found.html')
# VIEW FOUND ITEMS PAGE
@app.route("/view-found")
def view_found():
    user_id = session.get("user_id")
    q = request.args.get("q", "").strip()

    query = """
        SELECT found_items.*,
               users.name AS username,
               users.profile_image
        FROM found_items
        JOIN users ON found_items.user_id = users.id
        WHERE found_items.status = 'found'
    """

    values = []

    if q:
        search = f"%{q}%"
        query += """
            AND (
                LOWER(users.name) LIKE LOWER(%s) OR
                LOWER(found_items.title) LIKE LOWER(%s) OR
                LOWER(found_items.category) LIKE LOWER(%s) OR
                LOWER(found_items.location) LIKE LOWER(%s) OR
                LOWER(found_items.description) LIKE LOWER(%s) OR
                DATE_FORMAT(found_items.found_date, '%%Y-%%m-%%d') LIKE %s
            )
        """
        values.extend([search, search, search, search, search, search])

    query += " ORDER BY found_items.created_at DESC"

    items = query_db(query, tuple(values))

    return render_template(
        "view_found.html",
        items=items,
        current_user_id=user_id,
        search=q
    )
    
@app.route("/view-found-data")
def view_found_data():
    q = request.args.get("q", "").strip()

    query = """
        SELECT found_items.*,
               users.name AS username,
               users.profile_image,
               users.email
        FROM found_items
        JOIN users ON found_items.user_id = users.id
        WHERE found_items.status = 'found'
    """

    values = []

    if q:
        search = f"%{q}%"

        query += """
            AND (
                LOWER(users.name) LIKE LOWER(%s) OR
                LOWER(found_items.title) LIKE LOWER(%s) OR
                LOWER(found_items.category) LIKE LOWER(%s) OR
                LOWER(found_items.location) LIKE LOWER(%s) OR
                LOWER(found_items.description) LIKE LOWER(%s) OR
                LOWER(CAST(found_items.found_date AS CHAR)) LIKE LOWER(%s)
            )
        """

        values = [search, search, search, search, search, search]

    query += " ORDER BY found_items.created_at DESC"

    items = query_db(query, tuple(values))

    return render_template(
        "partials/found_items_cards.html",
        items=items
    )
from flask import request, render_template

@app.route("/search-items")
def search_items():
    q = request.args.get("q", "").strip()

    if not q:
        return render_template("partials/search_results.html",
                               lost_items=[],
                               found_items=[])

    keywords = q.split()

    lost_items = []
    found_items = []

    # ================= LOST =================
    lost_query = """
        SELECT id, title, image, category, location, description, lost_date
        FROM lost_items
        WHERE 1=1
    """

    lost_params = []

    for word in keywords:
        like = f"%{word}%"
        lost_query += """
            AND (
                title LIKE %s OR
                category LIKE %s OR
                location LIKE %s OR
                description LIKE %s
            )
        """
        lost_params.extend([like, like, like, like])

    lost_items = query_db(lost_query, tuple(lost_params))

    # ================= FOUND =================
    found_query = """
        SELECT id, title, image, category, location, description, found_date
        FROM found_items
        WHERE 1=1
    """

    found_params = []

    for word in keywords:
        like = f"%{word}%"
        found_query += """
            AND (
                title LIKE %s OR
                category LIKE %s OR
                location LIKE %s OR
                description LIKE %s
            )
        """
        found_params.extend([like, like, like, like])

    found_items = query_db(found_query, tuple(found_params))

    return render_template(
        "partials/search_results.html",
        lost_items=lost_items,
        found_items=found_items
    )
    
@app.route("/lost-details/<int:id>")
def lost_details(id):

    item = query_db("""
        SELECT 
            lost_items.*,
            users.name AS username,
            users.profile_image,
            users.email
        FROM lost_items
        JOIN users ON lost_items.user_id = users.id
        WHERE lost_items.id=%s
    """, (id,), one=True)

    if not item:
        return "Item not found", 404

    return render_template("view_lost.html", items=[item])

@app.route("/found-details/<int:id>")
def found_details(id):

    item = query_db("""
        SELECT 
            found_items.*,
            users.name AS username,
            users.profile_image,
            users.email
        FROM found_items
        JOIN users ON found_items.user_id = users.id
        WHERE found_items.id=%s
    """, (id,), one=True)

    if not item:
        return "Item not found", 404

    return render_template("view_found.html", items=[item])

@app.route("/guidelines")
def guidelines():
    # Agar chaho user info bhejna (optional)
    user = None
    if "user_id" in session:
        user = query_db("SELECT * FROM users WHERE id=%s", (session["user_id"],), one=True)
    
    return render_template("guidelines.html", user=user)
@app.route("/contact")
@login_required
def contact():
    return render_template("contact_us.html")

@app.route("/contact_admin", methods=["POST"])
@login_required
def contact_admin():
    user_id = session.get("user_id")
    subject = request.form["subject"]
    message = request.form["message"]

    execute_db(
        "INSERT INTO admin_messages (user_id, subject, message) VALUES (%s, %s, %s)",
        (user_id, subject, message)
    )

    flash("Message sent to admin successfully!", "success")

    return redirect(url_for("contact"))

# MY REPORTS PAGE
from datetime import datetime, timedelta
from flask import request, redirect, render_template

@app.route("/my-reports")
def my_reports():
    user_id = session.get("user_id")

    # 🔐 Login check
    if not user_id:
        return redirect("/login")

    # 🔥 Approval check (IMPORTANT)
    user = query_db(
        "SELECT status FROM users WHERE id=%s",
        (user_id,),
        one=True
    )

    if not user or user["status"] != "approved":
        return redirect("/pending")

    # 📌 Lost items
    lost_items_query = """
        SELECT lost_items.*, users.name AS username, users.profile_image
        FROM lost_items
        JOIN users ON lost_items.user_id = users.id
        WHERE lost_items.user_id=%s
        ORDER BY lost_items.created_at DESC
    """
    lost_items = query_db(lost_items_query, (user_id,))

    # 📌 Found items
    found_items_query = """
        SELECT found_items.*, users.name AS username, users.profile_image
        FROM found_items
        JOIN users ON found_items.user_id = users.id
        WHERE found_items.user_id=%s
        ORDER BY found_items.created_at DESC
    """
    found_items = query_db(found_items_query, (user_id,))

    return render_template(
        "my_reports.html",
        lost_items=lost_items,
        found_items=found_items
    )

from werkzeug.utils import secure_filename
import os

@app.route('/edit-report/<item_type>/<int:item_id>', methods=['GET', 'POST'])
def edit_report(item_type, item_id):
    if 'user_id' not in session:
        return redirect('/login')

    # GET ITEM
    if item_type == 'lost':
        item = query_db(
            "SELECT * FROM lost_items WHERE id=%s AND user_id=%s",
            (item_id, session['user_id']),
            one=True
        )
    else:
        item = query_db(
            "SELECT * FROM found_items WHERE id=%s AND user_id=%s",
            (item_id, session['user_id']),
            one=True
        )

    if not item:
        return redirect(url_for('my_reports'))

    if request.method == 'POST':
        title = request.form['title']
        category = request.form['category']
        location = request.form['location']
        description = request.form['description']
        date = request.form['date']

        # 🔥 IMAGE HANDLE
        image = request.files.get('image')
        filename = item['image']  # default = old image

        if image and image.filename != '':
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        if item_type == 'lost':
            execute_db("""
                UPDATE lost_items
                SET title=%s, category=%s, location=%s,
                    description=%s, lost_date=%s, image=%s
                WHERE id=%s AND user_id=%s
            """, (title, category, location, description, date, filename, item_id, session['user_id']))
        else:
            execute_db("""
                UPDATE found_items
                SET title=%s, category=%s, location=%s,
                    description=%s, found_date=%s, image=%s
                WHERE id=%s AND user_id=%s
            """, (title, category, location, description, date, filename, item_id, session['user_id']))

        
        return redirect(url_for('my_reports'))

    return render_template('edit_report.html', item=item, item_type=item_type)

@app.route('/delete-report/<item_type>/<int:item_id>', methods=['POST'])
def delete_report(item_type, item_id):
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']

    table = 'lost_items' if item_type == 'lost' else 'found_items'
    execute_db(f"DELETE FROM {table} WHERE id=%s AND user_id=%s", (item_id, user_id))
    return redirect(url_for('my_reports'))



from datetime import datetime

@app.route("/recover-lost/<int:item_id>", methods=["POST"])
def recover_lost(item_id):

    note = request.form.get("note") or ""

    query_db("""
        UPDATE lost_items
        SET status = 'recovered',
            recovery_note = %s,
            recovered_at = NOW()
        WHERE id = %s
    """, (note, item_id))

    return {"success": True}
@app.route("/undo-lost/<int:item_id>", methods=["POST"])
def undo_lost(item_id):

    if "user_id" not in session:
        return {"success": False}, 401

    execute_db("""
        UPDATE lost_items
        SET status='lost',
            recovery_note=NULL,
            recovered_at=NULL
        WHERE id=%s AND user_id=%s
    """, (item_id, session["user_id"]))

    return {"success": True}

@app.route("/return-found/<int:item_id>", methods=["POST"])
def return_found(item_id):

    if "user_id" not in session:
        return {"success": False}, 401

    note = request.form.get("note") or ""

    execute_db("""
        UPDATE found_items
        SET status = 'returned',
            return_note = %s,
            returned_at = NOW()
        WHERE id = %s AND user_id = %s
    """, (note, item_id, session["user_id"]))

    return {"success": True}

@app.route("/undo-found/<int:item_id>", methods=["POST"])
def undo_found(item_id):

    if "user_id" not in session:
        return {"success": False}, 401

    execute_db("""
        UPDATE found_items
        SET status='found',
            returned_at=NULL
        WHERE id=%s AND user_id=%s
    """, (item_id, session["user_id"]))

    return {"success": True}
# -----------------------------
# DUMMY ADMIN
# -----------------------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$CcduAqtrVRMbEIHY$b881438a786ef2fb592e4e7ed3fc8019a2e5821fdec4860d4f5b1bff77717afe255f66ed3e3e7298173687137f3b71ea0c3cfe7d8a2e7df21eab164946f0c4fa"
# password = admin123

# -----------------------------
# DB HELPER FUNCTIONS
# -----------------------------
import mysql.connector

conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='sada123456@$',
    database='lost_found'
)

def query_db(query, args=(), one=False):
    cur = conn.cursor(dictionary=True)
    cur.execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return rv[0] if one and rv else rv

def execute_db(query, args=()):
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    cur.close()

# -----------------------------
# ADMIN LOGIN DECORATOR
# -----------------------------
from functools import wraps

def admin_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapper


# ADMIN LOGIN / LOGOUT
# =============================
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Admin credentials check
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid admin credentials", "error")
            return render_template('admin_login.html')

    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


# =============================
# ADMIN LOGIN REQUIRED DECORATOR
# =============================
from functools import wraps

def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Admin login required!", "error")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function
# =============================
# DASHBOARD
@app.route("/admin/dashboard")
@admin_login_required
def admin_dashboard():

    # 👤 Approved users only
    total_users = query_db(
        "SELECT COUNT(*) as count FROM users WHERE status='approved'",
        one=True
    )['count']

    # ⏳ Pending requests
    pending_requests = query_db(
        "SELECT COUNT(*) as count FROM users WHERE status='pending'",
        one=True
    )['count']

    # 📦 Lost items
    total_lost = query_db(
        "SELECT COUNT(*) as count FROM lost_items",
        one=True
    )['count']

    # 📦 Found items
    total_found = query_db(
        "SELECT COUNT(*) as count FROM found_items",
        one=True
    )['count']

    # ✅ Resolved items
    recovered_lost = query_db(
        "SELECT COUNT(*) as count FROM lost_items WHERE status='recovered'",
        one=True
    )['count']

    returned_found = query_db(
        "SELECT COUNT(*) as count FROM found_items WHERE status='returned'",
        one=True
    )['count']

    total_resolved = recovered_lost + returned_found

    # 📅 Today stats
    today_lost = query_db(
        "SELECT COUNT(*) as count FROM lost_items WHERE DATE(created_at)=CURDATE()",
        one=True
    )['count']

    today_found = query_db(
        "SELECT COUNT(*) as count FROM found_items WHERE DATE(created_at)=CURDATE()",
        one=True
    )['count']

    # 🔥 NEW: Today's resolved
    today_resolved = query_db("""
        SELECT 
            (SELECT COUNT(*) FROM lost_items 
             WHERE status='recovered' AND DATE(recovered_at)=CURDATE())
            +
            (SELECT COUNT(*) FROM found_items 
             WHERE status='returned' AND DATE(returned_at)=CURDATE())
        AS count
    """, one=True)['count']

    # 📩 Total messages
    total_messages = query_db(
        "SELECT COUNT(*) as count FROM admin_messages",
        one=True
    )['count']

    # 📬 Unread messages
    unread_messages = query_db(
        "SELECT COUNT(*) as count FROM admin_messages WHERE is_read=0",
        one=True
    )['count']

    # 👤 Active users
    active_users = query_db(
        "SELECT COUNT(*) as count FROM users WHERE is_verified=1",
        one=True
    )['count']

    return render_template(
        "admin_dashboard.html",
        admin_name=session.get("admin_name"),

        total_users=total_users,
        pending_requests=pending_requests,

        total_lost=total_lost,
        total_found=total_found,
        total_resolved=total_resolved,

        today_lost=today_lost,
        today_found=today_found,

        # 🔥 NEW STATS
        today_resolved=today_resolved,
        total_messages=total_messages,
        unread_messages=unread_messages,
        active_users=active_users
    )
# =============================
# ADMIN USERS ROUTES
# =============================
@app.route('/admin/users')
@admin_login_required
def admin_users():
    q = request.args.get('q', '').strip()

    if q:
        like_q = f"%{q}%"
        users = query_db("""
            SELECT * FROM users 
            WHERE (name LIKE %s OR email LIKE %s)
            AND status='approved'
            ORDER BY created_at DESC
        """, (like_q, like_q))
    else:
        users = query_db("""
            SELECT * FROM users 
            WHERE status='approved'
            ORDER BY created_at DESC
        """)

    return render_template('admin_users.html', users=users, admin_name="Admin Sada")
@app.route('/admin/block-user/<int:user_id>')
@admin_login_required
def block_user(user_id):
    execute_db("UPDATE users SET is_verified=0 WHERE id=%s", (user_id,))
    return redirect(url_for('admin_users'))

@app.route('/admin/unblock-user/<int:user_id>')
@admin_login_required
def unblock_user(user_id):
    execute_db("UPDATE users SET is_verified=1 WHERE id=%s", (user_id,))
    return redirect(url_for('admin_users'))

@app.route('/admin/delete-user/<int:user_id>')
@admin_login_required
def delete_user(user_id):
    execute_db("DELETE FROM lost_items WHERE user_id=%s", (user_id,))
    execute_db("DELETE FROM found_items WHERE user_id=%s", (user_id,))
    execute_db("DELETE FROM messages WHERE sender_id=%s OR receiver_id=%s", (user_id, user_id))
    execute_db("DELETE FROM users WHERE id=%s", (user_id,))
    return redirect(url_for('admin_users'))

@app.route('/admin/contact-user/<int:user_id>')
@admin_login_required
def contact_user(user_id):
    user = query_db("SELECT email FROM users WHERE id=%s", (user_id,), one=True)
    return redirect(f"mailto:{user['email']}")

# =============================
# ADMIN LOST ITEMS ROUTES
# =============================
@app.route('/admin/lost-items')
@admin_login_required
def admin_lost_items():
    items = query_db("""
        SELECT li.id, li.title, li.category, li.location, li.lost_date, li.description, li.image,
               u.name AS user_name, u.email AS user_email, u.profile_image
        FROM lost_items li
        JOIN users u ON li.user_id = u.id
        ORDER BY li.id DESC
    """)
    for item in items:
        item['profile_image_url'] = url_for('static', filename='uploads/' + item['profile_image']) if item['profile_image'] else "https://cdn-icons-png.flaticon.com/512/847/847969.png"
        item['image_url'] = url_for('static', filename='uploads/' + item['image']) if item['image'] else None
    return render_template('admin_lost_items.html', items=items)

@app.route('/admin/lost-items/search')
@admin_login_required
def admin_search_lost_items():
    q = request.args.get('q', '').strip()
    like = f"%{q}%"

    # 🔍 MAIN SEARCH
    if q:
        items = query_db("""
            SELECT 
                li.id, li.title, li.category, li.location, li.lost_date, li.description, li.image,
                u.name AS user_name, u.email AS user_email, u.profile_image
            FROM lost_items li
            JOIN users u ON li.user_id = u.id
            WHERE 
                LOWER(li.title) LIKE LOWER(%s) OR
                LOWER(li.category) LIKE LOWER(%s) OR
                LOWER(li.location) LIKE LOWER(%s) OR
                LOWER(li.description) LIKE LOWER(%s) OR
                LOWER(u.email) LIKE LOWER(%s)
            ORDER BY li.id DESC
        """, (like, like, like, like, like))
    else:
        items = query_db("""
            SELECT 
                li.id, li.title, li.category, li.location, li.lost_date, li.description, li.image,
                u.name AS user_name, u.email AS user_email, u.profile_image
            FROM lost_items li
            JOIN users u ON li.user_id = u.id
            ORDER BY li.id DESC
        """)

    # 💡 RECOMMENDATIONS (IMPORTANT FIX)
    suggestions = []
    if q:
        suggestions = query_db("""
            SELECT DISTINCT li.title
            FROM lost_items li
            WHERE LOWER(li.title) LIKE LOWER(%s)
            LIMIT 5
        """, (like,))

    # 🖼️ IMAGE FIX
    for item in items:
        item['profile_image_url'] = url_for(
            'static', filename='uploads/' + item['profile_image']
        ) if item['profile_image'] else "https://cdn-icons-png.flaticon.com/512/847/847969.png"

        item['image_url'] = url_for(
            'static', filename='uploads/' + item['image']
        ) if item['image'] else None

    return render_template(
        "admin_lost_items.html",
        items=items,
        suggestions=suggestions,
        q=q
    )
    
@app.route('/admin/lost-items/suggestions')
@admin_login_required
def lost_items_suggestions():
    q = request.args.get('q', '').strip()

    if not q:
        return {"suggestions": []}

    like = f"%{q}%"

    results = query_db("""
        SELECT DISTINCT title
        FROM lost_items
        WHERE LOWER(title) LIKE LOWER(%s)
        LIMIT 5
    """, (like,))

    return {
        "suggestions": [r['title'] for r in results]
    }
@app.route('/admin/delete-lost-item/<int:item_id>')
@admin_login_required
def admin_delete_lost_item(item_id):
    item = query_db("SELECT li.title, u.name AS user_name, u.email AS user_email FROM lost_items li JOIN users u ON li.user_id=u.id WHERE li.id=%s", (item_id,), one=True)
    if not item:
        flash("Lost item not found", "error")
        return redirect(url_for('admin_lost_items'))
    execute_db("DELETE FROM lost_items WHERE id=%s", (item_id,))
    send_item_deleted_email(item['user_email'], item['user_name'], item['title'])
    flash("Lost item deleted & user notified 📧", "success")
    return redirect(url_for('admin_lost_items'))

@app.route('/admin/lost-item/<int:item_id>')
@admin_login_required
def admin_view_lost_item(item_id):
    item = query_db("SELECT li.*, u.name, u.email FROM lost_items li JOIN users u ON li.user_id=u.id WHERE li.id=%s", (item_id,), one=True)
    if not item:
        flash("Lost item not found", "error")
        return redirect(url_for('admin_lost_items'))
    return render_template('admin_lost_item_detail.html', item=item)

# -----------------------------
# FOUND ITEMS ROUTES
# -----------------------------
@app.route('/admin/found-items')
@admin_login_required
def admin_found_items():
    q = request.args.get('q', '').strip()
    if q:
        like = f"%{q}%"
        items = query_db("""
            SELECT fi.id, fi.title, fi.category, fi.location, fi.found_date, fi.description, fi.image,
                   u.name AS user_name, u.email AS user_email, u.profile_image
            FROM found_items fi
            JOIN users u ON fi.user_id = u.id
            WHERE fi.title LIKE %s OR u.email LIKE %s
            ORDER BY fi.id DESC
        """, (like, like))
    else:
        items = query_db("""
            SELECT fi.id, fi.title, fi.category, fi.location, fi.found_date, fi.description, fi.image,
                   u.name AS user_name, u.email AS user_email, u.profile_image
            FROM found_items fi
            JOIN users u ON fi.user_id = u.id
            ORDER BY fi.id DESC
        """)

    for item in items:
        item['profile_image_url'] = url_for('static', filename='uploads/' + item['profile_image']) if item.get('profile_image') else url_for('static', filename='images/default_user.png')
        item['image_url'] = url_for('static', filename='uploads/' + item['image']) if item.get('image') else None

    return render_template('admin_found_items.html', items=items)

@app.route('/admin/delete-found-item/<int:item_id>')
@admin_login_required
def admin_delete_found_item(item_id):
    item = query_db("SELECT fi.title, u.name AS user_name, u.email AS user_email FROM found_items fi JOIN users u ON fi.user_id=u.id WHERE fi.id=%s", (item_id,), one=True)
    if not item:
        flash("Found item not found", "error")
        return redirect(url_for('admin_found_items'))
    execute_db("DELETE FROM found_items WHERE id=%s", (item_id,))
    send_item_deleted_email(item['user_email'], item['user_name'], item['title'])
    flash("Found item deleted & user notified 📧", "success")
    return redirect(url_for('admin_found_items'))

@app.route('/admin/found-item/<int:item_id>')
@admin_login_required
def admin_view_found_item(item_id):
    item = query_db("SELECT fi.*, u.name, u.email FROM found_items fi JOIN users u ON fi.user_id=u.id WHERE fi.id=%s", (item_id,), one=True)
    if not item:
        flash("Found item not found", "error")
        return redirect(url_for('admin_found_items'))
    return render_template('admin_found_item_detail.html', item=item)

@app.route('/admin/found-items/search')
@admin_login_required
def admin_search_found_items():
    q = request.args.get('q', '').strip()
    like = f"%{q}%"

    items = query_db("""
        SELECT fi.id, fi.title, fi.category, fi.location, fi.found_date, fi.description, fi.image,
               u.name AS user_name, u.email AS user_email, u.profile_image
        FROM found_items fi
        JOIN users u ON fi.user_id = u.id
        WHERE fi.title LIKE %s OR u.email LIKE %s
        ORDER BY fi.created_at DESC
    """, (like, like))

    # Set image URLs for search results
    for item in items:
        item['profile_image_url'] = url_for('static', filename='uploads/' + item['profile_image']) if item.get('profile_image') else url_for('static', filename='images/default_user.png')
        item['image_url'] = url_for('static', filename='uploads/' + item['image']) if item.get('image') else None

    return render_template('admin_found_items.html', items=items)


@app.route("/admin/messages")
@admin_login_required  # ONLY ADMIN
def admin_messages():

    query = """
        SELECT 
            admin_messages.id,
            admin_messages.user_id,
            admin_messages.subject,
            admin_messages.message,
            admin_messages.created_at,
            users.name,
            users.email,
            users.profile_image
        FROM admin_messages
        JOIN users ON admin_messages.user_id = users.id
        ORDER BY admin_messages.created_at DESC
    """

    messages = query_db(query)

    return render_template("admin_messages.html", messages=messages)


@app.route("/admin/delete-message/<int:msg_id>", methods=["POST"])
@admin_login_required
def delete_message(msg_id):

    execute_db(
        "DELETE FROM admin_messages WHERE id = %s",
        (msg_id,)
    )

    flash("Message deleted successfully!", "success")
    return redirect(url_for("admin_messages"))
# =============================
# RESOLVED ITEMS
# =============================
@app.route("/admin/resolved")
@admin_login_required
def admin_resolved():

    # 🔴 LOST (recovered)
    lost_items = query_db("""
        SELECT 
            lost_items.*,
            users.name AS username,
            users.email,
            users.profile_image
        FROM lost_items
        JOIN users ON lost_items.user_id = users.id
        WHERE lost_items.status = 'recovered'
        ORDER BY lost_items.recovered_at DESC
    """)

    # 🔵 FOUND (returned)
    found_items = query_db("""
        SELECT 
            found_items.*,
            users.name AS username,
            users.email,
            users.profile_image
        FROM found_items
        JOIN users ON found_items.user_id = users.id
        WHERE found_items.status = 'returned'
        ORDER BY found_items.returned_at DESC
    """)

    return render_template(
        "admin_resolved.html",
        lost_items=lost_items,
        found_items=found_items
    )
    
@app.route("/admin/delete-resolved-lost/<int:item_id>")
@admin_login_required
def delete_resolved_lost(item_id):

    item = query_db("""
        SELECT li.title, li.recovery_note, u.name, u.email
        FROM lost_items li
        JOIN users u ON li.user_id = u.id
        WHERE li.id=%s
    """, (item_id,), one=True)

    if item:
        execute_db("DELETE FROM lost_items WHERE id=%s", (item_id,))

        send_email(
            item["email"],
            "Resolved Lost Item Removed",
            f"""
Hello {item['name']},

Your RECOVERED lost item "{item['title']}" has been removed by admin.
"""
        )

        flash("Resolved lost item deleted successfully!", "success")

    return redirect(url_for("admin_resolved"))


@app.route("/admin/delete-resolved-found/<int:item_id>")
@admin_login_required
def delete_resolved_found(item_id):

    item = query_db("""
        SELECT fi.title, fi.return_note, u.name, u.email
        FROM found_items fi
        JOIN users u ON fi.user_id = u.id
        WHERE fi.id=%s
    """, (item_id,), one=True)

    if item:
        execute_db("DELETE FROM found_items WHERE id=%s", (item_id,))

        send_email(
            item["email"],
            "Resolved Found Item Removed",
            f"""
Hello {item['name']},

Your RETURNED found item "{item['title']}" has been removed by admin.
"""
        )

        flash("Resolved found item deleted successfully!", "success")

    return redirect(url_for("admin_resolved"))
# =============================
# EMAIL FUNCTION
# =============================
def send_item_deleted_email(to_email, user_name, item_title):
    subject = "Lost & Found – Item Removed Notification"
    body = f"""
Dear {user_name},

We hope you are doing well.

We would like to inform you that your reported lost/found item titled
"{item_title}" has been removed from our platform.

🔒 Reason:
This action was taken due to one or more policy considerations,
such as incomplete information, duplicate entry, or policy violation.

If you believe this was a mistake, please submit a new report or contact support.

Kind regards,
Lost & Found Administration Team
"""
    # call your email sending function here
    send_email(to_email, subject, body)
    
    
@app.route("/admin/requests")
def admin_requests():
    # Fetch all pending users
    pending_users = query_db("SELECT * FROM users WHERE status='pending'")
    return render_template("admin_requests.html", users=pending_users)

@app.route("/admin/approve/<int:user_id>")
def approve_user(user_id):

    user = query_db(
        "SELECT name, email FROM users WHERE id=%s",
        (user_id,),
        one=True
    )

    if user:
        execute_db(
            "UPDATE users SET status='approved', is_verified=1 WHERE id=%s",
            (user_id,)
        )

        send_email(
            user['email'],
            "Account Approved ✅",
            f"""Hello {user['name']},

Your account has been approved 🎉

Login here:
http://127.0.0.1:5000/login
"""
        )

        flash("User approved + email sent!", "success")

    return redirect(url_for("admin_requests"))

@app.route("/admin/reject/<int:user_id>")
def reject_user(user_id):

    user = query_db(
        "SELECT name, email, student_card FROM users WHERE id=%s",
        (user_id,),
        one=True
    )

    if user:

        send_email(
            user['email'],
            "Account Rejected ❌",
            f"""Hello {user['name']},

Your account has been rejected.

You may register again.
"""
        )

        execute_db("DELETE FROM users WHERE id=%s", (user_id,))

        if user.get("student_card"):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], user["student_card"])
            if os.path.exists(file_path):
                os.remove(file_path)

        flash("User rejected + email sent!", "error")

    return redirect(url_for("admin_requests"))

@app.route("/admin/delete-rejected")
def delete_rejected_users():

    rejected_users = query_db(
        "SELECT student_card FROM users WHERE status='rejected'"
    )

    for user in rejected_users:
        if user.get("student_card"):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], user["student_card"])
            if os.path.exists(file_path):
                os.remove(file_path)

    execute_db("DELETE FROM users WHERE status='rejected'")

    flash("All rejected users deleted successfully!", "success")
    return redirect(url_for("admin_requests"))


from datetime import date

# =============================
# TODAY LOST ITEMS
# =============================
@app.route("/admin/today-lost")
@admin_login_required
def admin_today_lost():

    today_lost_items = query_db("""
        SELECT 
            li.*, 
            u.name AS user_name, 
            u.email AS user_email,
            u.profile_image
        FROM lost_items li
        JOIN users u ON li.user_id = u.id
        WHERE DATE(li.created_at) = CURDATE()
        ORDER BY li.created_at DESC
    """)

    return render_template(
        "admin_today_lost.html",
        today_lost_items=today_lost_items
    )
    
@app.route("/admin/today-delete-lost-item/<int:item_id>")
@admin_login_required
def admin_today_delete_lost(item_id):

    item = query_db("""
        SELECT li.title, u.name, u.email
        FROM lost_items li
        JOIN users u ON li.user_id = u.id
        WHERE li.id=%s
    """, (item_id,), one=True)

    if item:
        execute_db("DELETE FROM lost_items WHERE id=%s", (item_id,))

        send_email(
            item["email"],
            "Today Lost Item Deleted",
            f"""
Hello {item['name']},

Your TODAY lost item "{item['title']}" has been removed by admin.

Regards,
Lost & Found Team
"""
        )

        flash("Today lost item deleted successfully!", "success")

    return redirect(url_for("admin_today_lost"))

# =============================
# TODAY FOUND ITEMS
# =============================
@app.route("/admin/today-found")
@admin_login_required
def admin_today_found():

    today_found_items = query_db("""
        SELECT 
            fi.*, 
            u.name AS user_name, 
            u.email AS user_email,
            u.profile_image
        FROM found_items fi
        JOIN users u ON fi.user_id = u.id
        WHERE DATE(fi.created_at) = CURDATE()
        ORDER BY fi.created_at DESC
    """)

    return render_template(
        "admin_today_found.html",
        today_found_items=today_found_items
    )


@app.route("/admin/today-delete-found-item/<int:item_id>")
@admin_login_required
def admin_today_delete_found(item_id):

    item = query_db("""
        SELECT fi.title, u.name, u.email
        FROM found_items fi
        JOIN users u ON fi.user_id = u.id
        WHERE fi.id=%s
    """, (item_id,), one=True)

    if item:
        execute_db("DELETE FROM found_items WHERE id=%s", (item_id,))

        send_email(
            item["email"],
            "Today Found Item Deleted",
            f"""
Hello {item['name']},

Your TODAY found item "{item['title']}" has been removed by admin.

Regards,
Lost & Found Team
"""
        )

        flash("Today found item deleted successfully!", "success")

    return redirect(url_for("admin_today_found"))
# =============================
# TODAY RESOLVED ITEMS
# =============================
@app.route("/admin/today-resolved")
@admin_login_required
def admin_today_resolved():

    # 🔴 Recovered Lost Items (today)
    lost_items = query_db("""
        SELECT 
            li.*,
            u.name AS user_name,
            u.email AS user_email,
            u.profile_image
        FROM lost_items li
        JOIN users u ON li.user_id = u.id
        WHERE li.status = 'recovered'
        AND DATE(li.recovered_at) = CURDATE()
        ORDER BY li.recovered_at DESC
    """)

    # 🔵 Returned Found Items (today)
    found_items = query_db("""
        SELECT 
            fi.*,
            u.name AS user_name,
            u.email AS user_email,
            u.profile_image
        FROM found_items fi
        JOIN users u ON fi.user_id = u.id
        WHERE fi.status = 'returned'
        AND DATE(fi.returned_at) = CURDATE()
        ORDER BY fi.returned_at DESC
    """)

    return render_template(
        "admin_today_resolved.html",
        lost_items=lost_items,
        found_items=found_items
    )
    
@app.route("/admin/delete-today-resolved-lost/<int:item_id>")
@admin_login_required
def admin_delete_today_resolved_lost(item_id):

    item = query_db("""
        SELECT li.title, u.name, u.email
        FROM lost_items li
        JOIN users u ON li.user_id = u.id
        WHERE li.id=%s
    """, (item_id,), one=True)

    if item:
        execute_db("DELETE FROM lost_items WHERE id=%s", (item_id,))

        send_email(
            item["email"],
            "Resolved Report Deleted",
            f"""
Hello {item['name']},

Your RECOVERED lost item "{item['title']}" has been removed by admin.

Regards,
Lost & Found Team
"""
        )
        flash("Today resolved lost item deleted successfully!", "success")
        return redirect(url_for("admin_today_resolved"))

@app.route("/admin/delete-today-resolved-found/<int:item_id>")
@admin_login_required
def admin_delete_today_resolved_found(item_id):

    item = query_db("""
        SELECT fi.title, u.name, u.email
        FROM found_items fi
        JOIN users u ON fi.user_id = u.id
        WHERE fi.id=%s
    """, (item_id,), one=True)

    if item:
        execute_db("DELETE FROM found_items WHERE id=%s", (item_id,))

        send_email(
            item["email"],
            "Resolved Report Deleted",
            f"""
Hello {item['name']},

Your RETURNED found item "{item['title']}" has been removed by admin.

Regards,
Lost & Found Team
"""
        )
        flash("Today resolved found item deleted successfully!", "success")

    return redirect(url_for("admin_today_resolved"))
# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    app.run(debug=True)
