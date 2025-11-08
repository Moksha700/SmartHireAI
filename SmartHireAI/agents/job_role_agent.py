from langchain.prompts import PromptTemplate
import google.generativeai as genai
import json
import sys
import os
import time
from datetime import datetime, timedelta
import random

# Rate limiter class for managing API requests
class RateLimiter:
    def __init__(self, max_requests=2, time_window=60):  # 2 requests per minute for free tier
        self.max_requests = max_requests
        self.time_window = time_window  # in seconds
        self.requests = []
        
    def wait_if_needed(self):
        now = datetime.now()
        # Remove old requests
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < timedelta(seconds=self.time_window)]
        
        if len(self.requests) >= self.max_requests:
            # Calculate required wait time
            oldest_request = min(self.requests)
            wait_time = (oldest_request + timedelta(seconds=self.time_window) - now).total_seconds()
            if wait_time > 0:
                # Add some jitter to avoid thundering herd
                jitter = random.uniform(0.1, 2.0)
                total_wait = wait_time + jitter
                print(f"Rate limit reached. Waiting {total_wait:.2f} seconds...")
                time.sleep(total_wait)
        
        # Add current request
        self.requests.append(now)

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import GEMINI_API_KEY

class JobRoleAgent:
    def __init__(self):
        # Initialize Gemini AI
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            # First try to get available models
            models = genai.list_models()
            available_models = [m.name for m in models]
            print(f"Available models: {available_models}")
            
            # Check for available models
            model_options = [
                'models/gemini-pro-latest',
                'models/gemini-2.5-pro',
                'models/gemini-2.0-pro-exp'
            ]
            
            model_found = False
            for model_name in model_options:
                if model_name in available_models:
                    self.model = genai.GenerativeModel(model_name)
                    print(f"Using model: {model_name}")
                    model_found = True
                    break
                    
            if not model_found:
                raise ValueError(f"No suitable Gemini model found. Available models: {available_models}")
        except Exception as e:
            print(f"Error initializing Gemini AI: {e}")
            raise ValueError(f"Failed to initialize Gemini AI: {str(e)}")
        
        # Initialize prompts
        self.job_description_prompt = PromptTemplate(
            input_variables=["title", "salary"],
            template="""Generate a detailed job description for a faculty position with the following details:
            Title: {title}
            Salary: ${salary}
            
            Please provide a JSON response with the following structure:
            {
                "description": "Full job description",
                "responsibilities": ["List of key responsibilities"],
                "required_skills": ["List of required skills"],
                "qualifications": ["List of preferred qualifications"]
            }
            
            Ensure the description is professional, comprehensive, and suitable for an academic institution."""
        )
    
    def generate_job_details(self, title, salary):
        """Generate complete job details using Gemini AI"""
        try:
            # Check if API key is configured
            if not GEMINI_API_KEY:
                raise ValueError("Gemini API key is not configured. Please check your .env file.")

            # Format the prompt with clear JSON structure
            prompt = f"""Generate a detailed job description for a faculty position with the following details:
            Title: {title}
            Salary: ${salary}

            Return a JSON object with EXACTLY this structure:
            {{
                "description": "A detailed paragraph describing the role and institution",
                "responsibilities": [
                    "Responsibility 1",
                    "Responsibility 2",
                    "..."
                ],
                "required_skills": [
                    "Skill 1",
                    "Skill 2",
                    "..."
                ],
                "qualifications": [
                    "Qualification 1",
                    "Qualification 2",
                    "..."
                ]
            }}
            
            Ensure all arrays have at least 3 items. Keep the description concise but informative."""
            
            print(f"Sending prompt to Gemini AI: {prompt}")
            
            # Get response from Gemini AI
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
            ]
            
            # Initialize rate limiter for this request
            rate_limiter = RateLimiter(max_requests=2, time_window=60)
            
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                try:
                    rate_limiter.wait_if_needed()
                    response = self.model.generate_content(
                        contents=prompt,
                        generation_config=generation_config,
                        safety_settings=safety_settings
                    )
                    
                    if not response.text:
                        raise ValueError("Empty response from Gemini AI")
                    break
                    
                except Exception as api_error:
                    retry_count += 1
                    if "429" in str(api_error) and retry_count < max_retries:  # Rate limit error
                        print(f"Rate limit exceeded, retry {retry_count}/{max_retries}...")
                        time.sleep(35)  # Wait for the rate limit window
                        continue
                    elif retry_count == max_retries:
                        raise ValueError(f"Failed to get response after {max_retries} retries")
                    else:
                        raise  # Re-raise other errors
                
            print(f"Received response from Gemini AI: {response.text}")
            
            try:
                # Try to parse the response as JSON
                job_details = json.loads(response.text)
                
                # Validate the required fields
                required_fields = ['description', 'responsibilities', 
                                 'required_skills', 'qualifications']
                for field in required_fields:
                    if field not in job_details:
                        raise ValueError(f"Missing required field: {field}")
                    if field != 'description' and (
                        not isinstance(job_details[field], list) or 
                        len(job_details[field]) < 1
                    ):
                        raise ValueError(f"Field '{field}' must be a non-empty array")
                
                return job_details
                
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON response: {e}")
                # If JSON parsing fails, try to extract structured data from text
                structured_response = self._parse_unstructured_response(response.text, title=title, salary=salary)
                if not structured_response:
                    raise ValueError("Failed to parse response into required structure")
                return structured_response
                
        except Exception as e:
            error_msg = f"Error generating job details: {str(e)}"
            print(error_msg)
            return {
                'status': 'error',
                'error': error_msg
            }
    
    def _parse_unstructured_response(self, text, title="", salary=0):
        """Parse unstructured response into required format"""
        try:
            sections = {
                'description': '',
                'responsibilities': [],
                'required_skills': [],
                'qualifications': []
            }
            
            # First, try to find JSON-like structure in the text
            import re
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    json_data = json.loads(json_match.group())
                    if all(k in json_data for k in sections.keys()):
                        return json_data
                except:
                    pass
            
            current_section = None
            section_content = []
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Try to identify sections
                lower_line = line.lower()
                
                if any(keyword in lower_line for keyword in ['job description', 'position description', 'overview', 'about the role']):
                    current_section = 'description'
                    section_content = []
                elif any(keyword in lower_line for keyword in ['responsibilities', 'duties', 'role includes', 'you will']):
                    current_section = 'responsibilities'
                    section_content = []
                elif any(keyword in lower_line for keyword in ['required skills', 'skills', 'requirements', 'competencies']):
                    current_section = 'required_skills'
                    section_content = []
                elif any(keyword in lower_line for keyword in ['qualifications', 'education', 'experience required']):
                    current_section = 'qualifications'
                    section_content = []
                elif current_section:
                    # Process line based on section
                    if current_section == 'description':
                        sections['description'] += line + ' '
                    else:
                        # Check if line is a list item
                        cleaned_line = line.lstrip('- ').lstrip('* ').lstrip('•').lstrip('○').strip()
                        # Remove numbered bullets
                        cleaned_line = re.sub(r'^\d+[\.)]\s*', '', cleaned_line)
                        
                        if cleaned_line and not any(cleaned_line.startswith(x) for x in ['description:', 'responsibilities:', 'skills:', 'qualifications:']):
                            sections[current_section].append(cleaned_line)
            
            # Clean up description
            sections['description'] = sections['description'].strip()
            
            # Ensure each section has content
            if not sections['description']:
                sections['description'] = f"We are seeking a qualified candidate for the position of {title} with a competitive salary of ${salary:,.2f}."
            
            for section in ['responsibilities', 'required_skills', 'qualifications']:
                if not sections[section]:
                    sections[section] = ["To be specified"]
            
            # Remove duplicates while preserving order
            for section in ['responsibilities', 'required_skills', 'qualifications']:
                seen = set()
                sections[section] = [x for x in sections[section] if not (x in seen or seen.add(x))]
            
            return sections
            
        except Exception as e:
            print(f"Error parsing unstructured response: {e}")
            return None
    
    def validate_and_clean_job_details(self, job_details):
        """Validate and clean the generated job details"""
        if not job_details:
            return None
            
        # Ensure all sections exist
        sections = ['description', 'responsibilities', 'required_skills', 'qualifications']
        for section in sections:
            if section not in job_details:
                job_details[section] = [] if section != 'description' else ''
        
        # Clean lists (remove duplicates and empty items)
        for section in ['responsibilities', 'required_skills', 'qualifications']:
            if isinstance(job_details[section], list):
                job_details[section] = list(filter(None, set(job_details[section])))
            else:
                job_details[section] = []
        
        return job_details