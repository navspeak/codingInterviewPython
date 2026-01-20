from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

app = FastAPI(title="Customer API")

# ---------- DTOs (Pydantic models) ----------

class CustomerBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr

class CustomerCreate(CustomerBase):
    pass  # same fields as base

class CustomerUpdate(BaseModel):
    # partial update (PATCH-like); all optional
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    email: Optional[EmailStr] = None

class CustomerOut(CustomerBase):
    id: int

# ---------- "Repository" (in-memory, no DB) ----------

class CustomerRepo:
    def __init__(self) -> None:
        self._db: Dict[int, CustomerOut] = {}
        self._seq: int = 1

    def create(self, dto: CustomerCreate) -> CustomerOut:
        cid = self._seq
        self._seq += 1
        customer = CustomerOut(id=cid, **dto.model_dump())
        self._db[cid] = customer
        return customer

    def get(self, cid: int) -> Optional[CustomerOut]:
        return self._db.get(cid)

    def list_all(self) -> List[CustomerOut]:
        # stable ordering by id
        return [self._db[k] for k in sorted(self._db.keys())]

    def update(self, cid: int, dto: CustomerUpdate) -> Optional[CustomerOut]:
        existing = self._db.get(cid)
        if not existing:
            return None

        patch = dto.model_dump(exclude_unset=True)  # only provided fields
        updated = existing.model_copy(update=patch)
        self._db[cid] = updated
        return updated

    def delete(self, cid: int) -> bool:
        return self._db.pop(cid, None) is not None


repo = CustomerRepo()

# ---------- CRUD endpoints ----------

@app.post("/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(dto: CustomerCreate):
    return repo.create(dto)

@app.get("/customers/{cid}", response_model=CustomerOut)
def get_customer(cid: int):
    customer = repo.get(cid)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@app.get("/customers", response_model=list[CustomerOut])
def list_customers():
    return repo.list_all()

@app.put("/customers/{cid}", response_model=CustomerOut)
def update_customer(cid: int, dto: CustomerUpdate):
    customer = repo.update(cid, dto)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@app.delete("/customers/{cid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(cid: int):
    ok = repo.delete(cid)
    if not ok:
        raise HTTPException(status_code=404, detail="Customer not found")
    return None
