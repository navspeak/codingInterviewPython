from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
import strawberry

# ----------------------------
# In-memory "customer table"
# ----------------------------
CUSTOMERS = {
    1: {"id": 1, "name": "Alice", "email": "alice@x.com"},
    2: {"id": 2, "name": "Bob",   "email": "bob@x.com"},
}
NEXT_ID = 3  # ADDED: fix create_customer (NEXT_ID was used but not defined)

ORDERS = {
    1: [
        {"id": 101, "total": 250.0},
        {"id": 102, "total": 99.5},
    ],
    2: [
        {"id": 201, "total": 500.0},
    ],
}
NEXT_ORDER_ID = 202  # ADDED: simple order id generator


# ----------------------------
# GraphQL Types
# ----------------------------
@strawberry.type
class Order:
    id: int
    total: float
    # NOTE: Order.id and Order.total use DEFAULT resolvers

@strawberry.type
class Customer:
    id: int
    name: str
    email: str
    # NOTE: id, name, email use DEFAULT resolvers

    @strawberry.field
    def orders(self) -> list[Order]:
        # existing: field-level resolver for Customer.orders
        return [Order(**o) for o in ORDERS.get(self.id, [])] 

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
        # RESOLVER: Query.customer
        row = CUSTOMERS.get(id)
        return Customer(**row) if row else None

    @strawberry.field
    def customers(self, name_contains: str | None = None) -> list[Customer]:
        # RESOLVER: Query.customers
        rows = list(CUSTOMERS.values())

        if name_contains:
            needle = name_contains.lower()
            rows = [r for r in rows if needle in r["name"].lower()]

        return [Customer(**r) for r in rows]

    @strawberry.field
    def orders(self, customer_id: int) -> list[Order]:
        # RESOLVER: Query.orders
        return [Order(**o) for o in ORDERS.get(customer_id, [])]
    
# ----------------------------
# Mutation Root
# ----------------------------
@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_customer(self, input: CustomerCreateInput) -> Customer:
        # RESOLVER: Mutation.create_customer
        global NEXT_ID
        cid = NEXT_ID
        NEXT_ID += 1
        row = {"id": cid, "name": input.name, "email": input.email}
        CUSTOMERS[cid] = row
        ORDERS[cid] = []
        return Customer(**row)

    @strawberry.mutation
    def update_customer(self, id: int, input: CustomerUpdateInput) -> Customer | None:
        # RESOLVER: Mutation.update_customer
        row = CUSTOMERS.get(id)
        if not row:
            return None
        if input.name is not None:
            row["name"] = input.name
        if input.email is not None:
            row["email"] = input.email
        return Customer(**row)

    @strawberry.mutation
    def delete_customer(self, id: int) -> bool:
        # RESOLVER: Mutation.delete_customer
        existed = CUSTOMERS.pop(id, None) is not None
        if existed:
            ORDERS.pop(id, None)
        return existed

    @strawberry.mutation
    def create_order(self, customer_id: int, input: OrderCreateInput) -> Order | None:
        # RESOLVER: Mutation.create_order
        global NEXT_ORDER_ID
        if customer_id not in CUSTOMERS:
            return None
        NEXT_ORDER_ID += 1
        order = {"id": NEXT_ORDER_ID, "total": input.total}
        ORDERS.setdefault(customer_id, []).append(order)
        return Order(**order)


# ----------------------------
# Schema + App
# ----------------------------
schema = strawberry.Schema(query=Query, mutation=Mutation)

app = FastAPI()
app.include_router(GraphQLRouter(schema), prefix="/graphql")

#--------------------------------
# Query
#--------------------------------
# query {
#   customers {
#     id
#     name
#     email
#   }
# }
# query {
#   customers(nameContains: "ali") {
#     id
#     name
#   }
# }
# query {
#   customer(id: 1) {
#     id
#     name
#     orders {
#       id
#       total
#     }
#   }
# }
# query {
#   orders(customerId: 1) {
#     id
#     total
#   }
# }
#--------------------------------
# Mutations
#--------------------------------
# mutation {
#   createCustomer(
#     input: { name: "Charlie", email: "charlie@x.com" }
#   ) {
#     id
#     name
#     email
#   }
# }
# mutation {
#   updateCustomer(
#     id: 1
#     input: { email: "alice.new@x.com" }
#   ) {
#     id
#     name
#     email
#   }
# }
# NOTE:
# query {
#   customers {
#     name
#   }
# }
# uses :
#     Query.customers
#     Customer.name (default resolver)

# query {
#   customers {
#     name
#     orders {
#       total
#     }
#   }
# }
# uses:
#     Query.customers
#     Customer.name (default)
#     Customer.orders   ← NON-DEFAULT resolver
#     Order.total (default)

# This is source of N+1
# NOTE: Autocomplete in graphiql works because GraphQL has a strongly-typed schema that the client can introspect at runtime.
# Introspection is a built-in GraphQL capability that lets clients ask:
# “What types, fields, and arguments does this API support?”
# GraphQL servers expose special meta-fields like:
# __schema
# __type
# Example (you never type this manually):
# query {
#   __schema {
#     types {
#       name
#       fields {
#         name
#       }
#     }
#   }
# }
# this is code first not schema first (where graphql schema is create .graphql)
#Can Strawberry Do Schema-First?

# ⚠️ Not really (by design)
# Strawberry intentionally favors code-first.
# Schema-first tools are more common in:
# Apollo (JS/TS)
# graphql-java (Netflix DGS, Kickstart)