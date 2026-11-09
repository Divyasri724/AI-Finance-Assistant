from app import app
from models import db, User
from werkzeug.security import generate_password_hash

with app.app_context():

    user = User.query.filter_by(
        email="nagisettidivyasri724@gmail.com"
    ).first()

    if user:
        user.password = generate_password_hash("Divya@123")
        db.session.commit()
        print("Password Reset Successful!")
    else:
        print("User Not Found!")