import pdfplumber
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.ensemble import RandomForestClassifier
import numpy as np
import os

# Load English NLP model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import spacy.cli
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# Comprehensive list of tech skills for NER matching
TECH_SKILLS_DB = {
    "python", "java", "c++", "c", "javascript", "typescript", "html", "css",
    "react", "angular", "vue", "node.js", "express", "django", "flask", "spring boot",
    "sql", "mysql", "postgresql", "mongodb", "oracle", "nosql",
    "machine learning", "deep learning", "nlp", "data science", "pandas", "numpy", "scikit-learn",
    "aws", "azure", "gcp", "docker", "kubernetes", "git", "linux", "data structures", "algorithms"
}

def extract_skills_from_text(text):
    """
    NLP Engine: Scans any raw text string and uses Named Entity Recognition 
    to extract specific technical skills.
    """
    if not text:
        return ""

    doc = nlp(text.lower())
    found_skills = set()

    for token in doc:
        if token.text in TECH_SKILLS_DB:
            found_skills.add(token.text.title())
            
    for chunk in doc.noun_chunks:
        if chunk.text in TECH_SKILLS_DB:
            found_skills.add(chunk.text.title())

    return ", ".join(list(found_skills))

def extract_skills_from_pdf(pdf_path):
    """
    Reads a PDF and passes the text to the NLP Engine.
    """
    if not os.path.exists(pdf_path):
        return ""

    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + " "
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

    # Pass the raw text to our new reusable function
    return extract_skills_from_text(text)

def calculate_similarity(student_skills, jobs):
    """
    Matches student skills against Job Title + Skills + Description.
    """
    if not jobs: return []
    if not student_skills: return jobs

    job_texts = [f"{j['title']} {j['skills']} {j['skills']} {j['description']}" for j in jobs]
    documents = [student_skills] + job_texts
    
    tfidf = TfidfVectorizer(stop_words='english')
    matrix = tfidf.fit_transform(documents)
    
    cosine_sim = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    
    ranked_jobs = []
    for i, score in enumerate(cosine_sim):
        job = jobs[i]
        job['match_score'] = round(score * 100) 
        job['_id'] = str(job['_id'])
        
        if job['match_score'] > 5:
            ranked_jobs.append(job)
    
    return sorted(ranked_jobs, key=lambda x: x['match_score'], reverse=True)

def predict_placement_probability(cgpa, skill_count, applied_jobs_count):
    """
    ML Engine: Predicts the likelihood of a student getting placed.
    Uses a Random Forest Classifier trained on synthetic historical data.
    """
    try:
        cgpa = float(cgpa) if cgpa else 0.0
    except ValueError:
        cgpa = 0.0

    # SYNTHETIC DATASET (For demonstration purposes)
    # Features: [CGPA, Number of Skills, Number of Jobs Applied To]
    # Labels: 1 (Placed), 0 (Not Placed)
    X_train = np.array([
        [9.5, 8, 5], [8.0, 5, 10], [6.5, 2, 2], [7.5, 4, 15],
        [9.0, 6, 3], [5.5, 1, 1], [8.5, 7, 8], [7.0, 3, 5],
        [9.8, 10, 2], [6.0, 2, 10]
    ])
    y_train = np.array([1, 1, 0, 1, 1, 0, 1, 0, 1, 0])

    # Initialize and train the model
    rf_model = RandomForestClassifier(n_estimators=50, random_state=42)
    rf_model.fit(X_train, y_train)

    # Predict probability for the current student
    student_features = np.array([[cgpa, skill_count, applied_jobs_count]])
    probability = rf_model.predict_proba(student_features)[0][1] # Get probability of class 1
    
    return round(probability * 100)