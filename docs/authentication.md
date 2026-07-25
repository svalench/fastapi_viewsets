# Authentication

`register()` accepts an `OAuth2PasswordBearer` instance plus a list of logical operations that require a bearer token.

## How it works

```python
from fastapi import FastAPI
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Integer, String
from typing import Optional
from fastapi_viewsets import BaseViewset
from fastapi_viewsets.db_conf import Base, engine, get_session

app = FastAPI()
oauth2 = OAuth2PasswordBearer(tokenUrl="/token")

class Item(Base):
    """SQLAlchemy model for OAuth2-protected writes."""

    __tablename__ = "items_oauth"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)


class ItemSchema(BaseModel):
    """Pydantic schema for Item payloads and responses."""

    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    name: str


Base.metadata.create_all(bind=engine)
router = BaseViewset(
    endpoint="/items",
    model=Item,
    response_model=ItemSchema,
    db_session=get_session,
    tags=["items"],
)
router.register(
    methods=["LIST", "GET", "POST", "PATCH", "DELETE"],
    oauth_protect=oauth2,
    protected_methods=["POST", "PATCH", "DELETE"],
)
app.include_router(router)
```

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `methods` | `Optional[List[str]]` | `None` (all) | Logical methods to register: `LIST`, `GET`, `POST`, `PUT`, `PATCH`, `DELETE` |
| `oauth_protect` | `Optional[OAuth2PasswordBearer]` | `None` | OAuth2 dependency instance |
| `protected_methods` | `Optional[List[str]]` | `None` | Subset of `methods` that require the bearer token. Ignored if `oauth_protect` is `None`. |

## How protection is applied internally

When a method is in `protected_methods` and `oauth_protect` is provided:

1. The handler is wrapped with `functools.partial(handler, token=Depends(oauth_protect))`.
2. FastAPI injects the `OAuth2PasswordBearer` dependency, which requires the `Authorization: Bearer <token>` header on protected methods.
3. If the header is missing, FastAPI returns `401 Unauthorized` automatically.
4. Token validation and authorization logic (e.g. decoding JWT, checking scopes) is your responsibility — implement it in a dependency or inside the handler override.

Methods not in `protected_methods` remain publicly accessible. This lets you, for example, allow anonymous reads (`LIST`, `GET`) while requiring authentication for writes (`POST`, `PATCH`, `DELETE`).

## Adding a token endpoint

You still need to implement the `/token` endpoint that issues JWT tokens. Here's a minimal example:

!!! danger "Demo only — not production-ready"

    The example below issues a JWT to **any** username/password pair without
    verifying credentials. It also uses a hardcoded `SECRET_KEY`. Before
    deploying:

    - Replace the stub with real credential verification (database lookup,
      password hashing with `passlib[bcrypt]`).
    - Load `SECRET_KEY` from an environment variable or secrets manager.
    - Validate `exp`, `sub`, algorithm, audience, and issuer on every
      protected request via a dedicated dependency — `OAuth2PasswordBearer`
      only checks for the presence of a bearer header; any string passes.

```python
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"


@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Verify credentials here (e.g., check against a user table)
    # For demo purposes, always issue a token:
    access_token = jwt.encode(
        {
            "sub": form_data.username,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return {"access_token": access_token, "token_type": "bearer"}
```

!!! tip "Dependencies"

    For the token endpoint example above, install `python-jose`:

    ```bash
    pip install python-jose[cryptography]
    ```

    If you plan to hash passwords with `passlib`, install it separately:

    ```bash
    pip install passlib[bcrypt]
    ```

## Next steps

- [Overriding Handlers](overrides.md) — subclass for custom logic
- [Custom Routes](custom-routes.md) — adding non-CRUD endpoints
