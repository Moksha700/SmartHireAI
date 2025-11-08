import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys
import os

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    GMAIL_USER,
    GMAIL_APP_PASSWORD,
    SMTP_SERVER,
    SMTP_PORT,
    EMAIL_TEMPLATES
)

class EmailAgent:
    def __init__(self):
        self.sender_email = GMAIL_USER
        self.app_password = GMAIL_APP_PASSWORD
        
    def send_email(self, recipient_email, template_name, **kwargs):
        """Send email using specified template and parameters"""
        try:
            # Validate email configuration
            if not self.sender_email or not self.app_password:
                print("Error: Email configuration missing. Check GMAIL_USER and GMAIL_APP_PASSWORD in .env")
                return False

            # Get email template
            template = EMAIL_TEMPLATES.get(template_name)
            if not template:
                print(f"Error: Email template '{template_name}' not found")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg['Subject'] = template['subject'].format(**kwargs)
            
            # Add body
            body = template['body'].format(**kwargs)
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to SMTP server and send
            try:
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    try:
                        server.login(self.sender_email, self.app_password)
                    except smtplib.SMTPAuthenticationError as auth_error:
                        print("Error: Gmail authentication failed. Please check your APP PASSWORD")
                        print("Make sure you've generated an App Password from Google Account settings")
                        print(f"Auth error: {str(auth_error)}")
                        return False
                    server.send_message(msg)
                
                print(f"Email sent successfully to {recipient_email}")
                return True
                
            except Exception as e:
                print(f"Error sending email: {str(e)}")
                print("Check your internet connection and Gmail settings")
                return False
                
        except Exception as e:
            print(f"Error preparing email: {str(e)}")
            return False
    
    def send_selection_email(self, candidate_name, email, job_title):
        """Send selection notification email"""
        return self.send_email(
            recipient_email=email,
            template_name='selected',
            candidate_name=candidate_name,
            job_title=job_title
        )
    
    def send_rejection_email(self, candidate_name, email, job_title):
        """Send rejection notification email"""
        return self.send_email(
            recipient_email=email,
            template_name='rejected',
            candidate_name=candidate_name,
            job_title=job_title
        )