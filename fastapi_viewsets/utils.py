from fastapi import HTTPException
from starlette import status

def get_list_queryset(model, db_session, limit=None, offset=None):
    queryset = db_session().query(model)
    if limit:
        queryset = queryset.limit(limit)
    if offset:
        queryset = queryset.offset(offset)
    return queryset.all()


def get_element_by_id(model, db_session, id: int or str):
    return db_session().query(model).filter(getattr(model, 'id') == id).first()


def create_element(model, db_session, data):
    try:
        db = db_session()
        queryset = model(**data)
        db.add(queryset)
        db.commit()
        db.refresh(queryset)
        return queryset
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))



def update_element(model, db_session, id, data):
    db = db_session()
    data = {key: value for key, value in dict(data).items() if value}
    db.query(model).filter(getattr(model, 'id') == id).update(data, synchronize_session=False)
    db.commit()
    return get_element_by_id(model, db_session, id)


def delete_element(model, db_session, id):
    db = db_session()
    result = db.get(model, id)
    if not result:
        raise HTTPException(status_code=404, detail="Model not found")
    db.delete(result)
    db.commit()
    return True
