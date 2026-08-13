
# 1. DATABASE INITIALIZATION
from flask import Flask, request, jsonify
from flask_cors import CORS  # <-- Line 2

from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3
import random
import math

app = Flask(__name__)
CORS(app)  # <-- Line 10
DB_NAME = "loan_database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            email TEXT,
            pan TEXT,
            aadhaar_no TEXT,
            monthly_income REAL,
            credit_score INTEGER
        )
    ''')
    
    # Loans Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loans (
            loan_id TEXT PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            tenure_months INTEGER,
            interest_rate REAL,
            monthly_emi REAL,
            penalty REAL DEFAULT 0,
            status TEXT DEFAULT 'ACTIVE',
            noc_status TEXT DEFAULT 'PENDING'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# 2. HELPER: INTEREST RATE CALCULATOR
def calculate_interest_rate(income, credit_score):
    if income > 50000 and credit_score >= 750:
        return 12.0  # 12% Per Annum
    elif income > 25000 and credit_score >= 650:
        return 18.0  # 18% Per Annum
    else:
        return 24.0  # 24% Per Annum

# 3. API ENDPOINTS

@app.route('/')
def home():
    return jsonify({
        "status": "Server Live",
        "message": "Welcome to Loan Management API System"
    })

# Register User (Aadhaar, PAN, Email, Mobile Update)
@app.route('/api/users/register', methods=['POST'])
def register_user():
    data = request.json or {}
    name = data.get('name')
    phone = data.get('phone')
    email = data.get('email')
    pan = data.get('pan')
    aadhaar_no = data.get('aadhaar_no')
    monthly_income = float(data.get('monthly_income', 0))

    if not name or not phone or monthly_income <= 0:
        return jsonify({"error": "Name, Phone aur Monthly Income zaroori hain!"}), 400

    credit_score = 760 if monthly_income > 30000 else 620

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (name, phone, email, pan, aadhaar_no, monthly_income, credit_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (name, phone, email, pan, aadhaar_no, monthly_income, credit_score))
    
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        "message": "User KYC & Registration Successful!",
        "user_id": user_id,
        "name": name,
        "credit_score": credit_score
    }), 201

# Apply Loan & EMI Calculation
@app.route('/api/loans/apply', methods=['POST'])
def apply_loan():
    data = request.json or {}
    user_id = data.get('user_id')
    amount = float(data.get('amount', 0))
    tenure_months = int(data.get('tenure_months', 12))

    if not user_id or amount <= 0 or tenure_months <= 0:
        return jsonify({"error": "Valid User ID, Amount aur Tenure zaroori hai!"}), 400

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT monthly_income, credit_score FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "User nahi mila! Pehle register karein."}), 404

    income, credit_score = user
    interest_rate = calculate_interest_rate(income, credit_score)

    # EMI Formula Calculation
    monthly_rate = (interest_rate / 100) / 12
    emi = (amount * monthly_rate * math.pow(1 + monthly_rate, tenure_months)) / (math.pow(1 + monthly_rate, tenure_months) - 1)
    
    loan_id = f"LOAN-2026-{random.randint(1000, 9999)}"

    cursor.execute('''
        INSERT INTO loans (loan_id, user_id, amount, tenure_months, interest_rate, monthly_emi, status)
        VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
    ''', (loan_id, user_id, amount, tenure_months, interest_rate, round(emi, 2)))
    
    conn.commit()
    conn.close()

    return jsonify({
        "loan_id": loan_id,
        "user_id": user_id,
        "amount_sanctioned": amount,
        "interest_rate": f"{interest_rate}%",
        "tenure_months": tenure_months,
        "monthly_emi": round(emi, 2),
        "auto_debit_date": "5th of every month",
        "status": "APPROVED & ACTIVE"
    }), 201

# One-time Loan Foreclosure / Close Loan & Issue NOC
@app.route('/api/loans/close', methods=['POST'])
def close_loan():
    data = request.json or {}
    loan_id = data.get('loan_id')

    if not loan_id:
        return jsonify({"error": "Loan ID dena zaroori hai!"}), 400

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT amount, penalty, status FROM loans WHERE loan_id = ?", (loan_id,))
    loan = cursor.fetchone()

    if not loan:
        conn.close()
        return jsonify({"error": "Loan Record nahi mila!"}), 404

    if loan[2] == 'CLOSED':
        conn.close()
        return jsonify({"message": "Yeh loan pehle se hi CLOSED hai!"}), 400

    # Loan Close aur NOC Approve karna
    cursor.execute('''
        UPDATE loans 
        SET status = 'CLOSED', noc_status = 'APPROVED' 
        WHERE loan_id = ?
    ''', (loan_id,))
    
    conn.commit()
    conn.close()

    return jsonify({
        "loan_id": loan_id,
        "status": "CLOSED",
        "noc_status": "APPROVED",
        "message": "Loan successfully closed in one go! NOC generated."
    }), 200

# Get Details of Specific Loan
@app.route('/api/loans/<loan_id>', methods=['GET'])
def get_loan_details(loan_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM loans WHERE loan_id = ?", (loan_id,))
    loan = cursor.fetchone()
    conn.close()

    if not loan:
        return jsonify({"error": "Loan record nahi mila!"}), 404

    return jsonify({
        "loan_id": loan[0],
        "user_id": loan[1],
        "principal_amount": loan[2],
        "tenure_months": loan[3],
        "interest_rate": f"{loan[4]}%",
        "monthly_emi": loan[5],
        "late_penalty": loan[6],
        "status": loan[7],
        "noc_status": loan[8]
    })

# 4. CRON SCHEDULER (AUTO-DEBIT & ₹1,000 PENALTY CHECK)
def check_auto_debit_and_penalty():
    print("\n⏰ CRON ENGINE: Auto-debit bounce check active...")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Active loans par ₹1,000 late fee penalty lagana
    cursor.execute("UPDATE loans SET penalty = penalty + 1000 WHERE status = 'ACTIVE'")
    updated_rows = cursor.rowcount
    
    conn.commit()
    conn.close()
    print(f"⚠️ Total {updated_rows} active loans par ₹1,000 late penalty add kar di gayi hai.")

scheduler = BackgroundScheduler()
scheduler.add_job(func=check_auto_debit_and_penalty, trigger="interval", hours=24) # Har 24 ghante me chalega
scheduler.start()

# 5. SERVER RUN (Mobile Network Friendly)
if __name__ == '__main__':
    print("🚀 Python Loan App Server live ho raha hai...")
    # host='0.0.0.0' ki wajah se mobile phone local network se connect ho sakega
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)