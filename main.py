# Automations/main.py
from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database import (
    list_posts,
    get_recent_posts,
    create_posts,
    approve_post as approve_post_db,
    update_post_content,
    delete_post as delete_post_db,
)
from content_generator import ContentGenerator

# Load environment variables
load_dotenv()
if not os.getenv("PERPLEXITY_API_KEY"):
    raise RuntimeError("Missing required environment variable: PERPLEXITY_API_KEY")

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize content generator
content_generator = ContentGenerator(os.getenv("PERPLEXITY_API_KEY"))

@app.get("/")
async def dashboard(
    request: Request,
    filter: str = Query("all"),
):
    posts = await list_posts(filter)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "posts": posts, "filter": filter}
    )

# Generate posts and send email with deduplication
@app.post("/generate-posts")
async def generate_posts():
    try:
        # 1. Get recent posts (last 30 days) to check for duplicates
        recent_posts_data = await get_recent_posts(30)

        # 2. Generate new posts with deduplication
        print("Generating posts with deduplication...")
        generated_posts_data = content_generator.generate_posts(existing_posts=recent_posts_data)

        if not generated_posts_data:
            print("No posts were generated.")
            return {"message": "No posts were generated."}

        # 3. Save posts to the database (bulk insert)
        ids = await create_posts(generated_posts_data)
        print(f"Successfully generated and saved {len(ids)} posts.")

        # 4. Send the email digest
        print("Sending email digest...")
        email_sent = content_generator.send_email_digest(generated_posts_data)
        if not email_sent:
            print("Email digest failed to send. Check environment variables.")

        return {"message": f"{len(generated_posts_data)} posts generated and email sent successfully"}

    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during post generation.")

# Approve post
@app.post("/approve/{post_id}")
async def approve_post(post_id: str):
    ok = await approve_post_db(post_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post approved and others deleted"}

# Edit post (manual or autosave)
@app.post("/edit/{post_id}")
async def edit_post(post_id: str, content: str = Form(...)):
    ok = await update_post_content(post_id, content)
    if not ok:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post updated"}

# Delete post
@app.post("/delete/{post_id}")
async def delete_post(post_id: str):
    ok = await delete_post_db(post_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)