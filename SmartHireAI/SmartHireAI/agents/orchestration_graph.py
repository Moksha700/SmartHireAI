from typing import Dict
import sys
import os

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.job_role_agent import JobRoleAgent
from agents.resume_parser_agent import ResumeParserAgent
from agents.email_agent import EmailAgent
from utils.db_manager import DatabaseManager

class OrchestrationGraph:
    def __init__(self):
        self.job_agent = JobRoleAgent()
        self.resume_agent = ResumeParserAgent()
        self.email_agent = EmailAgent()
        self.db = DatabaseManager()
    
    def _process_job_posting(self, state: Dict) -> Dict:
        """Process new job posting"""
        try:
            # Extract job details from state
            title = state.get('job_title')
            salary = state.get('salary')
            
            # Generate job details
            job_details = self.job_agent.generate_job_details(title, salary)
            
            if job_details:
                # Store in database
                job = self.db.create_job(
                    title=title,
                    salary=salary,
                    description=job_details['description'],
                    responsibilities=job_details['responsibilities'],
                    required_skills=job_details['required_skills'],
                    qualifications=job_details['qualifications']
                )
                
                # Update state
                state['job_id'] = job['id']
                state['status'] = 'success'
                state['job_details'] = job_details
            else:
                state['status'] = 'error'
                state['error'] = 'Failed to generate job details'
            
        except Exception as e:
            state['status'] = 'error'
            state['error'] = str(e)
        
        return state
    
    def _process_application(self, state: Dict) -> Dict:
        """Process job application"""
        try:
            # Extract application details
            application_id = state.get('application_id')
            resume_text = state.get('resume_text')
            job_id = state.get('job_id')
            
            # Get job details
            job = self.db.get_job(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")
            
            # Parse resume
            parsed_resume = self.resume_agent.parse_resume(resume_text)
            
            if parsed_resume:
                # Calculate fit score
                job_details = {
                    'description': job['description'],
                    'responsibilities': job['responsibilities'],
                    'required_skills': job['required_skills'],
                    'qualifications': job['qualifications']
                }
                
                scores = self.resume_agent.calculate_fit_score(parsed_resume, job_details)
                
                if scores:
                    # Update application with score
                    overall_score = scores['overall_fit_score']
                    status = 'selected' if overall_score >= 70 else 'rejected'
                    
                    self.db.update_application_score(
                        application_id=application_id,
                        fit_score=overall_score,
                        status=status
                    )
                    
                    # Update state
                    state['status'] = 'success'
                    state['scores'] = scores
                    state['application_status'] = status
                else:
                    state['status'] = 'error'
                    state['error'] = 'Failed to calculate fit score'
            else:
                state['status'] = 'error'
                state['error'] = 'Failed to parse resume'
            
        except Exception as e:
            state['status'] = 'error'
            state['error'] = str(e)
        
        return state
    
    def _handle_notifications(self, state: Dict) -> Dict:
        """Handle email notifications"""
        try:
            if state.get('status') == 'success':
                # Get application details
                application = self.db.get_application(state['application_id'])
                job = self.db.get_job(state['job_id'])
                
                if application and job:
                    # Send appropriate email
                    if application['status'] == 'selected':
                        self.email_agent.send_selection_email(
                            candidate_name=application['full_name'],
                            email=application['email'],
                            job_title=job['title']
                        )
                    else:
                        self.email_agent.send_rejection_email(
                            candidate_name=application['full_name'],
                            email=application['email'],
                            job_title=job['title']
                        )
                    
                    state['notification_sent'] = True
                else:
                    state['notification_sent'] = False
                    state['error'] = 'Application or job not found'
            
        except Exception as e:
            state['notification_sent'] = False
            state['error'] = str(e)
        
        return state
    
    def process_job_creation(self, title: str, salary: float) -> Dict:
        """Process job creation workflow"""
        try:
            # Generate job details
            job_details = self.job_agent.generate_job_details(title, salary)
            
            if job_details and 'status' not in job_details:  # Not an error response
                try:
                    # Store in database
                    job = self.db.create_job(
                        title=title,
                        salary=salary,
                        description=job_details['description'],
                        responsibilities=job_details['responsibilities'],
                        required_skills=job_details['required_skills'],
                        qualifications=job_details['qualifications']
                    )
                    
                    return {
                        'status': 'success',
                        'job_id': job['id'],
                        'job_details': job_details
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'error': f'Failed to save job details: {str(e)}'
                    }
            else:
                error_msg = job_details.get('error', 'Failed to generate job details') if job_details else 'No response from job generator'
                return {
                    'status': 'error',
                    'error': error_msg
                }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def process_application_submission(
        self, 
        application_id: int,
        resume_text: str,
        job_id: int
    ) -> Dict:
        """Process application submission workflow
        
        Args:
            application_id (int): The ID of the application to process
            resume_text (str): The text content of the resume
            job_id (int): The ID of the job being applied for
            
        Returns:
            Dict: Processing result with status and details
        """
        try:
            # Validate inputs
            if not resume_text or not resume_text.strip():
                return {
                    'status': 'error',
                    'error': 'Resume text is empty or invalid'
                }
                
            # Get job details
            job = self.db.get_job(job_id)
            if not job:
                return {
                    'status': 'error',
                    'error': f"Job not found: {job_id}"
                }
            
            # Parse resume with enhanced error handling
            try:
                parsed_resume = self.resume_agent.parse_resume(resume_text)
                if not parsed_resume:
                    return {
                        'status': 'error',
                        'error': 'Resume parsing returned no valid information'
                    }
                
                # Validate parsed resume structure
                required_sections = ['education', 'skills', 'experience']
                missing_sections = [section for section in required_sections if not parsed_resume.get(section)]
                if missing_sections:
                    return {
                        'status': 'error',
                        'error': f'Resume parsing incomplete. Missing sections: {", ".join(missing_sections)}'
                    }
                    
            except ValueError as ve:
                return {
                    'status': 'error',
                    'error': f'Resume parsing failed: {str(ve)}'
                }
            except Exception as e:
                return {
                    'status': 'error',
                    'error': f'Unexpected error during resume parsing: {str(e)}'
                }
            
            # Calculate fit score with enhanced job details
            try:
                job_details = {
                    'description': job['description'],
                    'responsibilities': job['responsibilities'],
                    'required_skills': job['required_skills'],
                    'qualifications': job['qualifications']
                }
                
                scores = self.resume_agent.calculate_fit_score(parsed_resume, job_details)
                if not scores:
                    return {
                        'status': 'error',
                        'error': 'Failed to calculate fit score'
                    }
                
                # Validate scores structure
                required_scores = ['skill_match_score', 'experience_relevance_score', 
                                 'education_alignment_score', 'overall_fit_score']
                if not all(key in scores for key in required_scores):
                    return {
                        'status': 'error',
                        'error': 'Incomplete scoring results'
                    }
                    
                # Update application with score and enhanced status
                try:
                    overall_score = scores['overall_fit_score']
                    skill_match = scores['skill_match_score']
                    
                    # More nuanced selection criteria
                    status = 'selected' if (overall_score >= 70 and skill_match >= 60) else 'rejected'
                    
                    application = self.db.update_application_score(
                        application_id=application_id,
                        fit_score=overall_score,
                        status=status,
                        detailed_scores=scores  # Store the detailed scoring information
                    )
                    
                    if not application:
                        return {
                            'status': 'error',
                            'error': 'Failed to update application with scores'
                        }
                        
                    # Handle email notifications
                    try:
                        if status == 'selected':
                            self.email_agent.send_selection_email(
                                candidate_name=application['full_name'],
                                email=application['email'],
                                job_title=job['title']
                            )
                        else:
                            self.email_agent.send_rejection_email(
                                candidate_name=application['full_name'],
                                email=application['email'],
                                job_title=job['title']
                            )
                            
                        return {
                            'status': 'success',
                            'scores': scores,
                            'application_status': status,
                            'parsed_resume': parsed_resume  # Include parsed data for reference
                        }
                        
                    except Exception as e:
                        # Continue even if email fails
                        print(f"Warning: Failed to send notification email: {e}")
                        return {
                            'status': 'success',
                            'scores': scores,
                            'application_status': status,
                            'parsed_resume': parsed_resume,
                            'warning': 'Application processed but notification email failed'
                        }
                        
                except Exception as e:
                    return {
                        'status': 'error',
                        'error': f'Failed to update application: {str(e)}'
                    }
                    
            except Exception as e:
                return {
                    'status': 'error',
                    'error': f'Error during scoring: {str(e)}'
                }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Unexpected error in application processing: {str(e)}'
            }