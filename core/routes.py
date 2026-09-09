import os
import re # Make sure re is imported
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from core import db, bcrypt, socketio
from core.ai_service import calculate_similarity, extract_skills_from_pdf, predict_placement_probability
from core.models import User, Job
from core.ai_service import calculate_similarity
from core.job_fetcher import sync_external_jobs
from bson.objectid import ObjectId
from collections import Counter
import datetime
import uuid

main = Blueprint('main', __name__)

# CONFIG FOR UPLOADS
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

main = Blueprint('main', __name__)

# --- HELPER ---
def parse_salary(salary_str):
    s = str(salary_str).lower().replace(',', '')
    numbers = re.findall(r"[\d\.]+", s)
    if not numbers: return 0
    val = float(numbers[0])
    if 'month' in s: return (val * 12) / 100000
    if val > 100: return val / 100000
    return val

@main.route('/')
def home():
    # 1. Check if user is logged in
    if current_user.is_authenticated:
        if current_user.role == 'student':
            return redirect(url_for('main.student_dash'))
        elif current_user.role == 'faculty':
            return redirect(url_for('main.faculty_dash'))
        elif current_user.role == 'admin':
            return redirect(url_for('main.admin_dash'))
    
    # 2. CRITICAL FIX: 
    # This line must NOT be indented inside the 'if'.
    # It must be all the way to the left, aligned with the 'if'.
    return render_template('index.html')

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role_check = request.form.get('role_check')
        user_data = db.users.find_one({"email": email})
        
        if user_data and bcrypt.check_password_hash(user_data['password'], password):
            if user_data.get('role') != role_check:
                flash(f'Please switch to the {user_data.get("role").title()} tab.', 'warning')
                return render_template('login.html')
            login_user(User(user_data))
            return redirect(url_for('main.home'))
        flash('Invalid Credentials', 'danger')
    return render_template('login.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        
        # We now pass an empty string ("") for skills during initial signup
        User.create_user(
            request.form.get('name'), 
            request.form.get('email'), 
            hashed_pw, 
            request.form.get('role'), 
            "" 
        )
        flash('Account created! Login to continue.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

# --- STUDENT ROUTES ---
@main.route('/student/dashboard')
@login_required
def student_dash():
    if current_user.role != 'student': return redirect(url_for('main.home'))
    
    all_jobs = list(db.jobs.find())
    recommended = calculate_similarity(current_user.skills, all_jobs)
    
    # 1. Prepare "My Applications" Data for the Frontend JSON
    my_apps_data = []
    applied_ids = []
    
    stats = {'applied': 0, 'interviews': 0, 'offers': 0}

    # Iterate through all jobs to find where user is an applicant
    # Iterate through all jobs to find where user is an applicant
    for job in all_jobs:
        for app in job.get('applicants', []):
            if app['user_id'] == current_user.id:
                
                # --- NEW: Only mark as 'applied' if they haven't been rejected ---
                if app['status'] != 'Rejected':
                    applied_ids.append(str(job['_id']))
                
                stats['applied'] += 1
                
                # Update Stats
                if app['status'] == 'Interviewing': stats['interviews'] += 1
                elif app['status'] in ['Hired', 'Placed']: stats['offers'] += 1
                
                # Add to JSON list
                my_apps_data.append({
                    "company": job['company'],
                    "role": job['title'],
                    "status": app['status'],
                    "date": app.get('applied_date', datetime.datetime.now()).strftime("%Y-%m-%d") if isinstance(app.get('applied_date'), datetime.datetime) else "Recent"
                })
                
    return render_template('student_dash.html', 
                           jobs=recommended, 
                           applied_ids=applied_ids, 
                           stats=stats,
                           my_apps_data=my_apps_data) # <--- Passed to template

@main.route('/student/applications')
@login_required
def my_applications():
    if current_user.role != 'student': return redirect(url_for('main.home'))
    my_jobs = list(db.jobs.find({"applicants.user_id": current_user.id}))
    return render_template('my_applications.html', jobs=my_jobs)

@main.route('/student/notifications')
@login_required
def notifications():
    if current_user.role != 'student': return redirect(url_for('main.home'))
    notes = current_user.notifications[::-1] if current_user.notifications else []
    return render_template('notifications.html', notifications=notes)

@main.route('/student/profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        github = request.form.get('github')
        linkedin = request.form.get('linkedin')
        
        if github and not re.match(r'^https:\/\/(www\.)?github\.com\/[a-zA-Z0-9_-]+$', github):
            flash('Invalid GitHub URL. Must be https://github.com/username', 'danger')
            return redirect(url_for('main.edit_profile'))
            
        if linkedin and not re.match(r'^https:\/\/(www\.)?linkedin\.com\/in\/[a-zA-Z0-9_-]+\/?$', linkedin):
            flash('Invalid LinkedIn URL. Must be https://linkedin.com/in/username', 'danger')
            return redirect(url_for('main.edit_profile'))

        resume_filename = getattr(current_user, 'resume_link', '')
        cert_filename = getattr(current_user, 'certificate_link', '')
        
        # Keep track of manual skills
        current_skills = request.form.get('skills', '')

        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)

        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"{current_user.id}_resume.pdf")
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                resume_filename = filename
                
                # --- NEW NLP PARSER INTEGRATION ---
                extracted_skills = extract_skills_from_pdf(filepath)
                if extracted_skills:
                    # Merge extracted skills with manually typed ones, avoiding duplicates
                    combined = set([s.strip().lower() for s in current_skills.split(',') if s.strip()])
                    combined.update([s.strip().lower() for s in extracted_skills.split(',')])
                    current_skills = ", ".join([s.title() for s in combined])
                    flash('AI successfully extracted new skills from your resume!', 'info')

        if 'certificates' in request.files:
            file = request.files['certificates']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"{current_user.id}_certs.pdf") 
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                cert_filename = filename

        # --- NEW ML PREDICTOR INTEGRATION ---
        cgpa = request.form.get('cgpa')
        skill_count = len(current_skills.split(',')) if current_skills else 0
        applied_jobs_count = db.jobs.count_documents({"applicants.user_id": current_user.id})
        
        prob_score = predict_placement_probability(cgpa, skill_count, applied_jobs_count)

        internships = []
        intern_count = int(request.form.get('intern_count', 0))

        for i in range(intern_count):
            comp = request.form.get(f'intern_company_{i}')
            role = request.form.get(f'intern_role_{i}')
            start = request.form.get(f'intern_start_{i}')
            end = request.form.get(f'intern_end_{i}')
            old_cert = request.form.get(f'old_intern_cert_{i}', '')

            cert_file = request.files.get(f'intern_cert_{i}')
            cert_filename = old_cert

            # If they upload a new certificate for this specific internship
            if cert_file and cert_file.filename != '' and allowed_file(cert_file.filename):
                filename = secure_filename(f"{current_user.id}_intern_{i}_{uuid.uuid4().hex[:6]}.pdf")
                cert_file.save(os.path.join(UPLOAD_FOLDER, filename))
                cert_filename = filename

            if comp and role:  # Only save if they actually filled it out
                internships.append({
                    "company": comp,
                    "role": role,
                    "start_date": start,
                    "end_date": end,
                    "certificate_link": cert_filename
                })

        User.update_profile(current_user.id, {
            "name": request.form.get('name'),
            "skills": current_skills,
            "education": request.form.get('education'),
            "cgpa": cgpa,
            "experience": request.form.get('experience'),
            "resume_link": resume_filename,
            "certificate_link": cert_filename, # Keeps generic certs intact
            "github": github,
            "linkedin": linkedin,
            "placement_probability": prob_score,
            "branch": request.form.get('branch', 'Not Specified'),
            "academic_year": request.form.get('academic_year', 'Not Specified'),
            "study_year": request.form.get('study_year', 'Not Specified'),
            "division": request.form.get('division', 'Not Specified'),
            "internships": internships # Array of all internships
        })
        
        flash('Profile Updated Successfully', 'success')
        return redirect(url_for('main.student_dash'))
        
    return render_template('edit_profile.html')

@main.route('/apply/<job_id>')
@login_required
def apply_job(job_id):
    if current_user.role == 'student':
        Job.apply_to_job(job_id, current_user)
        flash('Application Sent Successfully!', 'success')
    return redirect(url_for('main.student_dash'))

# --- FACULTY ROUTES ---
@main.route('/faculty/dashboard')
@login_required
def faculty_dash():
    if current_user.role != 'faculty': return redirect(url_for('main.home'))
    
    students = list(db.users.find({"role": "student"}))
    
    # --- ADD THIS QUICK FIX LOOP HERE ---
    for student in students:
        if 'placement_probability' not in student:
            student['placement_probability'] = 0
    # ------------------------------------

    active_jobs = list(db.jobs.find({"applicants.status": "Interviewing"}))
    interview_list = []
    
    for job in active_jobs:
        for app in job['applicants']:
            if app.get('status') == 'Interviewing':
                interview_list.append({"name": app.get('name'), "company": job['company'], "role": job['title']})
                
    pending_students = [s for s in students if s.get('verification_status') == 'Pending']
    placed_count = sum(1 for s in students if s.get('placement_status') == 'Placed')
    
    return render_template('faculty_dash.html', students=students, pending_students=pending_students, interview_list=interview_list, total=len(students), placed=placed_count)

@main.route('/faculty/verify/<user_id>')
@login_required
def faculty_verify_student(user_id):
    if current_user.role != 'faculty': return redirect(url_for('main.home'))
    db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"verification_status": "Faculty Verified"}})
    flash('Student Verified.', 'success')
    return redirect(url_for('main.faculty_dash'))

@main.route('/faculty/nudge/<user_id>')
@login_required
def nudge_student(user_id):
    if current_user.role != 'faculty': return redirect(url_for('main.home'))
    msg = {
        "id": str(uuid.uuid4()),
        "title": "Faculty Reminder",
        "text": f"Reminder from Prof. {current_user.name}: Please update your status or apply to more jobs.",
        "date": datetime.datetime.now().strftime("%d %b, %I:%M %p"),
        "type": "alert",
        "is_read": False
    }
    db.users.update_one({"_id": ObjectId(user_id)}, {"$push": {"notifications": msg}})
    flash('Nudge Sent!', 'info')
    return redirect(url_for('main.faculty_dash'))

# --- ADMIN ROUTES ---
@main.route('/admin/dashboard')
@login_required
def admin_dash():
    if current_user.role != 'admin': return redirect(url_for('main.home'))
    
    jobs = list(db.jobs.find())
    students = list(db.users.find({"role": "student"}))
    
    # 1. Update app_count for the table display
    for job in jobs: 
        job['app_count'] = len(job.get('applicants', []))
    
    # 2. OPTIMIZED: Use Mongo Aggregation for Total Apps
    total_apps = Job.get_total_applications_count()
    
    # Keep salary logic in Python as regex parsing is complex in Mongo pipelines
    salaries = []
    for j in jobs:
        s_val = parse_salary(j.get('salary', '0'))
        if s_val > 0: salaries.append(s_val)
    avg_pkg = round(sum(salaries)/len(salaries), 2) if salaries else 0
    
    # 3. OPTIMIZED: Use Mongo Aggregation for Chart Analytics
    job_demand_results = Job.get_skill_demand()
    stu_supply_dict = User.get_skill_supply()
    
    # Format data for Chart.js
    labels = []
    data_demand = []
    data_supply = []
    
    for item in job_demand_results:
        skill_name = item['_id']
        labels.append(skill_name.title()) # Capitalize for the UI
        data_demand.append(item['count'])
        # Look up the supply from our O(1) dictionary, default to 0 if no students have it
        data_supply.append(stu_supply_dict.get(skill_name, 0))

    return render_template('admin_dash.html', 
                           jobs=jobs, 
                           students=students, 
                           total_apps=total_apps, 
                           avg_package=avg_pkg, 
                           labels=labels, 
                           data_demand=data_demand, 
                           data_supply=data_supply)

@main.route('/job/create', methods=['GET', 'POST'])
@login_required
def create_job():
    if current_user.role != 'admin': return redirect(url_for('main.home'))
    if request.method == 'POST':
        amount = request.form.get('salary_amount')
        period = request.form.get('salary_period')
        full_salary = f"{amount} {period}"
        Job.create_job(request.form.get('title'), request.form.get('company'), request.form.get('skills'), request.form.get('description'), current_user.name, full_salary)
        flash('Job Posted', 'success')
        return redirect(url_for('main.admin_dash'))
    return render_template('add_job.html')

@main.route('/job/delete/<job_id>')
@login_required
def delete_job(job_id):
    if current_user.role != 'admin': return redirect(url_for('main.home'))
    Job.delete_job(job_id)
    flash('Job Closed', 'success')
    return redirect(url_for('main.admin_dash'))

@main.route('/admin/job/<job_id>/manage')
@login_required
def manage_job_applicants(job_id):
    if current_user.role != 'admin': return redirect(url_for('main.home'))
    job = db.jobs.find_one({"_id": ObjectId(job_id)})
    return render_template('manage_job.html', job=job)

@main.route('/admin/sync_external')
@login_required
def run_data_pipeline():
    if current_user.role != 'admin': return redirect(url_for('main.home'))
    
    success, count = sync_external_jobs()
    
    if success:
        flash(f'Pipeline Success: Synchronized {count} new real-world jobs from Adzuna API.', 'success')
    else:
        flash('Pipeline Failed. Check API credentials or rate limits.', 'danger')
        
    return redirect(url_for('main.admin_dash'))

# --- PROFESSIONAL NOTIFICATION LOGIC ---
import uuid
import datetime
from bson.objectid import ObjectId

@main.route('/admin/job/<job_id>/update/<user_id>/<action>')
@login_required
def update_application_status(job_id, user_id, action):
    # 1. Security Check
    if current_user.role != 'admin': 
        return redirect(url_for('main.home'))
    
    # 2. Fetch Job Details (Critical for professional messages)
    job = db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        flash('Job details not found.', 'danger')
        return redirect(url_for('main.admin_dash'))

    job_title = job['title']
    company = job['company']
    
    # 3. Map Action to Status
    status_map = {
        'interview': 'Interviewing', 
        'hire': 'Hired', 
        'reject': 'Rejected', 
        'hold': 'Hold'
    }
    new_status = status_map.get(action)
    
    # 4. Update Logic
    if new_status:
        # A. Update the status in Job & User tables
        Job.update_applicant_status(job_id, user_id, new_status)
        
        # B. Define Professional Notification Content
        # Default fallback
        title = "Application Update"
        text = f"Your application status for {job_title} at {company} is now: {new_status}."
        n_type = "info"
        
        if new_status == 'Hired':
            title = "🎉 Offer Extended!"
            text = f"Congratulations! You have been selected for the {job_title} position at {company}. Check your email for the official offer letter."
            n_type = "success"

        elif new_status == 'Interviewing':
            title = "📹 Interview Invitation"
            text = f"Great news! Your application for {job_title} at {company} has been shortlisted. The HR team will contact you shortly."
            n_type = "warning" 

        elif new_status == 'Rejected':
            title = "Application Update"
            text = f"Thank you for your interest in the {job_title} role at {company}. Unfortunately, we will not be moving forward with your application at this time."
            n_type = "danger"
            
        elif new_status == 'Hold':
            title = "Application On Hold"
            text = f"Your application for {job_title} at {company} is currently on hold. We will notify you of any updates."
            n_type = "info"

        # C. Create Notification Object (Dictionary)
        msg = {
            "id": str(uuid.uuid4()),  # Unique ID required for the popup
            "title": title,
            "text": text,
            "date": datetime.datetime.now().strftime("%d %b, %I:%M %p"),
            "type": n_type,
            "is_read": False
        }

        # D. Push to Database
        db.users.update_one(
            {"_id": ObjectId(user_id)}, 
            {"$push": {"notifications": msg}}
        )

        # --- NEW: EMIT REAL-TIME WEBSOCKET EVENT ---
        socketio.emit('new_notification', {
            'target_user_id': str(user_id), 
            'notification': msg
        })
        
        flash(f'Status updated to {new_status}', 'success')
    
    # 5. Return (This was the cause of your IndentationError)
    return redirect(url_for('main.manage_job_applicants', job_id=job_id))

@main.route('/admin/verify/<user_id>')
@login_required
def admin_verify_student(user_id):
    if current_user.role != 'admin': return redirect(url_for('main.home'))
    db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"verification_status": "Admin Verified"}})
    flash('Student Approved.', 'success')
    return redirect(url_for('main.admin_dash'))

@main.route('/admin/reject/<user_id>')
@login_required
def admin_reject_student(user_id):
    if current_user.role != 'admin': return redirect(url_for('main.home'))
    db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"verification_status": "Rejected"}})
    flash('Student Rejected.', 'warning')
    return redirect(url_for('main.admin_dash'))

@main.route('/notifications/mark_read')
@login_required
def mark_notifications_read():
    # 1. Fetch the user's current data directly from DB
    user = db.users.find_one({"_id": ObjectId(current_user.id)})
    
    if not user or 'notifications' not in user:
        return redirect(url_for('main.notifications'))

    raw_notifications = user.get('notifications', [])
    clean_notifications = []
    
    # 2. Loop through to Clean & Update
    for note in raw_notifications:
        # CASE A: If it's an old Text String (Legacy)
        if isinstance(note, str):
            clean_notifications.append({
                "id": str(uuid.uuid4()),
                "title": "System Alert",
                "text": note,
                "date": datetime.datetime.now().strftime("%d %b, %I:%M %p"), # Assign current date
                "type": "info",
                "is_read": True  # Mark as read
            })
            
        # CASE B: If it's already a Dictionary (New Format)
        elif isinstance(note, dict):
            note['is_read'] = True  # Just update the status
            clean_notifications.append(note)
            
    # 3. Overwrite the database with the clean list
    db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"notifications": clean_notifications}}
    )
    
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('main.notifications'))

@main.route('/notifications/delete/<note_id>')
@login_required
def delete_notification(note_id):
    # MongoDB $pull removes an item from an array that matches the query
    db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$pull": {"notifications": {"id": note_id}}}
    )
    flash('Message deleted.', 'success')
    return redirect(url_for('main.notifications'))

# --- NEW: Delete Student Route ---
@main.route('/delete_student/<user_id>')
@login_required
def delete_student(user_id):
    # Security: Allow both Admin and Faculty to delete
    if current_user.role not in ['admin', 'faculty']: 
        return redirect(url_for('main.home'))
    
    User.delete_user(user_id)
    flash('Student account permanently deleted.', 'success')
    
    # Redirect back to the correct dashboard based on who clicked it
    if current_user.role == 'admin':
        return redirect(url_for('main.admin_dash'))
    return redirect(url_for('main.faculty_dash'))

# --- NEW: Mark Single Notification Read ---
@main.route('/notifications/mark_read/<note_id>')
@login_required
def mark_single_notification_read(note_id):
    db.users.update_one(
        {"_id": ObjectId(current_user.id), "notifications.id": note_id},
        {"$set": {"notifications.$.is_read": True}}
    )
    return redirect(url_for('main.notifications'))