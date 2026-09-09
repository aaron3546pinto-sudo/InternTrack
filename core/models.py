from flask_login import UserMixin
from core import db, login_manager
from bson.objectid import ObjectId
import datetime

@login_manager.user_loader
def load_user(user_id):
    u = db.users.find_one({"_id": ObjectId(user_id)})
    if not u: return None
    return User(u)

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.name = user_data['name']
        self.email = user_data['email']
        self.role = user_data['role']
        self.skills = user_data.get('skills', '')
        self.github = user_data.get('github', '')
        self.linkedin = user_data.get('linkedin', '')
        
        # Profile Fields
        self.education = user_data.get('education', '')
        self.cgpa = user_data.get('cgpa', '')
        self.experience = user_data.get('experience', '')
        self.resume_link = user_data.get('resume_link', '')
        self.certificate_link = user_data.get('certificate_link', '')
        
        # --- FIX: LOAD ACADEMIC & INTERNSHIP FIELDS ---
        self.branch = user_data.get('branch', '')
        self.study_year = user_data.get('study_year', '')
        self.academic_year = user_data.get('academic_year', '')
        self.division = user_data.get('division', '')
        self.internships = user_data.get('internships', [])
        # ----------------------------------------------
        
        self.verification_status = user_data.get('verification_status', 'Pending')
        self.placement_status = user_data.get('placement_status', 'Open')
        self.notifications = user_data.get('notifications', [])
        
        # ML FIELD
        self.placement_probability = user_data.get('placement_probability', 0)

    @property
    def unread_notifications_count(self):
        count = 0
        for n in self.notifications:
            # Check if notification is a Dictionary (New format) AND is_read is False
            if isinstance(n, dict) and not n.get('is_read', False):
                count += 1
        return count

    @staticmethod
    def create_user(name, email, password, role, skills):
        user_data = {
            "name": name, "email": email, "password": password, "role": role, "skills": skills,
            "verification_status": "Pending" if role == 'student' else "Verified",
            "placement_status": "Open", "notifications": [],
            "github": "", "linkedin": "", 
            "education": "", "cgpa": "", "experience": "", 
            "resume_link": "", "certificate_link": "",
            "branch": "", "study_year": "", "academic_year": "", "division": "",
            "internships": []
        }
        return db.users.insert_one(user_data)

    @staticmethod
    def update_profile(user_id, data):
        db.users.update_one({"_id": ObjectId(user_id)}, {"$set": data})

    @staticmethod
    def get_skill_supply():
        """
        DBMS Flex: Uses an aggregation pipeline to split the comma-separated 
        skills string, clean the text, and count frequencies across all students.
        """
        pipeline = [
            {"$match": {"role": "student"}}, # Only look at students
            {"$project": {"skillsArray": {"$split": [{"$ifNull": ["$skills", ""]}, ","]}}},
            {"$unwind": "$skillsArray"},
            {"$project": {"skill": {"$trim": {"input": {"$toLower": "$skillsArray"}}}}},
            {"$match": {"skill": {"$ne": ""}}},
            {"$group": {"_id": "$skill", "count": {"$sum": 1}}}
        ]
        results = list(db.users.aggregate(pipeline))
        return {item['_id']: item['count'] for item in results}
    
    @staticmethod
    def delete_user(user_id):
        # 1. Delete the user document
        db.users.delete_one({"_id": ObjectId(user_id)})
        # 2. Clean up: Remove them from any jobs they applied to
        db.jobs.update_many(
            {"applicants.user_id": user_id},
            {"$pull": {"applicants": {"user_id": user_id}}}
        )

class Job:
    @staticmethod
    def create_job(title, company, skills, description, posted_by, salary):
        return db.jobs.insert_one({
            "title": title, "company": company, "skills": skills,
            "description": description, "posted_by": posted_by, "salary": salary,
            "applicants": [],
            "posted_date": datetime.datetime.now()
        })
    
    @staticmethod
    def apply_to_job(job_id, user):
        applicant_entry = {
            "user_id": user.id, "name": user.name, "email": user.email, "skills": user.skills,
            "status": "Applied", "applied_date": datetime.datetime.now()
        }
        
        # 1. Clear out any previous "Rejected" application for this specific user
        db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$pull": {"applicants": {"user_id": user.id, "status": "Rejected"}}}
        )
        
        # 2. Push the new application
        db.jobs.update_one(
            {"_id": ObjectId(job_id), "applicants.user_id": {"$ne": user.id}}, 
            {"$push": {"applicants": applicant_entry}}
        )

    @staticmethod
    def update_applicant_status(job_id, user_id, new_status):
        db.jobs.update_one(
            {"_id": ObjectId(job_id), "applicants.user_id": user_id},
            {"$set": {"applicants.$.status": new_status}}
        )
        if new_status == "Hired":
            db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"placement_status": "Placed"}})
        elif new_status == "Interviewing":
            db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"placement_status": "Interviewing"}})
        elif new_status == "Hold":
            db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"placement_status": "Hold"}})
        elif new_status == "Rejected":
             db.users.update_one(
                 {"_id": ObjectId(user_id), "placement_status": {"$nin": ["Placed", "Interviewing"]}}, 
                 {"$set": {"placement_status": "Rejected"}}
             )
    
    @staticmethod
    def delete_job(job_id):
        db.jobs.delete_one({"_id": ObjectId(job_id)})

    @staticmethod
    def get_skill_demand():
        pipeline = [
            {"$project": {"skillsArray": {"$split": [{"$ifNull": ["$skills", ""]}, ","]}}},
            {"$unwind": "$skillsArray"},
            {"$project": {"skill": {"$trim": {"input": {"$toLower": "$skillsArray"}}}}},
            {"$match": {"skill": {"$ne": ""}}},
            {"$group": {"_id": "$skill", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}, 
            {"$limit": 5}             
        ]
        return list(db.jobs.aggregate(pipeline))

    @staticmethod
    def get_total_applications_count():
        pipeline = [
            {"$project": {"app_count": {"$size": {"$ifNull": ["$applicants", []]}}}},
            {"$group": {"_id": None, "total": {"$sum": "$app_count"}}}
        ]
        result = list(db.jobs.aggregate(pipeline))
        return result[0]['total'] if result else 0