# ViewSets for FastApi

### Installation

For install package run command

```
 pip install fastapi_viewsets
```

### Usage
Create python environment and install this packages:
```
pip install PyJWT
pip install bcrypt
```
Create ```main.py``` and copy this code:
```
from datetime import timedelta, datetime
from typing import Optional

import bcrypt as bcrypt
import jwt as jwt
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi_viewsets import BaseViewset
from fastapi_viewsets.db_conf import Base, get_session, engine
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Boolean

# create fastapi app
from starlette import status

app = FastAPI()


class UserSchema(BaseModel):
    """Pydantic Schema"""
    id: Optional[int]
    username: str
    password: str
    is_admin: Optional[bool]

    class Config:
        orm_mode = True


class User(Base):
    """SQLAlchemy model"""

    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    password = Column(String(255))
    is_admin = Column(Boolean, default=False)


Base.metadata.create_all(engine)  # created table in db (by default this is sqlite3 base.db)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# created viewset for our model
user_model = BaseViewset(
    endpoint='/user',
    model=User,
    response_model=UserSchema,
    db_session=get_session,
    tags=['Fast example endpoint']
)

# registered all methods GET POST PUT PATCH DELETE
user_model.register()

protected_user_model = BaseViewset(prefix='/protected',
                                   endpoint='/user',
                                   model=User,
                                   response_model=UserSchema,
                                   db_session=get_session,
                                   tags=['Protected endpoint']
                                   )
# registered only selected methods and protected selected ones
protected_user_model.register(methods=['LIST', 'POST', 'GET', 'PUT'],
                              protected_methods=['LIST', 'POST', 'GET', 'PUT'],
                              oauth_protect=oauth2_scheme)

# add routes to fastapi
app.include_router(user_model)
app.include_router(protected_user_model)

# other endpoints

secret_key = 'SECRET_KEY'

algorithm = "HS256"


def create_access_token(data, expires_delta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    access_token = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return access_token


@app.get("/items/")
async def read_items(token: str = Depends(oauth2_scheme)):
    return {"token": token}


@app.post('/token')
def generate_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user_form = UserSchema(username=form_data.username, password=form_data.password)
    user = get_session().query(User).filter(User.username == user_form.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='username is incorrect'
        )

    if user_form.password.encode("utf-8") == user.password.encode(
            "utf-8"):  # need to hash the password wen create user and use bcrypt for check
        access_token_expires = timedelta(minutes=60 * 5)
        access_token = create_access_token(data={"user": user.username, "id": user.id},
                                           expires_delta=access_token_expires)
        return {'access_token': access_token, 'token_type': 'bearer'}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='password is incorrect'
        )

```
Run by command ```uvicorn main:app --reload```

After start application go to [docs](http://localhost:8000/docs)