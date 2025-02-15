from app import app, db

# Ensure database operations happen within the app context
with app.app_context():
    db.create_all()
    print("✅ PostgreSQL database initialized successfully!")
