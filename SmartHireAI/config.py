import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Admin credentials
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # Change in production

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Email Configuration
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Database Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "Cluster0")

# Application Settings
FIT_SCORE_THRESHOLD = 70  # Default threshold for candidate selection
ALLOWED_RESUME_EXTENSIONS = {'pdf', 'docx'}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB

# Email Templates
EMAIL_TEMPLATES = {
    "selected": {
        "subject": "Interview Shortlist - Faculty Position",
        "body": """Dear {candidate_name},
        
Congratulations! We are pleased to inform you that you have been shortlisted for an interview for the {job_title} position.

We will contact you shortly with further details about the interview process.

Best regards,
SmartHire AI Team"""
    },
    "rejected": {
        "subject": "Application Status Update - Faculty Position",
        "body": """Dear {candidate_name},

Thank you for your interest in the {job_title} position and for taking the time to apply.

After careful consideration, we regret to inform you that we will not be moving forward with your application at this time.

We wish you the best in your future endeavors.

Best regards,
SmartHire AI Team"""
    }
}