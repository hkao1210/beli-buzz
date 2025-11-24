import praw
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

def get_reddit_posts(subreddit_name="FoodToronto", limit=20):
    """
    Fetches hot posts from a specified subreddit.
    """
    try:
        reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT")
        )
        
        subreddit = reddit.subreddit(subreddit_name)
        posts = []
        
        print(f"Fetching posts from r/{subreddit_name}...")
        for submission in subreddit.hot(limit=limit):
            # Simple time filter: check if created in last 24h
            created_utc = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
            if datetime.now(timezone.utc) - created_utc < timedelta(hours=24):
                posts.append({
                    "id": submission.id,
                    "title": submission.title,
                    "text": submission.selftext,
                    "url": submission.url,
                    "score": submission.score,
                    "comments": [comment.body for comment in submission.comments.list()[:5] if hasattr(comment, 'body')]
                })
        
        return posts
    except Exception as e:
        print(f"Error fetching Reddit posts: {e}")
        return []

if __name__ == "__main__":
    # Test the scraper
    data = get_reddit_posts()
    print(f"Found {len(data)} posts.")
