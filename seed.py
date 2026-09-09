from core import create_app, db, bcrypt

app = create_app()

with app.app_context():
    db.users.delete_many({})
    db.jobs.delete_many({})
    
    pw = bcrypt.generate_password_hash('123').decode('utf-8')
    
    # 1. Admin & Faculty
    db.users.insert_one({"name": "Admin", "email": "admin@test.com", "password": pw, "role": "admin"})
    db.users.insert_one({"name": "Faculty", "email": "faculty@test.com", "password": pw, "role": "faculty"})
    
    # 2. Student 1: FRESH (Needs Faculty Verification)
    db.users.insert_one({
        "name": "Rahul New", "email": "rahul@test.com", "password": pw, "role": "student",
        "verification_status": "Pending", "placement_status": "Open", "skills": "Python", "notifications": []
    })
    
    # 3. Student 2: FACULTY VERIFIED (Needs Admin Approval)
    db.users.insert_one({
        "name": "Sneha Mid", "email": "sneha@test.com", "password": pw, "role": "student",
        "verification_status": "Faculty Verified", "placement_status": "Open", "skills": "Java", "notifications": []
    })

    print(">>> Data Reset. Login with password '123'")