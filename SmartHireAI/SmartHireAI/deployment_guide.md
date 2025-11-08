# Deployment Guide for SmartHire AI

## 1. Streamlit Cloud Deployment (Recommended Method)

### Prerequisites
1. Create a GitHub account
2. Create a Streamlit Cloud account (https://streamlit.io/cloud)

### Steps:

1. **Prepare Your Repository**
```bash
# Initialize git if not already done
git init
git add .
git commit -m "Initial commit"

# Create a new repository on GitHub and push your code
git remote add origin <your-github-repo-url>
git push -u origin main
```

2. **Create .streamlit/secrets.toml**
```toml
# Add your sensitive configuration
GEMINI_API_KEY = "your-api-key"
MONGODB_URI = "your-mongodb-uri"
ADMIN_USERNAME = "your-admin-username"
ADMIN_PASSWORD = "your-admin-password"
AWS_ACCESS_KEY_ID = "your-aws-access-key"
AWS_SECRET_ACCESS_KEY = "your-aws-secret-key"
AWS_BUCKET_NAME = "your-bucket-name"
```

3. **Deploy on Streamlit Cloud**
- Go to https://streamlit.io/cloud
- Click "New app"
- Select your repository and branch
- Select app.py as the main file
- Add your secrets in the Streamlit Cloud dashboard

## 2. Alternative: Deploy on AWS Elastic Beanstalk

### Prerequisites
1. Install AWS CLI
2. Install AWS EB CLI
3. Create AWS account

### Steps:

1. **Initialize EB Application**
```bash
eb init -p python-3.12 smarthire-ai
```

2. **Create EB Environment**
```bash
eb create smarthire-ai-env
```

3. **Configure Environment Variables**
- Go to AWS Console
- Navigate to Elastic Beanstalk
- Select your environment
- Add environment variables for all secrets

## 3. Alternative: Deploy on Heroku

### Prerequisites
1. Install Heroku CLI
2. Create Heroku account

### Steps:

1. **Create Procfile**
```
web: streamlit run app.py --server.port $PORT
```

2. **Deploy to Heroku**
```bash
heroku create smarthire-ai
heroku git:remote -a smarthire-ai
git push heroku main
```

3. **Set Environment Variables**
```bash
heroku config:set GEMINI_API_KEY=your-api-key
heroku config:set MONGODB_URI=your-mongodb-uri
# Add other environment variables
```

## Important Deployment Considerations

### 1. Database Setup
- Use MongoDB Atlas for global database access
- Set up proper database indexes
- Configure database backups

### 2. File Storage
- Use AWS S3 for file storage instead of local storage
- Configure CORS for S3 bucket
- Set up proper bucket policies

### 3. Email Configuration
- Use a production SMTP server
- Configure SPF and DKIM records
- Set up email monitoring

### 4. Security
- Enable HTTPS
- Set up proper CORS policies
- Implement rate limiting
- Set up monitoring and logging
- Configure proper backup strategies

### 5. Performance
- Configure caching
- Set up CDN for static files
- Optimize database queries
- Implement proper error handling

## Required Code Changes for Production

1. **Update config.py**
```python
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
MONGODB_URI = os.getenv('MONGODB_URI')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')
```

2. **Update file_handler.py to use S3**
```python
import boto3
from botocore.exceptions import ClientError

class FileHandler:
    def __init__(self):
        self.s3 = boto3.client('s3')
        self.bucket = os.getenv('AWS_BUCKET_NAME')

    def save_resume(self, file):
        try:
            file_name = f"resumes/{uuid.uuid4()}-{file.name}"
            self.s3.upload_fileobj(file, self.bucket, file_name)
            return f"s3://{self.bucket}/{file_name}"
        except ClientError as e:
            print(f"Error uploading file to S3: {e}")
            raise
```

3. **Update database configuration**
```python
from pymongo import MongoClient
from pymongo.server_api import ServerApi

client = MongoClient(os.getenv('MONGODB_URI'), server_api=ServerApi('1'))
db = client.get_database('smarthire')
```

## Monitoring and Maintenance

1. **Set up Monitoring**
- Use AWS CloudWatch or similar
- Monitor application metrics
- Set up alerts for errors
- Track API usage and costs

2. **Regular Maintenance**
- Update dependencies regularly
- Monitor security advisories
- Perform regular backups
- Test restore procedures

3. **Scaling Considerations**
- Configure auto-scaling if needed
- Monitor resource usage
- Optimize for cost
- Plan for increased traffic

## Cost Considerations

1. **Fixed Costs**
- Domain name registration
- SSL certificates
- Base hosting costs
- Database hosting

2. **Variable Costs**
- API usage (Gemini AI)
- Storage costs (S3)
- Database operations
- Email sending

3. **Optional Costs**
- CDN services
- Advanced monitoring
- Backup services
- Support services