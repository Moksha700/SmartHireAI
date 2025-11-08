import os
from werkzeug.utils import secure_filename
from config import ALLOWED_RESUME_EXTENSIONS, MAX_UPLOAD_SIZE
import pypdf
import docx

class FileHandler:
    def __init__(self, upload_folder='uploads'):
        self.upload_folder = upload_folder
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
    
    def allowed_file(self, filename):
        return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_RESUME_EXTENSIONS
    
    def save_resume(self, uploaded_file):
        """Save a resume file uploaded through Streamlit
        
        Args:
            uploaded_file: A Streamlit UploadedFile object
            
        Returns:
            str: Path to the saved file
            
        Raises:
            ValueError: If file is invalid or upload fails
            IOError: If there are file system issues
        """
        if uploaded_file is None:
            raise ValueError("No file was uploaded")
            
        try:
            # Get the file name and validate attributes
            if not hasattr(uploaded_file, 'name'):
                raise ValueError("Invalid file object - missing name attribute")
            if not hasattr(uploaded_file, 'size'):
                raise ValueError("Invalid file object - missing size attribute")
            if not hasattr(uploaded_file, 'getbuffer'):
                raise ValueError("Invalid file object - missing getbuffer method")
                
            filename = uploaded_file.name
            
            # Validate file type
            if not self.allowed_file(filename):
                raise ValueError(f"File type not allowed. Allowed types: {', '.join(ALLOWED_RESUME_EXTENSIONS)}")
            
            # Validate file size
            if uploaded_file.size > MAX_UPLOAD_SIZE:
                raise ValueError(f"File size exceeds maximum limit of {MAX_UPLOAD_SIZE/1024/1024:.1f}MB")
            
            # Create safe filename
            safe_filename = secure_filename(filename)
            if not safe_filename:
                raise ValueError("Invalid filename after sanitization")
                
            filepath = os.path.join(self.upload_folder, safe_filename)
            
            # Ensure unique filename
            base, extension = os.path.splitext(filepath)
            counter = 1
            while os.path.exists(filepath):
                filepath = f"{base}_{counter}{extension}"
                counter += 1
            
            # Ensure upload directory exists
            os.makedirs(self.upload_folder, exist_ok=True)
            
            # Save the file using Streamlit's UploadedFile
            try:
                with open(filepath, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                    
                # Verify file was saved successfully
                if not os.path.exists(filepath):
                    raise IOError("File failed to save")
                    
                return filepath
                
            except Exception as e:
                # Clean up partial file if save failed
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except:
                        pass
                raise IOError(f"Failed to save file: {str(e)}")
                
        except (AttributeError, ValueError, IOError) as e:
            raise ValueError(str(e))
        except Exception as e:
            raise ValueError(f"Unexpected error saving file: {str(e)}")
    
    def extract_text_from_pdf(self, filepath):
        """Extract text content from PDF file"""
        text = ""
        try:
            pdf_reader = pypdf.PdfReader(filepath)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return None
        return text
    
    def extract_text_from_docx(self, filepath):
        """Extract text content from DOCX file"""
        text = ""
        try:
            doc = docx.Document(filepath)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        except Exception as e:
            print(f"Error extracting text from DOCX: {e}")
            return None
        return text
    
    def extract_resume_text(self, filepath):
        """Extract text from resume file regardless of format"""
        if filepath.lower().endswith('.pdf'):
            return self.extract_text_from_pdf(filepath)
        elif filepath.lower().endswith('.docx'):
            return self.extract_text_from_docx(filepath)
        return None
    
    def delete_file(self, filepath):
        """Delete a file from the upload folder"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
        except Exception as e:
            print(f"Error deleting file: {e}")
        return False