from core import create_app, db

app = create_app()

with app.app_context():
    # This command drops the entire collections
    db.users.drop()
    db.jobs.drop()
    
    print(">>> ⚠️ DATABASE COMPLETELY DESTROYED ⚠️")
    print("All Users, Jobs, and Admins are gone.")
    print("You must now go to /register to create a new user.")