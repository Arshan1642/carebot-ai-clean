import os

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import db, User, ChatHistory, Appointment
from datetime import datetime
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'carebotai-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///carebot.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")  # Put your Groq API key here

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ===== CREATE DATABASE =====
with app.app_context():
    db.create_all()

# ===== HOME =====
@app.route("/")
def home():
    return render_template("index.html")
# ===== APPOINTMENTS PAGE =====
@app.route("/appointments")
def appointments():
    return render_template("appointments.html")

@app.route("/hospitals")
def hospitals():
    return render_template("hospitals.html")

# ===== CHAT PAGE =====
@app.route("/carebot")
def carebot():
    chats = []
    if current_user.is_authenticated:
        chats = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.timestamp.desc()).limit(30).all()
    return render_template("carebot.html", chats=chats)

# ===== SIGNUP =====
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template("signup.html", error="Email already registered! Please login.")

        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('home'))

    return render_template("signup.html")

# ===== LOGIN =====
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            return render_template("login.html", error="Invalid email or password!")

    return render_template("login.html")

# ===== LOGOUT =====
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# ===== DASHBOARD =====
@app.route("/dashboard")
@login_required
def dashboard():
    chats = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.timestamp.desc()).limit(20).all()
    appointments = Appointment.query.filter_by(user_id=current_user.id).order_by(Appointment.created_at.desc()).all()
    return render_template("dashboard.html", user=current_user, chats=chats, appointments=appointments)

# ===== CHAT =====
@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": """You are CareBot AI, an advanced AI healthcare assistant specialized for India. You help users with health-related queries in a professional, empathetic, and structured way.

When a user describes symptoms:
1. List possible conditions clearly
2. Rate severity as: 🟢 Mild / 🟡 Moderate / 🔴 Serious
3. Give immediate home remedies if applicable
4. Recommend whether to visit a doctor or not
5. Suggest which type of specialist to visit

When asked about medicines:
1. Give the medicine name (Indian brand if possible)
2. Common dosage
3. Side effects
4. Mention if prescription is needed

Always:
- Be empathetic and caring in tone
- Give responses in clear sections with headings
- Use simple English that anyone can understand
- End every response with: '⚠️ Always consult a qualified doctor for proper diagnosis.'
- Never diagnose definitively — always say 'possible' or 'may indicate'

You are serving users across India so be aware of common Indian health conditions like dengue, typhoid, malaria, diabetes, blood pressure issues etc."""
            },
            {
                "role": "user",
                "content": user_message
            }
        ]
    }

    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
    result = response.json()
    bot_reply = result["choices"][0]["message"]["content"]

    # Save to chat history if user is logged in
    if current_user.is_authenticated:
        chat_entry = ChatHistory(
            user_id=current_user.id,
            message=user_message,
            response=bot_reply
        )
        db.session.add(chat_entry)
        db.session.commit()

    return jsonify({"reply": bot_reply})

# ===== BOOK APPOINTMENT =====
@app.route("/book-appointment", methods=["POST"])
def book_appointment():
    data = request.json
    appointment = Appointment(
        user_id=current_user.id if current_user.is_authenticated else None,
        name=data.get("name"),
        phone=data.get("phone"),
        specialty=data.get("specialty"),
        date=data.get("date"),
        time=data.get("time"),
        issue=data.get("issue")
    )
    db.session.add(appointment)
    db.session.commit()
    return jsonify({"success": True, "message": "Appointment booked successfully!"})

# ===== GET CHAT HISTORY =====
@app.route("/chat-history")
@login_required
def chat_history():
    chats = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.timestamp.desc()).limit(50).all()
    return jsonify([{
        "message": c.message,
        "response": c.response,
        "timestamp": c.timestamp.strftime("%d %b %Y, %I:%M %p")
    } for c in chats])

if __name__ == "__main__":
    app.run(debug=True)