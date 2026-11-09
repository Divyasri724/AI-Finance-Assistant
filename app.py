import os
import calendar
from datetime import datetime

import joblib
import numpy as np

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)

from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Transaction, Budget


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

app.config["SECRET_KEY"] = "ai-finance-assistant-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + os.path.join(BASE_DIR, "instance", "finance.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db.init_app(app)

CATEGORIES = [
    "Food",
    "Travel",
    "Shopping",
    "Bills",
    "Education",
    "Health",
    "Entertainment",
    "Salary",
    "Other"
]

MODEL_PATH = os.path.join(
    BASE_DIR, "ml_models", "expense_category_model.pkl"
)

expense_model = None

try:
    if os.path.exists(MODEL_PATH):
        expense_model = joblib.load(MODEL_PATH)
except Exception:
    expense_model = None


with app.app_context():
    db.create_all()


def get_current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    return db.session.get(User, user_id)


def predict_category(description):
    if expense_model is not None:
        try:
            return expense_model.predict([description])[0]
        except Exception:
            pass

    return "Other"


@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))

        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password)
        )

        db.session.add(user)
        db.session.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user:
            password_valid = check_password_hash(
                user.password, password
            ) if user.password.startswith(("pbkdf2:", "scrypt:")) else (
                user.password == password
            )

            if password_valid:
                if not user.password.startswith(("pbkdf2:", "scrypt:")):
                    user.password = generate_password_hash(password)
                    db.session.commit()

                session["user_id"] = user.id
                session["user_name"] = user.name

                return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    user = get_current_user()

    if not user:
        return redirect(url_for("login"))

    transactions = Transaction.query.filter_by(
        user_id=user.id
    ).order_by(Transaction.id.desc()).all()

    income = sum(
        t.amount for t in transactions if t.type.lower() == "income"
    )

    expenses = sum(
        t.amount for t in transactions if t.type.lower() == "expense"
    )

    balance = income - expenses

    category_totals = {}

    for transaction in transactions:
        if transaction.type.lower() == "expense":
            category_totals[transaction.category] = (
                category_totals.get(transaction.category, 0)
                + transaction.amount
            )

    chart_labels = list(category_totals.keys())
    chart_values = list(category_totals.values())

    recent_transactions = transactions[:5]

    return render_template(
        "dashboard.html",
        user=user,
        income=income,
        expenses=expenses,
        balance=balance,
        transactions=recent_transactions,
        chart_labels=chart_labels,
        chart_values=chart_values,
        categories=CATEGORIES
    )


@app.route("/transaction", methods=["GET", "POST"])
def transaction():
    user = get_current_user()

    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        description = request.form.get("description", "").strip()
        amount = request.form.get("amount", "")
        transaction_type = request.form.get("type", "")
        category = request.form.get("category", "")
        date = request.form.get("date", "")

        try:
            amount = float(amount)

            if amount <= 0:
                raise ValueError

            if transaction_type not in ["Income", "Expense"]:
                raise ValueError

            if not description or not date:
                raise ValueError

            if category not in CATEGORIES:
                category = predict_category(description)

            record = Transaction(
                user_id=user.id,
                description=description,
                amount=amount,
                type=transaction_type,
                category=category,
                date=date
            )

            db.session.add(record)
            db.session.commit()

            flash("Transaction added successfully.", "success")
            return redirect(url_for("transactions"))

        except ValueError:
            flash("Please enter valid transaction details.", "danger")

    return render_template(
        "transaction.html",
        categories=CATEGORIES,
        today=datetime.today().strftime("%Y-%m-%d")
    )


@app.route("/transactions")
def transactions():
    user = get_current_user()

    if not user:
        return redirect(url_for("login"))

    records = Transaction.query.filter_by(
        user_id=user.id
    ).order_by(Transaction.id.desc()).all()

    return render_template(
        "transactions.html",
        transactions=records
    )


@app.route("/edit_transaction/<int:transaction_id>", methods=["GET", "POST"])
def edit_transaction(transaction_id):
    user = get_current_user()

    if not user:
        return redirect(url_for("login"))

    record = Transaction.query.filter_by(
        id=transaction_id,
        user_id=user.id
    ).first_or_404()

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
            description = request.form.get("description", "").strip()
            transaction_type = request.form.get("type", "")
            category = request.form.get("category", "")
            date = request.form.get("date", "")

            if amount <= 0 or not description or not date:
                raise ValueError

            if transaction_type not in ["Income", "Expense"]:
                raise ValueError

            if category not in CATEGORIES:
                raise ValueError

            record.description = description
            record.amount = amount
            record.type = transaction_type
            record.category = category
            record.date = date

            db.session.commit()

            flash("Transaction updated successfully.", "success")
            return redirect(url_for("transactions"))

        except ValueError:
            flash("Please enter valid transaction details.", "danger")

    return render_template(
        "edit_transaction.html",
        record=record,
        categories=CATEGORIES
    )


@app.route("/delete_transaction/<int:transaction_id>", methods=["POST"])
def delete_transaction(transaction_id):
    user = get_current_user()

    if not user:
        return redirect(url_for("login"))

    record = Transaction.query.filter_by(
        id=transaction_id,
        user_id=user.id
    ).first_or_404()

    db.session.delete(record)
    db.session.commit()

    flash("Transaction deleted successfully.", "success")
    return redirect(url_for("transactions"))


@app.route("/budget", methods=["GET", "POST"])
def budget():
    user = get_current_user()

    if not user:
        return redirect(url_for("login"))

    current_month = datetime.today().strftime("%Y-%m")

    if request.method == "POST":
        category = request.form.get("category", "")
        month = request.form.get("month", current_month)

        try:
            limit_amount = float(
                request.form.get("limit_amount", 0)
            )

            if category not in CATEGORIES or limit_amount <= 0:
                raise ValueError

            existing_budget = Budget.query.filter_by(
                user_id=user.id,
                category=category,
                month=month
            ).first()

            if existing_budget:
                existing_budget.limit_amount = limit_amount
            else:
                new_budget = Budget(
                    user_id=user.id,
                    category=category,
                    limit_amount=limit_amount,
                    month=month
                )
                db.session.add(new_budget)

            db.session.commit()

            flash("Budget saved successfully.", "success")
            return redirect(url_for("budget"))

        except ValueError:
            flash("Please enter valid budget details.", "danger")

    budgets = Budget.query.filter_by(
        user_id=user.id
    ).order_by(Budget.month.desc()).all()

    budget_details = []

    for item in budgets:
        spent = db.session.query(
            db.func.sum(Transaction.amount)
        ).filter(
            Transaction.user_id == user.id,
            Transaction.category == item.category,
            Transaction.type == "Expense",
            Transaction.date.like(item.month + "%")
        ).scalar() or 0

        budget_details.append({
            "id": item.id,
            "category": item.category,
            "month": item.month,
            "limit_amount": item.limit_amount,
            "spent": spent,
            "remaining": item.limit_amount - spent
        })

    return render_template(
        "budget.html",
        budgets=budget_details,
        categories=CATEGORIES,
        current_month=current_month
    )


@app.route("/delete_budget/<int:budget_id>", methods=["POST"])
def delete_budget(budget_id):
    user = get_current_user()

    if not user:
        return redirect(url_for("login"))

    record = Budget.query.filter_by(
        id=budget_id,
        user_id=user.id
    ).first_or_404()

    db.session.delete(record)
    db.session.commit()

    flash("Budget deleted successfully.", "success")
    return redirect(url_for("budget"))


@app.route("/prediction")
def prediction():
    user = get_current_user()

    if not user:
        return redirect(url_for("login"))

    transactions = Transaction.query.filter_by(
        user_id=user.id,
        type="Expense"
    ).all()

    monthly_expenses = {}

    for item in transactions:
        month = item.date[:7]
        monthly_expenses[month] = (
            monthly_expenses.get(month, 0) + item.amount
        )

    sorted_months = sorted(monthly_expenses.keys())

    labels = sorted_months[-6:]
    values = [monthly_expenses[month] for month in labels]

    if len(values) >= 2:
        x_values = np.arange(len(values))
        slope, intercept = np.polyfit(x_values, values, 1)
        forecast = max(0, float(slope * len(values) + intercept))
    elif len(values) == 1:
        forecast = values[0]
    else:
        forecast = 0

    return render_template(
        "prediction.html",
        forecast=forecast,
        labels=labels,
        values=values
    )


@app.route("/insights")
def insights():
    user = get_current_user()

    if not user:
        return redirect(url_for("login"))

    transactions = Transaction.query.filter_by(
        user_id=user.id
    ).all()

    income = sum(
        t.amount for t in transactions if t.type.lower() == "income"
    )

    expenses = sum(
        t.amount for t in transactions if t.type.lower() == "expense"
    )

    insights_list = []

    if expenses == 0:
        insights_list.append(
            "You have not recorded any expenses yet."
        )
    else:
        insights_list.append(
            f"Your total recorded expenses are ₹{expenses:.2f}."
        )

    if income > 0:
        savings = income - expenses
        insights_list.append(
            f"Your current recorded balance is ₹{savings:.2f}."
        )

        if savings > 0:
            insights_list.append(
                "Your recorded income is higher than your expenses."
            )
        elif savings < 0:
            insights_list.append(
                "Your recorded expenses are higher than your income."
            )
        else:
            insights_list.append(
                "Your recorded income and expenses are equal."
            )

    category_totals = {}

    for item in transactions:
        if item.type.lower() == "expense":
            category_totals[item.category] = (
                category_totals.get(item.category, 0) + item.amount
            )

    if category_totals:
        highest_category = max(
            category_totals, key=category_totals.get
        )

        insights_list.append(
            f"Your highest spending category is {highest_category}."
        )

    return render_template(
        "insights.html",
        insights=insights_list
    )


@app.route("/chatbot")
def chatbot():
    if not get_current_user():
        return redirect(url_for("login"))

    return render_template("chatbot.html")


@app.route("/chatbot/message", methods=["POST"])
def chatbot_message():
    user = get_current_user()

    if not user:
        return jsonify({"reply": "Please log in first."}), 401

    data = request.get_json(silent=True) or {}
    message = data.get("message", "").lower().strip()

    transactions = Transaction.query.filter_by(
        user_id=user.id
    ).all()

    income = sum(
        t.amount for t in transactions if t.type.lower() == "income"
    )

    expenses = sum(
        t.amount for t in transactions if t.type.lower() == "expense"
    )

    balance = income - expenses

    if "income" in message:
        reply = f"Your total recorded income is ₹{income:.2f}."

    elif "expense" in message or "spending" in message:
        reply = f"Your total recorded expenses are ₹{expenses:.2f}."

    elif "balance" in message or "saving" in message:
        reply = f"Your current recorded balance is ₹{balance:.2f}."

    elif "budget" in message:
        reply = "You can view and manage your budgets on the Budget page."

    elif "transaction" in message:
        reply = (
            f"You have recorded {len(transactions)} transactions."
        )

    elif "hello" in message or "hi" in message:
        reply = f"Hello {user.name}! How can I help you with your finances?"

    else:
        reply = (
            "I can help you check your income, expenses, balance, "
            "budgets and transactions. What would you like to know?"
        )

    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(debug=True)