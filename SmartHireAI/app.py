import streamlit as st
import os
import sys
import json
from datetime import datetime
from agents.job_role_agent import JobRoleAgent
from agents.resume_parser_agent import ResumeParserAgent
from agents.email_agent import EmailAgent
from agents.orchestration_graph import OrchestrationGraph
from utils.db_manager import DatabaseManager
from utils.file_handler import FileHandler
from config import ADMIN_USERNAME, ADMIN_PASSWORD, FIT_SCORE_THRESHOLD

# Initialize database and components
try:
    db = DatabaseManager()
except Exception as e:
    st.error(f"Failed to initialize database: {str(e)}")
    st.stop()

file_handler = FileHandler()
orchestrator = OrchestrationGraph()

# Create uploads directory if it doesn't exist
if not os.path.exists('uploads'):
    os.makedirs('uploads')

# Set page config
st.set_page_config(
    page_title="SmartHire AI",
    page_icon="🎓",
    layout="wide"
)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def login():
    """Handle admin login"""
    st.title("Admin Login")
    st.markdown("""
        <style>
            .stTextInput > label {
                font-weight: 500;
                margin-bottom: 0.5rem;
            }
            .stTextInput > div > div > input {
                border-radius: 4px;
            }
        </style>
    """, unsafe_allow_html=True)
    
    username = st.text_input(
        "Username",
        key="username_input",
        autocomplete="username",
        help="Enter your admin username"
    )
    password = st.text_input(
        "Password",
        type="password",
        key="password_input",
        autocomplete="current-password",
        help="Enter your admin password"
    )
    
    if st.button("Login", key="login_button"):
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            st.session_state.authenticated = True
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid credentials")

def admin_dashboard():
    """Display admin dashboard"""
    st.title("Admin Dashboard")
    
    # Sidebar for navigation
    page = st.sidebar.radio("Navigation", ["Job Postings", "Applications"])
    
    if page == "Job Postings":
        show_job_postings()
    else:
        show_applications()

def show_job_postings():
    """Display and manage job postings"""
    st.header("Job Postings")
    
    # Create new job posting
    with st.expander("Create New Job Posting"):
        with st.form("job_posting_form"):
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Job Title")
            with col2:
                salary = st.number_input("Salary", min_value=0.0, step=1000.0, value=50000.0)
            
            submitted = st.form_submit_button("Generate Job Posting")
            if submitted:
                if title and salary:
                    with st.spinner("Generating job details..."):
                        try:
                            # Check if GEMINI_API_KEY is configured
                            if not os.getenv('GEMINI_API_KEY'):
                                st.error("Gemini API key is not configured. Please check your .env file.")
                                st.info("Add your Gemini API key to the .env file as GEMINI_API_KEY=your_key_here")
                                return
                            
                            result = orchestrator.process_job_creation(title, salary)
                            if result and result.get('status') == 'success':
                                st.success("Job posting created successfully!")
                                st.balloons()
                                st.rerun()
                            else:
                                error_msg = result.get('error', 'Unknown error') if result else 'No response from server'
                                st.error(f"Error creating job posting: {error_msg}")
                                if "API key" in error_msg:
                                    st.info("Make sure you have added your Gemini API key to the .env file")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                            st.info("If this persists, check your internet connection and Gemini API key configuration.")
                else:
                    st.error("Please fill in both job title and salary.")
    
    # List existing job postings
    try:
        jobs = db.get_all_jobs()
        if jobs:
            for idx, job in enumerate(jobs):
                with st.expander(f"{job['title']} - ${job['salary']:,.2f}"):
                    st.write("**Description:**")
                    st.write(job['description'])
                    
                    if job['responsibilities']:
                        st.write("**Responsibilities:**")
                        responsibilities = job['responsibilities']
                        if isinstance(responsibilities, str):
                            responsibilities = responsibilities.split('\n')
                        for resp in responsibilities:
                            if resp.strip():
                                st.write(f"- {resp.strip()}")
                    
                    if job['required_skills']:
                        st.write("**Required Skills:**")
                        skills = job['required_skills']
                        if isinstance(skills, str):
                            skills = skills.split('\n')
                        for skill in skills:
                            if skill.strip():
                                st.write(f"- {skill.strip()}")
                    
                    if job['qualifications']:
                        st.write("**Qualifications:**")
                        qualifications = job['qualifications']
                        if isinstance(qualifications, str):
                            qualifications = qualifications.split('\n')
                        for qual in qualifications:
                            if qual.strip():
                                st.write(f"- {qual.strip()}")
                    
                    # Actions
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"Delete Job", key=f"delete_{idx}"):
                            try:
                                if db.delete_job(job['id']):
                                    st.success("Job deleted successfully!")
                                    st.rerun()
                                else:
                                    st.error("Failed to delete job.")
                            except Exception as e:
                                st.error(f"Error deleting job: {str(e)}")
                    
                    with col2:
                        if st.button(f"View Applications", key=f"view_{idx}"):
                            st.session_state.selected_job_id = job['id']
                            st.session_state.page = 'admin_applications'
                            st.rerun()
        else:
            st.info("No job postings available.")
    except Exception as e:
        st.error(f"Error loading job postings: {str(e)}")

def show_applications():
    """Display and manage applications"""
    st.header("Applications")
    
    # Filter by job
    jobs = db.get_all_jobs()
    job_titles = {job['id']: job['title'] for job in jobs}
    selected_job = st.selectbox(
        "Select Job Posting",
        options=list(job_titles.keys()),
        format_func=lambda x: job_titles[x]
    )
    
    # Fit score threshold adjustment
    threshold = st.slider(
        "Fit Score Threshold",
        min_value=0,
        max_value=100,
        value=FIT_SCORE_THRESHOLD
    )
    
    # Display applications
    applications = db.get_applications_by_job(selected_job)
    if applications:
        for app in applications:
            with st.expander(f"{app['full_name']} - {app['email']} - Job: {job_titles[selected_job]} (ID: {selected_job})"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.write(f"**Age:** {app['age']}")
                with col2:
                    st.write(f"**Gender:** {app['gender']}")
                with col3:
                    st.write(f"**Applied:** {datetime.fromisoformat(app['applied_at']).strftime('%Y-%m-%d')}")
                with col4:
                    st.write(f"**Job Title:** {job_titles[selected_job]}")
                st.write(f"**Job ID:** {selected_job}")
                
                st.write("**Fit Score:**")
                if app['fit_score'] is not None:
                    try:
                        score = float(app['fit_score'])
                        score_color = "green" if score >= threshold else "red"
                        st.markdown(f"<h3 style='color: {score_color}'>{score:.1f}/100</h3>", unsafe_allow_html=True)
                    except (ValueError, TypeError):
                        st.warning("Score calculation pending")
                else:
                    st.warning("Score calculation pending")
                    
                st.write("**Status:**", app['status'].title() if app['status'] else "Pending")
                
                # Display detailed scores if available
                if app.get('parsed_scores'):
                    try:
                        scores = app['parsed_scores']
                        # Handle the case where scores might be a JSON string
                        if isinstance(scores, str):
                            try:
                                scores = json.loads(scores)
                            except json.JSONDecodeError:
                                scores = None
                                
                        if isinstance(scores, dict):
                            st.write("**Detailed Scores:**")
                            for category, score in scores.items():
                                if category != 'reasoning':
                                    try:
                                        st.write(f"- {category.replace('_', ' ').title()}: {float(score):.1f}")
                                    except (ValueError, TypeError):
                                        continue
                            if 'reasoning' in scores:
                                st.write("**Reasoning:**")
                                st.markdown(f"```\n{scores['reasoning']}\n```")
                    except Exception as e:
                        st.error(f"Error displaying scores: {str(e)}")
                
                if st.button(f"Download Resume #{app['id']}"):
                    if os.path.exists(app['resume_path']):
                        with open(app['resume_path'], 'rb') as f:
                            st.download_button(
                                "Download Resume",
                                f,
                                file_name=os.path.basename(app['resume_path'])
                            )
    else:
        st.info("No applications found for this job posting.")

def candidate_portal():
    """Display candidate portal"""
    st.title("Faculty Position Applications")
    
    # List active job postings
    jobs = db.get_all_jobs(active_only=True)
    
    for job in jobs:
        with st.expander(f"{job['title']} - ${job['salary']:,.2f}"):
            st.write("**Description:**")
            st.write(job['description'])
            
            st.write("**Required Skills:**")
            skills = job['required_skills']
            if isinstance(skills, str):
                skills = skills.split('\n')
            for skill in skills:
                if skill and isinstance(skill, str):
                    st.write(f"- {skill.strip()}")
            
            # Application form
            st.subheader("Apply for this position")
            with st.form(f"application_form_{job['id']}"):
                    st.markdown("""
                        <style>
                            .stTextInput > label, .stNumberInput > label, .stSelectbox > label {
                                font-weight: 500;
                                margin-bottom: 0.5rem;
                            }
                            .stTextInput > div > div > input,
                            .stNumberInput > div > div > input,
                            .stSelectbox > div > div > div {
                                border-radius: 4px;
                            }
                            .required::after {
                                content: "*";
                                color: red;
                                margin-left: 4px;
                            }
                        </style>
                    """, unsafe_allow_html=True)
                    
                    full_name = st.text_input(
                        "Full Name*",
                        key=f"full_name_{job['id']}",
                        autocomplete="name",
                        help="Enter your full name as it appears on official documents"
                    )
                    
                    email = st.text_input(
                        "Email Address*",
                        key=f"email_{job['id']}",
                        autocomplete="email",
                        help="Enter your primary email address"
                    )
                    
                    age = st.number_input(
                        "Age*",
                        min_value=18,
                        max_value=100,
                        key=f"age_{job['id']}",
                        help="Enter your current age"
                    )
                    
                    gender = st.selectbox(
                        "Gender*",
                        ["Male", "Female", "Other", "Prefer not to say"],
                        key=f"gender_{job['id']}",
                        help="Select your gender"
                    )
                    
                    resume_file = st.file_uploader(
                        "Upload Resume (PDF/DOCX)*",
                        type=['pdf', 'docx'],
                        key=f"resume_{job['id']}",
                        help="Upload your resume in PDF or DOCX format"
                    )
                    
                    submit = st.form_submit_button("Submit Application")
            
            if submit:
                if not all([full_name, email, age, gender, resume_file]):
                        st.error("Please fill all fields and upload your resume.")
                else:
                    resume_path = None
                    try:
                        # Validate email format
                        if '@' not in email or '.' not in email:
                            st.error("Please enter a valid email address.")
                            return
                            
                        # Save resume with enhanced error handling
                        try:
                            resume_path = file_handler.save_resume(resume_file)
                        except ValueError as ve:
                            st.error(f"Resume upload error: {str(ve)}")
                            return
                        except Exception as e:
                            st.error("Failed to save resume file. Please try uploading again.")
                            st.error(f"Error details: {str(e)}")
                            return
                            
                        # Create application record with error handling
                        try:
                            application = db.create_application(
                                job_id=job['id'],
                                full_name=full_name,
                                email=email,
                                age=age,
                                gender=gender,
                                resume_path=resume_path
                            )
                            
                            if not application:
                                raise ValueError("Failed to create application record")
                                
                        except Exception as e:
                            if resume_path and os.path.exists(resume_path):
                                try:
                                    os.remove(resume_path)
                                except:
                                    pass
                            st.error(f"Failed to create application: {str(e)}")
                            return
                        
                        # Extract and process resume text
                        resume_text = file_handler.extract_resume_text(resume_path)
                        if not resume_text:
                            if resume_path and os.path.exists(resume_path):
                                try:
                                    os.remove(resume_path)
                                except:
                                    pass
                            st.error("Could not extract text from the resume. Please ensure the file is not corrupted or password protected.")
                            return
                        
                        # Process application through orchestrator
                        with st.spinner("Processing your application..."):
                            try:
                                result = orchestrator.process_application_submission(
                                    application_id=application['id'],
                                    resume_text=resume_text,
                                    job_id=job['id']
                                )
                                
                                if not isinstance(result, dict):
                                    raise ValueError("Invalid response from application processor")
                                    
                                if result.get('status') == 'success':
                                    st.success("Your application has been submitted successfully!")
                                    st.info("You will receive an email notification about your application status.")
                                else:
                                    error_msg = result.get('error', 'Unknown error occurred during processing')
                                    st.error(f"Application processing failed: {error_msg}")
                                    # Keep the file and application record for manual review
                                    
                            except Exception as e:
                                st.error(f"Error during application processing: {str(e)}")
                                st.info("Your application has been saved and will be reviewed manually.")
                                
                    except Exception as e:
                        st.error(f"Unexpected error during application submission: {str(e)}")
                        # Clean up any saved files if we failed
                        if resume_path and os.path.exists(resume_path):
                            try:
                                os.remove(resume_path)
                            except:
                                pass

def main():
    """Main application entry point"""
    # Add a back button in the sidebar
    if 'page' in st.session_state and st.session_state.page != 'home':
        if st.sidebar.button("← Back to Home"):
            st.session_state.page = 'home'
            st.session_state.authenticated = False
            st.rerun()

    # Landing page
    if 'page' not in st.session_state or st.session_state.page == 'home':
        st.title("Welcome to SmartHire AI")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Admin", key="admin_button"):
                st.session_state.page = 'admin'
                st.rerun()
        
        with col2:
            if st.button("Candidate", key="candidate_button"):
                st.session_state.page = 'candidate'
                st.rerun()
    
    # Route to appropriate page
    elif st.session_state.page == 'admin':
        if not st.session_state.authenticated:
            login()
        else:
            admin_dashboard()
    
    elif st.session_state.page == 'candidate':
        candidate_portal()

if __name__ == "__main__":
    # Initialize session state variables
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'page' not in st.session_state:
        st.session_state.page = 'home'
    main()