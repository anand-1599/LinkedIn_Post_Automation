from fastapi import FastAPI, Request, Depends, Form, Query, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import os
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from database import SessionLocal, Post
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

# DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dashboard route with filter param
@app.get("/")
async def dashboard(
    request: Request,
    filter: str = Query("all"),
    db: Session = Depends(get_db)
):
    query = db.query(Post)
    if filter == "approved":
        query = query.filter(Post.is_approved == True)
    elif filter == "pending":
        query = query.filter(Post.is_approved == False)

    posts = query.order_by(Post.created_at.desc()).all()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "posts": posts, "filter": filter}
    )

# Generate posts
@app.post("/generate-posts")
async def generate_posts(db: Session = Depends(get_db)):
    posts = content_generator.generate_posts()
    for post in posts:
        db_post = Post(**post)
        db.add(db_post)
    db.commit()
    return {"message": "Posts generated successfully"}

# Approve post
@app.post("/approve/{post_id}")
async def approve_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.is_approved = True
    db.commit()

    # Prune other unapproved posts from same batch
    db.query(Post).filter(
        Post.batch_timestamp == post.batch_timestamp,
        Post.id != post_id,
        Post.is_approved == False
    ).delete(synchronize_session=False)
    db.commit()
    return {"message": "Post approved and others deleted"}

# Edit post (manual or autosave)
@app.post("/edit/{post_id}")
async def edit_post(
    post_id: int,
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.content = content
    db.commit()
    return {"message": "Post updated"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
