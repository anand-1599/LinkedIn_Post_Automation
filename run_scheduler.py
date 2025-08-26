# Automations/run_scheduler.py
from database import SessionLocal, Post
from content_generator import ContentGenerator
import os
from datetime import datetime, timedelta
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
    
    print("Generating posts with deduplication...")
    try:
        # 1. Get recent posts (last 30 days) to check for duplicates
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        recent_posts = db.query(Post).filter(Post.created_at >= cutoff_date).all()
        recent_posts_data = [{"content": p.content} for p in recent_posts]
        
        # 2. Generate new posts with deduplication
        posts_data = content_generator.generate_posts(existing_posts=recent_posts_data)
        
        if not posts_data:
            print("No posts were generated.")
            return

        # 3. Save posts to database
        for post in posts_data:
            db.add(Post(**post))
        db.commit()
        print(f"Successfully saved {len(posts_data)} posts.")

        # 4. Send email digest
        print("Sending email digest...")
        email_sent = content_generator.send_email_digest(posts_data)
        if not email_sent:
            print("Email digest failed to send. Check environment variables.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    scheduled_generate()