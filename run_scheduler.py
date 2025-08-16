# Automations/run_scheduler.py
from database import SessionLocal, Post
from content_generator import ContentGenerator
import os
from dotenv import load_dotenv

# Load environment variables for local testing
load_dotenv()

def scheduled_generate():
    db = SessionLocal()
    # Ensure the API key is loaded
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("Error: PERPLEXITY_API_KEY not found.")
        return

    content_generator = ContentGenerator(api_key)

    print("Generating posts...")
    try:
        posts = content_generator.generate_posts()
        if not posts:
            print("No posts were generated.")
            return

        for post_data in posts:
            db_post = Post(**post_data)
            db.add(db_post)
        db.commit()
        print(f"Successfully generated and saved {len(posts)} posts.")
    except Exception as e:
        print(f"An error occurred during post generation: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    scheduled_generate()