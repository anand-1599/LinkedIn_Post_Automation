# Automations/run_scheduler.py
from database import SessionLocal, Post
from content_generator import ContentGenerator
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def scheduled_generate():
    """
    This function is executed by the Render Cron Job.
    It generates new posts and sends an email digest.
    """
    db = SessionLocal()
    
    # Ensure the API key and email settings are loaded
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("Error: PERPLEXITY_API_KEY not found.")
        return

    # Initialize the content generator
    content_generator = ContentGenerator(api_key)
    
    print("Generating posts...")
    posts = []
    try:
        # 1. Generate new posts
        generated_posts_data = content_generator.generate_posts()
        
        if not generated_posts_data:
            print("No posts were generated.")
            return

        # 2. Save posts to the database
        for post_data in generated_posts_data:
            db_post = Post(**post_data)
            db.add(db_post)
            posts.append(post_data) # Keep the data for the email
        db.commit()
        print(f"Successfully generated and saved {len(posts)} posts.")

        # 3. Send the email digest with the newly created posts
        if posts:
            print("Sending email digest...")
            email_sent = content_generator.send_email_digest(posts)
            if not email_sent:
                print("Email digest failed to send. Check your environment variables.")
        
    except Exception as e:
        print(f"An error occurred during the scheduled job: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Running scheduled task manually...")
    scheduled_generate()
    print("Task finished.")