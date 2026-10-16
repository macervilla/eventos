from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.usuarios import UserLocationPreference
from app.schemas.ubicacion import UserLocationPreferenceUpsert


def get_preference(db: Session, user_id: int) -> UserLocationPreference | None:
    return db.scalar(
        select(UserLocationPreference).where(UserLocationPreference.user_id == user_id)
    )


def upsert_preference(
    db: Session,
    *,
    user_id: int,
    data: UserLocationPreferenceUpsert,
) -> UserLocationPreference:
    preference = get_preference(db, user_id)
    values = data.model_dump()

    if preference is None:
        preference = UserLocationPreference(user_id=user_id, **values)
        db.add(preference)
    else:
        for key, value in values.items():
            setattr(preference, key, value)

    db.commit()
    db.refresh(preference)
    return preference
