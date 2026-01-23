from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, SecurityScopes
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel

app = FastAPI(title="FastAPI OAuth2 + JWT demo")

# --- Security configuration ---
SECRET_KEY = "change-me"  # put in env var in real apps
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# tokenUrl must match your login endpoint path
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={"admin": "Admin access", "read": "Read access"},
)

# --- DTOs ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class User(BaseModel):
    username: str
    scopes: list[str] = []

# --- Fake user store (replace with DB) ---
fake_users = {
    "alice": {"username": "alice", "password_hash": pwd_context.hash("alicepw"), "scopes": ["read"]},
    "bob":   {"username": "bob",   "password_hash": pwd_context.hash("bobpw"),   "scopes": ["read", "admin"]},
}

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def authenticate_user(username: str, password: str) -> User | None:
    u = fake_users.get(username)
    if not u:
        return None
    if not verify_password(password, u["password_hash"]):
        return None
    return User(username=u["username"], scopes=u["scopes"])

def create_access_token(*, subject: str, scopes: list[str], expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "scopes": scopes,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# --- AuthZ dependency (JWT validation + scopes check) ---
def get_current_user(
    security_scopes: SecurityScopes,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    auth_header = 'Bearer scope="' + " ".join(security_scopes.scopes) + '"'
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": auth_header},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        token_scopes: list[str] = payload.get("scopes", [])
        if not username:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user_record = fake_users.get(username)
    if not user_record:
        raise credentials_exc

    user = User(username=username, scopes=user_record["scopes"])

    # enforce required scopes
    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
    return user

# --- Endpoints ---
@app.post("/token", response_model=Token)
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token = create_access_token(
        subject=user.username,
        scopes=user.scopes,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token)

@app.get("/me")
def me(current_user: Annotated[User, Security(get_current_user, scopes=["read"])]):
    return {"username": current_user.username, "scopes": current_user.scopes}

@app.get("/admin")
def admin(current_user: Annotated[User, Security(get_current_user, scopes=["admin"])]):
    return {"message": f"Welcome admin {current_user.username}"}
