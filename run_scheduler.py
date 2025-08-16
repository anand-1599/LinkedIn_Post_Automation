# Automations/run_scheduler.py
from database import SessionLocal, Post
from content_generator import ContentGenerator
import os
from dotenv import load_dotenv

# Load .env file for local testing; GitHub Actions will use secrets
load_dotenv()

def scheduled_generate():
    db = SessionLocal()
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("Error: PERPLEXITY_API_KEY not found.")
        return

    content_generator = ContentGenerator(api_key)
    
    print("Generating posts...")
    try:
        posts_data = content_generator.generate_posts()
        
        if not posts_data:
            print("No posts were generated.")
            return

        for post in posts_data:
            db.add(Post(**post))
        db.commit()
        print(f"Successfully saved {len(posts_data)} posts.")

        print("Sending email digest...")
        content_generator.send_email_digest(posts_data)
        
    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    scheduled_generate()