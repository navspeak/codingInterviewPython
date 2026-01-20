from typing import Dict
from fastapi import FastAPI, Depends, APIRouter, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

app = FastAPI(title="DI + Router demo")

#DTOs
class CustomerCreate(BaseModel):
    name: str
    email: EmailStr

class CustomerOut(CustomerCreate):
    id: int = Field(gt=0)

# Repo
class Repo:
    def __init__(self) -> None:
        self._db: Dict[int, CustomerOut] = {}
        self._seq: int = 1

    def create(self, dto: CustomerCreate) -> CustomerOut:
        cid = self._seq
        self._seq += 1
        c = CustomerOut(id=cid, **dto.model_dump())
        self._db[cid] = c
        return c

    def get(self, cid: int) -> CustomerOut | None:
        return self._db.get(cid)

    def list_all(self) -> list[CustomerOut]:
        return [self._db[k] for k in sorted(self._db.keys())]

repo = Repo()

#Dependencies
def get_repo()-> Repo:
    return repo

def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    # Very simple auth dependency (like a filter)
    if x_api_key != "secret":
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

# ----------------------------
# Routers
# ----------------------------
customers_router = APIRouter(
    prefix="/customers",
    tags=["customers"],
    dependencies=[Depends(require_api_key)],  # applies to all endpoints in this router
)

@customers_router.post("", response_model=CustomerOut)
def create_customer(dto: CustomerCreate, r: Repo = Depends(get_repo)):
    return r.create(dto)

@customers_router.get("", response_model=list[CustomerOut])
def list_customers(r: Repo = Depends(get_repo)):
    return r.list_all()

@customers_router.get("/{cid}", response_model=CustomerOut)
def get_customer(cid: int, r: Repo = Depends(get_repo)):
    c = r.get(cid)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c

# Include router in app
app.include_router(customers_router)

# A non-protected endpoint (no API key needed)
@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}