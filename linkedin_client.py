from linkedin_api import Linkedin
from datetime import datetime

class LinkedInClient:
    def __init__(self, email, password):
        self.api = Linkedin(email, password)
    
    def post_content(self, content):
        try:
            self.api.post(text=content)
            return {
                "success": True,
                "posted_at": datetime.utcnow()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }