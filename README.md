# 🎓 InternTrack

An intelligent placement analytics and real-time job aggregation platform built to modernize traditional institutional recruitment systems using Machine Learning, Natural Language Processing, and automated ETL pipelines.

---

## 📌 Project Overview

InternTrack bridges the gap between academic preparation and real-world market demands by transforming static placement portals into proactive, data-driven ecosystems. The application automates resume skill extraction, predicts placement readiness, aggregates live job listings from external markets, and provides tailored dashboards for students, faculty, and administrators.

This project was developed in partial fulfillment of the requirements for the Bachelor of Engineering in Computer Engineering at St. Francis Institute of Technology (A.Y. 2025–26).

---

## ✨ Key Features

* **Automated Skill Extraction (NLP):** Extracts structured technical skills from unstructured resume PDFs using spaCy Named Entity Recognition (NER) to eliminate manual data entry errors.
* **Placement Success Prediction (ML):** Evaluates a student's probability of securing a placement using a Random Forest classifier trained on CGPA, technical skills, and application activity.
* **Real-Time Job Aggregation (ETL Pipeline):** Fetches live job opportunities via the Adzuna REST API, processes data through an ETL pipeline, and matches opportunities using TF-IDF vectorization and Cosine Similarity scoring.
* **Role-Based Dashboards:**
  * **Student Dashboard:** View placement probability, profile strength, applications, and AI-driven job recommendations.
  * **Faculty Dashboard:** Monitor student performance and identify at-risk students for proactive intervention.
  * **Admin Console:** Manage campus job postings, system analytics, and Skill Demand vs. Supply visual metrics.
* **Low-Latency Communication:** Real-time updates and notification delivery integrated using WebSockets.

---

## 📁 Project Structure

```text
InternTrack/
│
├── app.py                   # Main Flask application entry point
├── config.py                # Environment configurations & API settings
├── requirements.txt         # Project dependencies (spaCy, scikit-learn, PyMongo, etc.)
├── README.md                # Project documentation
│
├── modules/                 # Core backend business logic & modules
│   ├── __init__.py
│   ├── nlp_parser.py        # spaCy NER engine for resume parsing & skill normalization
│   ├── predictor.py         # Random Forest ML model for placement probability calculation
│   ├── job_aggregator.py    # Adzuna API ETL pipeline logic
│   └── matcher.py           # TF-IDF & Cosine Similarity matching algorithms
│
├── database/                # Database models & connections
│   ├── __init__.py
│   └── mongo_setup.py       # MongoDB schemas & aggregation pipeline setup
│
├── routes/                  # Controller routes for different roles
│   ├── __init__.py
│   ├── student_routes.py    # Student profile, resume upload, & recommendations
│   ├── faculty_routes.py    # Faculty analytics & student intervention system
│   └── admin_routes.py      # Admin dashboard & campus job management
│
├── templates/               # Frontend HTML templates
│   ├── landing.html         # Portal landing page
│   ├── student_dash.html    # Student dashboard view
│   ├── faculty_dash.html    # Faculty overview & analytics view
│   └── admin_dash.html      # Admin console view
│
├── static/                  # Static assets & scripts
│   ├── css/                 # Modern UI styling & themes
│   ├── js/                  # Client-side scripts & WebSocket handlers
│   └── images/              # Dynamic UI icons & branding assets
│
└── uploads/                 # Temporary storage for student resume uploads (.pdf)
