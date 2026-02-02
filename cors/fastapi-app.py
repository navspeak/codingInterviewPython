from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Streamlit runs on http://localhost:8501 by default
ALLOWED_ORIGINS = [
    "http://localhost:8502", # change back to 8501 to get rids of CORS error
    "http://127.0.0.1:8502",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # 👈 allow Streamlit origin
    allow_credentials=True,
    allow_methods=["*"],             # GET, POST, OPTIONS, etc.
    allow_headers=["*"],             # Authorization, Content-Type, etc.
)

@app.get("/employees")
def employees():
    return [
        {"name": "Alice", "salary": 50000},
        {"name": "Bob", "salary": 60000},
        {"name": "Charlie", "salary": 70000},
    ]

@app.post("/echo")
def echo(payload: dict):
    return {"you_sent": payload}
