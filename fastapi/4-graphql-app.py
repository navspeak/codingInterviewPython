from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
import strawberry

# ----------------------------
# In-memory "customer table"
# ----------------------------
CUSTOMERS: dict[int, dict] = {
    1: {"id": 1, "name": "Alice", "email": "alice@x.com"},
    2: {"id": 2, "name": "Bob",   "email": "bob@x.com"},
    3: {"id": 3, "name": "Asha",  "email": "asha@x.com"},
}
NEXT_ID = 4


# ----------------------------
# GraphQL Types
# ----------------------------
@strawberry.type
class Customer:
    id: int
    name: str
    email: str


# ----------------------------
# GraphQL Inputs (DTOs)
# ----------------------------
@strawberry.input
class CustomerCreateInput:
    name: str
    email: str


@strawberry.input
class CustomerUpdateInput:
    name: str | None = None
    email: str | None = None


# ----------------------------
# Query Root
# ----------------------------
@strawberry.type
class Query:
    @strawberry.field
    def customer(self, id: int) -> Customer | None:
        row = CUSTOMERS.get(id)
        return Customer(**row) if row else None

    @strawberry.field
    def customers(self, name_contains: str | None = None) -> list[Customer]:
        rows = list(CUSTOMERS.values())

        if name_contains:
            needle = name_contains.lower()
            rows = [r for r in rows if needle in r["name"].lower()]

        return [Customer(**r) for r in rows]


# ----------------------------
# Mutation Root
# ----------------------------
@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_customer(self, input: CustomerCreateInput) -> Customer:
        global NEXT_ID
        cid = NEXT_ID
        NEXT_ID += 1

        row = {"id": cid, "name": input.name, "email": input.email}
        CUSTOMERS[cid] = row
        return Customer(**row)

    @strawberry.mutation
    def update_customer(self, id: int, input: CustomerUpdateInput) -> Customer | None:
        row = CUSTOMERS.get(id)
        if not row:
            return None

        # PATCH semantics: only update fields provided
        if input.name is not None:
            row["name"] = input.name
        if input.email is not None:
            row["email"] = input.email

        return Customer(**row)

    @strawberry.mutation
    def delete_customer(self, id: int) -> bool:
        return CUSTOMERS.pop(id, None) is not None


# ----------------------------
# FastAPI + GraphiQL
# ----------------------------
schema = strawberry.Schema(query=Query, mutation=Mutation)

app = FastAPI(title="Customers GraphQL (In-Memory)")
app.include_router(GraphQLRouter(schema), prefix="/graphql")
