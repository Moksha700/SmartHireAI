from langchain.text_splitter import RecursiveCharacterTextSplitter
import google.generativeai as genai
import json
import sys
import os
import re
import time
from difflib import SequenceMatcher
from datetime import datetime, timedelta
import random

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

from config import GEMINI_API_KEY

class ResumeParserAgent:
    def __init__(self):
        # Initialize Gemini AI
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Initialize rate limiter for free tier (2 requests per minute)
        self.rate_limiter = RateLimiter(max_requests=2, time_window=60)
        
        # Try to get available models
        self.rate_limiter.wait_if_needed()
        models = genai.list_models()
        available_models = [m.name for m in models]
        print(f"Available models: {available_models}")
        
        # Check for available models
        model_options = [
            'models/gemini-pro-latest',
            'models/gemini-2.5-pro',
            'models/gemini-2.0-pro-exp',
            'gemini-pro'
        ]
        
        model_found = False
        for model_name in model_options:
            try:
                self.model = genai.GenerativeModel(model_name)
                print(f"Using model: {model_name}")
                model_found = True
                break
            except Exception as e:
                print(f"Failed to initialize model {model_name}: {e}")
                continue
                
        if not model_found:
            raise ValueError(f"No suitable Gemini model found. Available models: {available_models}")
            
        # Initialize text splitter for long documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )
        
    def _preprocess_resume_text(self, text):
        """Clean and normalize resume text for better parsing
        
        Args:
            text (str): Raw resume text
            
        Returns:
            str: Cleaned and normalized text
        """
        if not text:
            return ""
            
        # Replace multiple newlines with single newline
        text = re.sub(r'\n\s*\n', '\n', text)
        
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common OCR and formatting issues
        text = text.replace('•', '-')  # Replace bullets with dashes
        text = re.sub(r'[\u2022\u2023\u2043\u204C\u204D\u2219\u25D8\u25E6\u2619]', '-', text)  # More bullet chars
        text = text.replace('"', '"').replace('"', '"')  # Normalize quotes
        text = text.replace(''', "'").replace(''', "'")  # Normalize apostrophes
        
        # Add newlines before common section headers
        section_headers = [
            'education',
            'experience',
            'employment',
            'work history',
            'skills',
            'technical skills',
            'projects',
            'achievements',
            'certifications',
            'professional summary',
            'objective'
        ]
        for header in section_headers:
            pattern = re.compile(r'(?i)(?<!\n)' + re.escape(header))
            text = pattern.sub(r'\n' + header, text)
        
        # Clean up any resulting multiple newlines again
        text = re.sub(r'\n\s*\n', '\n', text)
        text = text.strip()
        
        return text
    
    def _create_chunk_prompt(self, chunk, chunk_index, total_chunks):
        """Create an optimized prompt for chunk processing
        
        Args:
            chunk (str): Text chunk to process
            chunk_index (int): Index of current chunk
            total_chunks (int): Total number of chunks
            
        Returns:
            str: Formatted prompt
        """
        return f"""Analyze the following section (part {chunk_index + 1} of {total_chunks}) of a resume and extract key information in JSON format:

Resume Section:
{chunk}

Return a JSON object with EXACTLY this structure. Include ONLY information that is explicitly present in the text:
{{
    "education": [
        {{
            "degree": "Full degree name",
            "institution": "Full institution name",
            "year": "Completion year or expected"
        }}
    ],
    "skills": [
        "Individual technical or soft skills"
    ],
    "experience": [
        {{
            "title": "Exact job title",
            "company": "Company name",
            "duration": "Employment period",
            "responsibilities": [
                "Key responsibilities or achievements"
            ]
        }}
    ],
    "projects": [
        {{
            "name": "Project name",
            "description": "Brief project description",
            "technologies": [
                "Technologies used"
            ]
        }}
    ]
}}

Important:
1. Only include information that appears in the text
2. Keep all text exactly as it appears (preserve case, spelling, etc.)
3. For missing sections, use empty arrays
4. Do not fabricate or infer missing details
"""
        
    def parse_resume(self, resume_text):
        """Parse resume text and extract structured information
        
        Args:
            resume_text (str): The text content of the resume to parse
            
        Returns:
            dict: Parsed resume information or None if parsing fails
            
        Raises:
            ValueError: If the resume text is invalid or parsing fails
        """
        if not resume_text or not resume_text.strip():
            raise ValueError("Resume text is empty or invalid")
            
        print(f"Starting resume parsing. Text length: {len(resume_text)}")
        print("First 100 characters of resume:", resume_text[:100].replace('\n', ' '))
            
        try:
            # Clean and normalize text
            resume_text = self._preprocess_resume_text(resume_text)
            print(f"Preprocessed text length: {len(resume_text)}")
            
            # Split long resume text into manageable chunks
            chunks = self.text_splitter.split_text(resume_text)
            print(f"Split into {len(chunks)} chunks")
            
            # Process each chunk and combine results
            combined_info = {
                "education": [],
                "skills": [],
                "experience": [],
                "projects": []
            }
            
            for i, chunk in enumerate(chunks):
                # Create optimized prompt for this chunk
                prompt = self._create_chunk_prompt(chunk, i, len(chunks))
                
                # Try parsing with multiple temperature settings if needed
                temperatures = [0.3, 0.5, 0.7]  # Start conservative, get more creative if needed
                
                chunk_info = None
                last_error = None
                
                for temp in temperatures:
                    generation_config = {
                        "temperature": temp,
                        "top_p": 0.9,
                        "top_k": 40,
                        "max_output_tokens": 2048,
                    }
                
                    try:
                        print(f"\nProcessing chunk {i+1}/{len(chunks)} with temperature {temp}")
                        
                        # Handle rate limiting
                        self.rate_limiter.wait_if_needed()
                        try:
                            response = self.model.generate_content(
                                prompt,
                                generation_config=generation_config
                            )
                            
                            if not response.text:
                                print(f"Warning: Empty response from Gemini AI for chunk {i+1}")
                                continue
                        except Exception as api_error:
                            if "429" in str(api_error):  # Rate limit error
                                print("Rate limit exceeded, retrying with backoff...")
                                time.sleep(35)  # Wait for the rate limit window
                                continue
                            raise  # Re-raise other errors
                            
                        try:
                            # Clean the response text to help with JSON parsing
                            response_text = response.text.strip()
                            print(f"Raw response from Gemini AI (first 100 chars): {response_text[:100]}")
                            
                            # Try to extract JSON from markdown code blocks if present
                            if '```json' in response_text or '```' in response_text:
                                pattern = r'```(?:json)?\s*([\s\S]*?)```'
                                matches = re.findall(pattern, response_text)
                                if matches:
                                    response_text = matches[0].strip()
                                else:
                                    response_text = re.sub(r'^```json\s*|\s*```$', '', response_text)
                            
                            # Attempt to fix common JSON issues
                            response_text = response_text.replace('None', 'null')
                            response_text = re.sub(r',(\s*[}\]])', r'\1', response_text)  # Remove trailing commas
                            
                            try:
                                chunk_info = json.loads(response_text)
                            except json.JSONDecodeError as je:
                                print(f"Initial JSON parsing failed: {je}")
                                # Try to extract just the JSON object if there's extra text
                                json_match = re.search(r'({[\s\S]*})', response_text)
                                if json_match:
                                    try:
                                        chunk_info = json.loads(json_match.group(1))
                                    except json.JSONDecodeError:
                                        raise
                                else:
                                    raise
                            
                            # Validate chunk information structure
                            if self._validate_chunk_info(chunk_info):
                                print(f"Successfully parsed chunk {i+1}")
                                print(f"Found: {sum(len(chunk_info[k]) for k in chunk_info)} items")
                                break  # Use this successful result
                            else:
                                print(f"Invalid structure in chunk {i+1} response")
                                print("Missing or invalid sections in response")
                                last_error = "Invalid response structure"
                                
                        except json.JSONDecodeError as je:
                            print(f"JSON parse error in chunk {i+1}: {je}")
                            last_error = f"JSON parse error: {str(je)}"
                            continue
                            
                    except Exception as e:
                        print(f"Error processing chunk {i+1}: {e}")
                        last_error = str(e)
                        continue
                
                if chunk_info:
                    # Merge validated chunk information
                    for key in combined_info:
                        if key in chunk_info and isinstance(chunk_info[key], list):
                            # Enhanced deduplication with fuzzy matching
                            self._merge_chunk_data(combined_info[key], chunk_info[key])
                else:
                    print(f"Failed to parse chunk {i+1}: {last_error}")
                    continue  # Try next chunk
            
            # Clean and validate the information
            cleaned_info = self._clean_combined_info(combined_info)
            
            # Ensure we have some structure to work with
            self._is_valid_result(cleaned_info)
            
            # Extract any text-based skills if we don't have many
            if len(cleaned_info['skills']) < 3:
                # Try to extract skills from the raw text
                words = set(resume_text.lower().split())
                common_skills = {
                    'python', 'java', 'javascript', 'c++', 'sql', 'management',
                    'leadership', 'communication', 'analysis', 'research',
                    'development', 'programming', 'design', 'testing',
                    'project', 'team', 'agile', 'database', 'web'
                }
                found_skills = words.intersection(common_skills)
                if found_skills:
                    cleaned_info['skills'].extend(list(found_skills))
            
            return cleaned_info
            
        except Exception as e:
            print(f"Warning: Error during resume parsing: {str(e)}")
            print("Returning minimal valid structure for scoring")
            
            # Return an empty structure indicating parsing failure
            return {
                "education": [],  # Empty education indicates parsing failure
                "skills": [],    # Empty skills indicates parsing failure
                "experience": [], # Empty experience indicates parsing failure
                "projects": [],   # Empty projects indicates parsing failure
                "parsing_error": str(e)  # Include the error for debugging
            }
    
    def _validate_chunk_info(self, chunk_info):
        """Validate the structure of parsed chunk information"""
        if not isinstance(chunk_info, dict):
            print("Validation failed: Response is not a dictionary")
            return False
            
        # Initialize an empty structure if missing
        for key in ['education', 'skills', 'experience', 'projects']:
            if key not in chunk_info:
                chunk_info[key] = []
            elif not isinstance(chunk_info[key], list):
                chunk_info[key] = []
        
        valid_items_found = False
        
        # Validate and clean education entries
        cleaned_education = []
        for edu in chunk_info['education']:
            if isinstance(edu, dict):
                cleaned_edu = {
                    'degree': str(edu.get('degree', '')).strip(),
                    'institution': str(edu.get('institution', '')).strip(),
                    'year': str(edu.get('year', '')).strip()
                }
                if cleaned_edu['degree'] or cleaned_edu['institution']:
                    cleaned_education.append(cleaned_edu)
                    valid_items_found = True
        chunk_info['education'] = cleaned_education
        
        # Clean skills (any non-empty strings)
        cleaned_skills = []
        for skill in chunk_info['skills']:
            if skill and isinstance(skill, (str, int, float)):
                cleaned_skill = str(skill).strip()
                if cleaned_skill:
                    cleaned_skills.append(cleaned_skill)
                    valid_items_found = True
        chunk_info['skills'] = cleaned_skills
        
        # Validate and clean experience entries
        cleaned_experience = []
        for exp in chunk_info['experience']:
            if isinstance(exp, dict):
                cleaned_exp = {
                    'title': str(exp.get('title', '')).strip(),
                    'company': str(exp.get('company', '')).strip(),
                    'duration': str(exp.get('duration', '')).strip(),
                    'responsibilities': []
                }
                
                # Clean responsibilities
                if 'responsibilities' in exp and isinstance(exp['responsibilities'], list):
                    cleaned_exp['responsibilities'] = [
                        str(r).strip() for r in exp['responsibilities']
                        if r and str(r).strip()
                    ]
                
                if cleaned_exp['title'] or cleaned_exp['company']:
                    cleaned_experience.append(cleaned_exp)
                    valid_items_found = True
        chunk_info['experience'] = cleaned_experience
        
        # Validate and clean projects
        cleaned_projects = []
        for proj in chunk_info['projects']:
            if isinstance(proj, dict):
                cleaned_proj = {
                    'name': str(proj.get('name', '')).strip(),
                    'description': str(proj.get('description', '')).strip(),
                    'technologies': []
                }
                
                # Clean technologies
                if 'technologies' in proj and isinstance(proj['technologies'], list):
                    cleaned_proj['technologies'] = [
                        str(t).strip() for t in proj['technologies']
                        if t and str(t).strip()
                    ]
                
                if cleaned_proj['name'] or cleaned_proj['description']:
                    cleaned_projects.append(cleaned_proj)
                    valid_items_found = True
        chunk_info['projects'] = cleaned_projects
        
        if not valid_items_found:
            print("Validation failed: No valid items found in any section")
            return False
            
        return True
    
    def _merge_chunk_data(self, existing_items, new_items):
        """Merge new items into existing items with fuzzy matching to avoid duplicates"""
        for new_item in new_items:
            should_add = True
            
            # Convert items to comparable strings
            new_str = json.dumps(new_item) if isinstance(new_item, dict) else new_item
            
            for existing_item in existing_items:
                existing_str = json.dumps(existing_item) if isinstance(existing_item, dict) else existing_item
                
                # Use fuzzy matching to detect similar items
                similarity = SequenceMatcher(None, new_str.lower(), existing_str.lower()).ratio()
                if similarity > 0.8:  # Items are very similar
                    should_add = False
                    break
                    
            if should_add:
                existing_items.append(new_item)
    
    def _clean_combined_info(self, combined_info):
        """Clean and validate the combined information"""
        cleaned = {
            "education": [],
            "skills": [],
            "experience": [],
            "projects": []
        }
        
        # Clean education entries
        for edu in combined_info.get('education', []):
            if isinstance(edu, dict) and all(k in edu for k in ['degree', 'institution', 'year']):
                cleaned['education'].append({
                    'degree': str(edu['degree']).strip(),
                    'institution': str(edu['institution']).strip(),
                    'year': str(edu['year']).strip()
                })
                
        # Clean skills (remove duplicates and empty strings)
        skills_set = set()
        for skill in combined_info.get('skills', []):
            if skill and isinstance(skill, str):
                skills_set.add(skill.strip())
        cleaned['skills'] = sorted(list(skills_set))
        
        # Clean experience entries
        for exp in combined_info.get('experience', []):
            if isinstance(exp, dict) and all(k in exp for k in ['title', 'company', 'duration', 'responsibilities']):
                cleaned_exp = {
                    'title': str(exp['title']).strip(),
                    'company': str(exp['company']).strip(),
                    'duration': str(exp['duration']).strip(),
                    'responsibilities': [
                        str(r).strip() for r in exp['responsibilities']
                        if r and isinstance(r, str)
                    ]
                }
                if cleaned_exp['responsibilities']:  # Only include if it has responsibilities
                    cleaned['experience'].append(cleaned_exp)
                    
        # Clean projects
        for proj in combined_info.get('projects', []):
            if isinstance(proj, dict) and all(k in proj for k in ['name', 'description', 'technologies']):
                cleaned_proj = {
                    'name': str(proj['name']).strip(),
                    'description': str(proj['description']).strip(),
                    'technologies': [
                        str(t).strip() for t in proj['technologies']
                        if t and isinstance(t, str)
                    ]
                }
                if cleaned_proj['technologies']:  # Only include if it has technologies
                    cleaned['projects'].append(cleaned_proj)
                    
        return cleaned
    
    def _is_valid_result(self, cleaned_info):
        """Ensure we have at least some structure to work with"""
        print("Processing resume information...")
        
        # Ensure we have the basic structure
        if not cleaned_info:
            cleaned_info = {}
            
        # Ensure all sections exist with at least minimal content
        if 'education' not in cleaned_info or not cleaned_info['education']:
            cleaned_info['education'] = [{
                'degree': 'Not Specified',
                'institution': 'Not Specified',
                'year': 'Not Specified'
            }]
            
        if 'skills' not in cleaned_info or not cleaned_info['skills']:
            cleaned_info['skills'] = ['General Skills']
            
        if 'experience' not in cleaned_info or not cleaned_info['experience']:
            cleaned_info['experience'] = [{
                'title': 'Not Specified',
                'company': 'Not Specified',
                'duration': 'Not Specified',
                'responsibilities': ['Not Specified']
            }]
            
        if 'projects' not in cleaned_info or not cleaned_info['projects']:
            cleaned_info['projects'] = [{
                'name': 'Not Specified',
                'description': 'Not Specified',
                'technologies': ['Not Specified']
            }]
            
        print("Resume sections processed:")
        print(f"Education entries: {len(cleaned_info['education'])}")
        print(f"Skills found: {len(cleaned_info['skills'])}")
        print(f"Experience entries: {len(cleaned_info['experience'])}")
        print(f"Projects: {len(cleaned_info['projects'])}")
        
        return True  # Always return True as we ensure minimal valid structure
    
    def calculate_fit_score(self, parsed_resume, job_details):
        """Calculate a weighted fit score by comparing resume with job requirements"""
        try:
            # Skip scoring if resume parsing failed (empty fields)
            if not parsed_resume.get("skills") and not parsed_resume.get("experience"):
                print("Resume parsing failed - using minimal score")
                return {
                    "skill_match_score": 5.0,
                    "experience_relevance_score": 5.0,
                    "education_alignment_score": 5.0,
                    "overall_fit_score": 5.0,
                    "reasoning": "Resume parsing failed or insufficient information provided"
                }
            
            # Prepare comparison prompt with focus on weighted component scoring
            prompt = f"""Analyze this candidate's profile against the job requirements and provide a precise scoring breakdown.

Job Requirements:
{json.dumps(job_details, indent=2)}

Candidate Profile:
{json.dumps(parsed_resume, indent=2)}

Scoring Guidelines:

1. Skills Assessment (40% of total):
   - Exact skills matches: Award 3 points each
   - Related/transferable skills: Award 1-2 points based on relevance
   - Domain-specific skills alignment: 0-20 bonus points
   - Normalize to 100 point scale

2. Experience Evaluation (40% of total):
   - Years in similar roles: 0-40 points
   - Industry relevance: 0-30 points
   - Role responsibility matches: 0-30 points
   
3. Education Score (20% of total):
   - Degree level match: 0-40 points
   - Field relevance: 0-40 points
   - Institution ranking/reputation: 0-20 points

Calculate each component score (0-100) and return:
{{
    "skill_match_score": float,
    "experience_relevance_score": float, 
    "education_alignment_score": float,
    "overall_fit_score": float,  // Weighted average of above scores
    "reasoning": "Detailed scoring breakdown and justification"
}}

Important Rules:
- Score conservatively - require clear evidence
- Use exact 0-100 scale for each component
- Show detailed math in reasoning
- Lower scores for missing/unclear info
- Consider quality and depth, not just presence
"""
            
            try:
                # Get model response and parse scores with rate limiting
                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        self.rate_limiter.wait_if_needed()
                        response = self.model.generate_content(prompt)
                        scores = json.loads(response.text)
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
                
                # Validate and normalize scores
                required_fields = [
                    'skill_match_score', 
                    'experience_relevance_score',
                    'education_alignment_score', 
                    'overall_fit_score',
                    'reasoning'
                ]
                
                # Use conservative scores for any missing fields
                for field in required_fields:
                    if field not in scores:
                        scores[field] = 15.0 if field != 'reasoning' else "Score calculation incomplete"
                    elif field != 'reasoning':
                        # Ensure scores are floats between 0-100
                        try:
                            scores[field] = float(scores[field])
                            scores[field] = max(0.0, min(100.0, scores[field]))
                        except (ValueError, TypeError):
                            scores[field] = 15.0
                
                # Calculate weighted average if not provided
                if not scores['overall_fit_score'] or scores['overall_fit_score'] > 100:
                    scores['overall_fit_score'] = (
                        0.4 * scores['skill_match_score'] +
                        0.4 * scores['experience_relevance_score'] +
                        0.2 * scores['education_alignment_score']
                    )
                
                return scores
                
            except json.JSONDecodeError as je:
                print(f"JSON parsing error in score calculation: {je}")
                return {
                    "skill_match_score": 15.0,
                    "experience_relevance_score": 15.0,
                    "education_alignment_score": 15.0,
                    "overall_fit_score": 15.0,
                    "reasoning": f"Score parsing failed: {str(je)}"
                }
                
            except Exception as e:
                print(f"Error in detailed score calculation: {e}")
                return {
                    "skill_match_score": 10.0,
                    "experience_relevance_score": 10.0,
                    "education_alignment_score": 10.0,
                    "overall_fit_score": 10.0,
                    "reasoning": f"Score calculation error: {str(e)}"
                }
            
        except Exception as e:
            print(f"Fatal error in score calculation: {e}")
            return {
                "skill_match_score": 5.0,
                "experience_relevance_score": 5.0,
                "education_alignment_score": 5.0,
                "overall_fit_score": 5.0,
                "reasoning": f"Fatal scoring error: {str(e)}"
            }
    
    def enhance_score_with_embeddings(self, resume_text, job_description):
        """Use text comparison to calculate similarity"""
        try:
            # For now, return a basic similarity score based on common words
            resume_words = set(resume_text.lower().split())
            job_words = set(job_description.lower().split())
            
            common_words = resume_words.intersection(job_words)
            similarity = len(common_words) / max(len(resume_words), len(job_words))
            
            return similarity * 100
            
        except Exception as e:
            print(f"Error calculating similarity: {e}")
            return 0
    
    def _calculate_cosine_similarity(self, vec1, vec2):
        """Calculate cosine similarity between two vectors"""
        import numpy as np
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        return dot_product / (norm1 * norm2)
    
    def generate_detailed_feedback(self, scores, parsed_resume, job_details):
        """Generate detailed feedback about the candidate's fit"""
        try:
            prompt = f"""Based on the following comparison, generate detailed feedback:
            
            Scores:
            {json.dumps(scores, indent=2)}
            
            Candidate Profile:
            {json.dumps(parsed_resume, indent=2)}
            
            Job Requirements:
            {json.dumps(job_details, indent=2)}
            
            Provide specific feedback on:
1. Strong matches
2. Areas for improvement
3. Missing critical requirements
4. Recommendations for the candidate
            """
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            print(f"Error generating feedback: {e}")
            return None