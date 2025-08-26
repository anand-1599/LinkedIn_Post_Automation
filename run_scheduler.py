# Automations/run_scheduler.py
import asyncio
from database import create_posts, get_recent_posts
from content_generator import ContentGenerator
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load .env file for local testing; GitHub Actions will use secrets
load_dotenv()

async def scheduled_generate():
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("Error: PERPLEXITY_API_KEY not found.")
        return

    content_generator = ContentGenerator(api_key)
    print("Generating posts with deduplication...")
    try:
        recent_posts_data = await get_recent_posts(30)
        posts_data = content_generator.generate_posts(existing_posts=recent_posts_data)
        if not posts_data:
            print("No posts were generated.")
            return
        await create_posts(posts_data)
        print(f"Successfully saved {len(posts_data)} posts.")
        print("Sending email digest...")
        email_sent = content_generator.send_email_digest(posts_data)
        if not email_sent:
            print("Email digest failed to send. Check environment variables.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(scheduled_generate())