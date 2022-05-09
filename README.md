# ViewSets for FastApi

### Installation

For install package run command

```
 pip install fastapi_viewsets
```

### Usage

Create ```main.py``` and copy this code:
```
from typing import Optional

from fastapi import FastAPI
from fastapi_viewsets import Base as BaseViewset
from fastapi_viewsets.db_conf import Base, get_session, engine
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Boolean

# create fastapi app
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


Base.metadata.create_all(engine)  # create table in db (by default this is sqlite3 base.db)

# create viewset for our model
user_model = BaseViewset(prefix='/users',
                         endpoint='/user',
                         model=User,
                         response_model=UserSchema,
                         db_session=get_session
                         )
# register all methods GET POST PUT PATCH DELETE 
user_model.register()

# add rote to fastapi 
app.include_router(user_model)

```
Run by command ```uvicorn main:app --reload```

After start application go to [docs](http://localhost:8000/docs)