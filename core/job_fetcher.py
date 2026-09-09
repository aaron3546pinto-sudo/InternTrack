import os
import requests
from core import db
import datetime
# Import our new text scanner
from core.ai_service import extract_skills_from_text 

def sync_external_jobs():
    """
    Data Engineering Pipeline: Fetches real-world jobs from Adzuna,
    uses NLP to extract specific skills from the description, 
    and maps it to the InternTrack DB schema.
    """
    app_id = os.getenv('ADZUNA_APP_ID')
    app_key = os.getenv('ADZUNA_APP_KEY')
    
    url = f"https://api.adzuna.com/v1/api/jobs/in/search/1?app_id={app_id}&app_key={app_key}&results_per_page=15&what=software%20intern&where=Mumbai"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            new_jobs = 0
            
            for job in data.get('results', []):
                if not db.jobs.find_one({"ext_id": str(job['id'])}):
                    
                    raw_description = job.get('description', '')
                    
                    # --- NEW: AI SKILL EXTRACTION ---
                    # Scan the description for exact matches (e.g., HTML, Java, Python)
                    extracted_skills = extract_skills_from_text(raw_description)
                    
                    # If the NLP couldn't find specific skills, provide a baseline fallback
                    final_skills = extracted_skills if extracted_skills else "Software Engineering"
                    
                    db.jobs.insert_one({
                        "title": job.get('title').replace('<strong>', '').replace('</strong>', ''),
                        "company": job.get('company', {}).get('display_name', 'External Company'),
                        "description": raw_description,
                        "skills": final_skills, # Now contains specific tech stack
                        "salary": "See Listing",
                        "posted_by": "Adzuna API",
                        "ext_id": str(job['id']),
                        "source": "External",
                        "url": job.get('redirect_url'),
                        "applicants": [],
                        "posted_date": datetime.datetime.now()
                    })
                    new_jobs += 1
            return True, new_jobs
        return False, 0
    except Exception as e:
        print(f"API Pipeline Error: {e}")
        return False, 0