from pymongo import MongoClient, errors
from datetime import datetime
import json
from bson import ObjectId
from config import MONGODB_URI, DATABASE_NAME
import urllib.parse

class DatabaseManager:
    def __init__(self):
        try:
            # Parse the URI to ensure proper encoding
            uri_parts = urllib.parse.urlparse(MONGODB_URI)
            username = urllib.parse.quote_plus(uri_parts.username) if uri_parts.username else None
            password = urllib.parse.quote_plus(uri_parts.password) if uri_parts.password else None
            netloc = uri_parts.netloc.split('@')[-1]  # Get the host:port part
            
            # Reconstruct the URI with encoded components
            encoded_uri = f"mongodb+srv://{username}:{password}@{netloc}"
            if uri_parts.path:
                encoded_uri += uri_parts.path
            if uri_parts.query:
                encoded_uri += f"?{uri_parts.query}"
                
            self.client = MongoClient(encoded_uri)
            # Test the connection
            self.client.admin.command('ping')
            print("Successfully connected to MongoDB")
            self.db = self.client[DATABASE_NAME]
        except errors.ConnectionFailure as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise
        except Exception as e:
            print(f"Error initializing database: {e}")
            raise

    def _format_job_dict(self, job):
        """Convert MongoDB job document to application format"""
        if not job:
            print("Warning: Received empty job document")
            return None
        try:
            # Ensure _id exists and is valid
            if '_id' not in job:
                print("Error: Job document missing _id field")
                return None
                
            formatted_job = {
                'id': str(job['_id']),
                'title': job.get('title', 'Untitled Position'),
                'salary': float(job.get('salary', 0.0)),
                'description': job.get('description', ''),
                'responsibilities': job.get('responsibilities', '').split('\n') if job.get('responsibilities') else [],
                'required_skills': job.get('required_skills', '').split('\n') if job.get('required_skills') else [],
                'qualifications': job.get('qualifications', '').split('\n') if job.get('qualifications') else [],
                'created_at': job.get('created_at', datetime.utcnow()).isoformat(),
                'is_active': bool(job.get('is_active', 1)),
                'department': job.get('department', 'General'),
                'location': job.get('location', 'Remote')
            }
            print(f"Successfully formatted job: {formatted_job['id']} - {formatted_job['title']}")
            return formatted_job
        except Exception as e:
            print(f"Error formatting job document: {e}")
            print(f"Job document content: {job}")
            return None

    def _format_application_dict(self, app):
        """Convert MongoDB application document to application format"""
        if not app:
            return None
        return {
            'id': str(app['_id']),
            'job_id': app['job_id'],
            'full_name': app['full_name'],
            'email': app['email'],
            'age': app['age'],
            'gender': app['gender'],
            'resume_path': app.get('resume_path'),
            'fit_score': app.get('fit_score'),
            'parsed_scores': app.get('parsed_scores'),
            'status': app.get('status', 'pending'),
            'applied_at': app['applied_at'].isoformat() if app.get('applied_at') else None
        }

    def create_job(self, title, salary, description, responsibilities, required_skills, qualifications):
        """Create a new job posting"""
        try:
            # Convert lists to string if necessary
            if isinstance(responsibilities, list):
                responsibilities = '\n'.join(responsibilities)
            if isinstance(required_skills, list):
                required_skills = '\n'.join(required_skills)
            if isinstance(qualifications, list):
                qualifications = '\n'.join(qualifications)

            job_data = {
                'title': title,
                'salary': float(salary),
                'description': description,
                'responsibilities': responsibilities,
                'required_skills': required_skills,
                'qualifications': qualifications,
                'created_at': datetime.utcnow(),
                'is_active': 1
            }
            
            # Insert the job and get its ID
            result = self.db.jobs.insert_one(job_data)
            job_id = str(result.inserted_id)
            
            # Retrieve the job document and format it
            job = self.db.jobs.find_one({'_id': ObjectId(job_id)})
            if not job:
                raise Exception("Failed to retrieve created job")
                
            # Format the job document for response
            return self._format_job_dict(job)
        except Exception as e:
            print(f"Error creating job: {e}")
            raise

    def get_job(self, job_id):
        """Get a job by ID"""
        try:
            job = self.db.jobs.find_one({'_id': ObjectId(job_id)})
            return self._format_job_dict(job)
        except Exception as e:
            print(f"Error getting job: {e}")
            return None

    def get_all_jobs(self, active_only=True):
        """Get all jobs"""
        try:
            query = {'is_active': 1} if active_only else {}
            jobs = list(self.db.jobs.find(query))
            print(f"Found {len(jobs)} jobs in database")
            
            formatted_jobs = []
            for job in jobs:
                formatted_job = self._format_job_dict(job)
                if formatted_job:
                    formatted_jobs.append(formatted_job)
                else:
                    print(f"Warning: Failed to format job: {job.get('_id', 'unknown id')}")
            
            print(f"Successfully formatted {len(formatted_jobs)} jobs")
            return formatted_jobs
        except Exception as e:
            print(f"Error getting all jobs: {e}")
            print("Returning empty list")
            return []

    def update_job(self, job_id, **kwargs):
        """Update a job posting"""
        try:
            update_data = {
                '$set': {
                    **kwargs,
                    'updated_at': datetime.utcnow()
                }
            }
            self.db.jobs.update_one({'_id': ObjectId(job_id)}, update_data)
            return self.get_job(job_id)
        except Exception as e:
            print(f"Error updating job: {e}")
            return None

    def delete_job(self, job_id):
        """Soft delete a job by setting is_active to 0"""
        try:
            result = self.db.jobs.update_one(
                {'_id': ObjectId(job_id)},
                {
                    '$set': {
                        'is_active': 0,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error deleting job: {e}")
            return False

    def create_application(self, job_id, full_name, email, age, gender, resume_path):
        """Create a new application"""
        try:
            application_data = {
                'job_id': job_id,
                'full_name': full_name,
                'email': email,
                'age': int(age),
                'gender': gender,
                'resume_path': resume_path,
                'status': 'pending',
                'applied_at': datetime.utcnow()
            }
            result = self.db.applications.insert_one(application_data)
            return self.get_application(str(result.inserted_id))
        except Exception as e:
            print(f"Error creating application: {e}")
            return None

    def update_application_score(self, application_id, fit_score, status, detailed_scores=None):
        """Update application with score and status information"""
        try:
            update_data = {}
            
            # Handle fit score
            try:
                if fit_score is not None:
                    update_data['fit_score'] = float(fit_score)
                else:
                    update_data['fit_score'] = 50.0
            except (ValueError, TypeError):
                print(f"Warning: Invalid fit score value: {fit_score}, using default")
                update_data['fit_score'] = 50.0
            
            # Handle status
            if status and isinstance(status, str):
                update_data['status'] = status.lower()
            else:
                update_data['status'] = 'pending'
            
            # Handle detailed scores
            if detailed_scores:
                try:
                    if isinstance(detailed_scores, dict):
                        update_data['parsed_scores'] = detailed_scores
                    elif isinstance(detailed_scores, str):
                        update_data['parsed_scores'] = json.loads(detailed_scores)
                except (TypeError, json.JSONDecodeError) as e:
                    print(f"Warning: Could not store detailed scores: {e}")
            
            update_data['updated_at'] = datetime.utcnow()
            
            result = self.db.applications.update_one(
                {'_id': ObjectId(application_id)},
                {'$set': update_data}
            )
            
            if result.modified_count > 0:
                return self.get_application(application_id)
            return None
            
        except Exception as e:
            print(f"Error updating application score: {e}")
            return None

    def get_applications_by_job(self, job_id):
        """Get all applications for a specific job"""
        try:
            applications = list(self.db.applications.find({'job_id': job_id}))
            return [self._format_application_dict(app) for app in applications]
        except Exception as e:
            print(f"Error getting applications by job: {e}")
            return []

    def get_application(self, application_id):
        """Get an application by ID"""
        try:
            application = self.db.applications.find_one({'_id': ObjectId(application_id)})
            return self._format_application_dict(application)
        except Exception as e:
            print(f"Error getting application: {e}")
            return None

    def close(self):
        """Close the MongoDB connection"""
        if self.client:
            self.client.close()