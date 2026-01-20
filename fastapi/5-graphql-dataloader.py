from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
import strawberry
from strawberry.types import Info
from strawberry.dataloader import DataLoader
import asyncio

# ----------------------------
# In-memory data (simulating DB tables)
# ----------------------------
CUSTOMERS = {
    1: {"id": 1, "name": "Alice", "email": "alice@x.com"},
    2: {"id": 2, "name": "Bob",   "email": "bob@x.com"},
    3: {"id": 3, "name": "Asha",  "email": "asha@x.com"},
}
NEXT_ID = 4

ORDERS = {
    1: [{"id": 101, "total": 250.0}, {"id": 102, "total": 99.5}],
    2: [{"id": 201, "total": 500.0}],
    3: [{"id": 301, "total": 10.0}, {"id": 302, "total": 20.0}, {"id": 303, "total": 30.0}],
}
NEXT_ORDER_ID = 303


# ----------------------------
# N+1 SIMULATION HELPERS
# ----------------------------
DB_CALLS = {"orders_selects": 0}  # just to prove N+1 behavior

def db_select_orders_by_customer_id(customer_id: int) -> list[dict]:
    # N+1 PROBLEM: if this runs per customer, you get N selects
    DB_CALLS["orders_selects"] += 1
    return ORDERS.get(customer_id, [])

def db_select_orders_by_customer_ids(customer_ids: list[int]) -> dict[int, list[dict]]:
    # BATCH FIX: one select for all customers in this request
    DB_CALLS["orders_selects"] += 1
    return {cid: ORDERS.get(cid, []) for cid in customer_ids}


# ----------------------------
# DataLoader (BATCH LOADER)
# ----------------------------
async def batch_load_orders(customer_ids: list[int]) -> list[list[dict]]:
    # DataLoader calls this ONCE with many keys (customer_ids)
    # Simulate async IO boundary:
    await asyncio.sleep(0)

    rows_map = db_select_orders_by_customer_ids(customer_ids)

    # IMPORTANT: must return results in SAME order as input keys
    return [rows_map.get(cid, []) for cid in customer_ids]


def make_context() -> dict:
    # Per-request context (fresh DataLoader per request is typical)
    return {
        "orders_loader": DataLoader(load_fn=batch_load_orders),
        "db_calls": DB_CALLS,  # just to observe counts
    }


# ----------------------------
# GraphQL Types
# ----------------------------
@strawberry.type
class Order:
    id: int
    total: float


@strawberry.type
class Customer:
    id: int
    name: str
    email: str

    @strawberry.field
    async def orders(self, info: Info) -> list["Order"]:
        # ✅ FIX: use DataLoader (BATCH) instead of per-customer "select"
        loader: DataLoader[int, list[dict]] = info.context["orders_loader"]
        order_rows = await loader.load(self.id)  # batched across all customers
        return [Order(**o) for o in order_rows]

        # ❌ NAIVE (N+1): uncomment to see N selects
        # order_rows = db_select_orders_by_customer_id(self.id)
        # return [Order(**o) for o in order_rows]


# ----------------------------
# GraphQL Inputs
# ----------------------------
@strawberry.input
class CustomerCreateInput:
    name: str
    email: str


@strawberry.input
class OrderCreateInput:
    total: float


# ----------------------------
# Query Root
# ----------------------------
@strawberry.type
class Query:
    @strawberry.field
    def customers(self, name_contains: str | None = None) -> list[Customer]:
        rows = list(CUSTOMERS.values())
        if name_contains:
            needle = name_contains.lower()
            rows = [r for r in rows if needle in r["name"].lower()]
        return [Customer(**r) for r in rows]

    @strawberry.field
    def customer(self, id: int) -> Customer | None:
        row = CUSTOMERS.get(id)
        return Customer(**row) if row else None

    @strawberry.field
    def debug_db_calls(self, info: Info) -> str:
        # handy to see N+1 vs batch (run query then call this)
        return f"orders_selects={info.context['db_calls']['orders_selects']}"


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
        ORDERS[cid] = []
        return Customer(**row)

    @strawberry.mutation
    def create_order(self, customer_id: int, input: OrderCreateInput) -> Order | None:
        global NEXT_ORDER_ID
        if customer_id not in CUSTOMERS:
            return None
        NEXT_ORDER_ID += 1
        order_row = {"id": NEXT_ORDER_ID, "total": float(input.total)}
        ORDERS.setdefault(customer_id, []).append(order_row)
        return Order(**order_row)


# ----------------------------
# FastAPI + GraphiQL
# ----------------------------
schema = strawberry.Schema(query=Query, mutation=Mutation)

app = FastAPI(title="Customers GraphQL (N+1 + DataLoader)")

# NOTE: context_getter is how resolvers access DataLoader via info.context
app.include_router(GraphQLRouter(schema, context_getter=make_context), prefix="/graphql")
