from typing import Union
from fastapi import FastAPI, Query

app = FastAPI()

# 1. Basic Query Parameters
# When you visit: /items/?skip=0&limit=10
# 'skip' and 'limit' are inferred as query params because they aren't in the path
@app.get("/items/")
async def read_items(skip: int = 0, limit: int = 10):
    return {"skip": skip, "limit": limit}

# 2. Optional Parameters
# Using 'Union' or 'None' makes the parameter optional.
# URL: /users/5 or /users/5?name=gemini
@app.get("/users/{user_id}")
async def read_user(user_id: int, name: Union[str, None] = None):
    return {"user_id": user_id, "name": name}

# 3. Validation and Metadata with Query()
# Use Query() to add constraints like min_length, regex, or aliases
@app.get("/search/")
async def search_items(
    q: Union[str, None] = Query(
        default=None, 
        min_length=3, 
        max_length=50, 
        pattern="^fixedquery$",
        title="Search Query",
        description="Search for items by a specific keyword"
    )
):
    results = {"items": [{"item_id": "Foo"}, {"item_id": "Bar"}]}
    if q:
        results.update({"q": q})
    return results

# 4. Required Query Parameters
# Simply omit the default value to make it mandatory
# URL: /required/?token=123 (Fails if token is missing)
@app.get("/required/")
async def required_param(token: str):
    return {"token": token}

# 5. List/Multiple Values
# URL: /tags/?t=red&t=blue
@app.get("/tags/")
async def read_tags(t: list[str] = Query(default=[])):
    return {"tags": t}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)