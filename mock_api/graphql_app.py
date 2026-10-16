"""Small Strawberry GraphQL mock for protocol-drift tests."""

import strawberry
from fastapi import FastAPI, HTTPException
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig


@strawberry.type
class User:
    id: str
    name: str
    email: str


@strawberry.type
class UserEnvelope:
    data: User


class GraphQLMock:
    def __init__(self) -> None:
        self.data = {
            "123": {"name": "Ada", "email": "ada@example.com"},
            "456": {"name": "Bob", "email": "bob@example.com"},
        }
        self.mutation: str | None = None
        self.app = self._build()

    def set_mutation(self, mutation: str | None) -> None:
        if mutation not in (None, "M1", "M2", "M3"):
            raise ValueError(f"unknown GraphQL mutation {mutation!r}")
        self.mutation = mutation
        self.app = self._build()

    def state(self) -> dict:
        return {key: dict(value) for key, value in self.data.items()}

    def _build(self) -> FastAPI:
        api = self
        m1, m2, m3 = self.mutation == "M1", self.mutation == "M2", self.mutation == "M3"

        if m1 and m3:
            @strawberry.type
            class Query:
                @strawberry.field(name="get_user")
                def get_user(self, customer_id: str) -> UserEnvelope:
                    return api.lookup(customer_id, True)
        elif m1:
            @strawberry.type
            class Query:
                @strawberry.field(name="get_user")
                def get_user(self, customer_id: str) -> User:
                    return api.lookup(customer_id, False)
        elif m3:
            @strawberry.type
            class Query:
                @strawberry.field(name="get_user")
                def get_user(self, user_id: str) -> UserEnvelope:
                    return api.lookup(user_id, True)
        else:
            @strawberry.type
            class Query:
                @strawberry.field(name="get_user")
                def get_user(self, user_id: str) -> User:
                    return api.lookup(user_id, False)

        @strawberry.type
        class Mutation:
            @strawberry.mutation(name="update_email")
            def update_email(self, user_id: int if m2 else str, email: str) -> User:
                uid = str(user_id)
                if uid not in api.data:
                    raise HTTPException(404, "user not found")
                api.data[uid]["email"] = email
                return User(id=uid, **api.data[uid])

        schema = strawberry.Schema(
            query=Query, mutation=Mutation, config=StrawberryConfig(auto_camel_case=False)
        )
        app = FastAPI()
        app.include_router(GraphQLRouter(schema), prefix="/graphql")
        return app

    def lookup(self, uid: str, nested: bool) -> User | UserEnvelope:
        if uid not in self.data:
            raise HTTPException(404, "user not found")
        user = User(id=uid, **self.data[uid])
        return UserEnvelope(data=user) if nested else user

    async def __call__(self, scope, receive, send) -> None:
        await self.app(scope, receive, send)


def create_app() -> GraphQLMock:
    return GraphQLMock()
