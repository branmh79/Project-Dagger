import firebase_admin
from firebase_admin import credentials, db
import os

def initialize_firebase():
    """Initialize Firebase with credentials from environment variables or service account file."""
    try:
        # Check if Firebase app is already initialized
        firebase_admin.get_app()
        return
    except ValueError:
        pass  # App not initialized, continue with initialization
    
    # Try to get credentials from environment variable (for Render)
    service_account_info = os.getenv('FIREBASE_SERVICE_ACCOUNT')
    
    if service_account_info:
        # Parse JSON from environment variable
        import json
        cred_dict = json.loads(service_account_info)
        cred = credentials.Certificate(cred_dict)
    else:
        # Fallback to service account file (for local development)
        try:
            cred = credentials.Certificate('firebase_config.json')
        except FileNotFoundError:
            print("Warning: No Firebase credentials found. Please set FIREBASE_SERVICE_ACCOUNT environment variable or provide firebase_config.json")
            return
    
    # Initialize the app
    firebase_admin.initialize_app(cred, {
        'databaseURL': os.getenv('FIREBASE_DATABASE_URL', 'https://your-project-id.firebaseio.com')
    })

# Initialize Firebase when module is imported
initialize_firebase() 