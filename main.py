
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Security
)

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

from pydantic import BaseModel, Field, EmailStr, ConfigDict
from sqlalchemy.orm import Session

import jwt

from database import get_db, init_db
from models import Student

from security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token
)


app = FastAPI(title="AI Tutor API")

# Initialize database
init_db()

# JWT Authentication Scheme
bearer_scheme = HTTPBearer()


# ==============================
# PYDANTIC SCHEMAS
# ==============================

class StudentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)


class StudentLogin(BaseModel):
    email: EmailStr
    password: str


class StudentUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100
    )
    email: EmailStr | None = None


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr


# ==============================
# HOME API
# ==============================

@app.get("/")
def home():
    return {
        "message": "Welcome to AI Tutor API"
    }


# ==============================
# STUDENT REGISTRATION API
# ==============================

@app.post(
    "/register",
    response_model=StudentResponse,
    status_code=201
)
def register_student(
    student_data: StudentCreate,
    db: Session = Depends(get_db)
):

    existing_student = db.query(Student).filter(
        Student.email == student_data.email
    ).first()

    if existing_student:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    hashed_password = hash_password(
        student_data.password
    )

    new_student = Student(
        name=student_data.name,
        email=student_data.email,
        password=hashed_password
    )

    db.add(new_student)
    db.commit()
    db.refresh(new_student)

    return new_student


# ==============================
# STUDENT LOGIN API WITH JWT
# ==============================

@app.post("/login")
def login_student(
    login_data: StudentLogin,
    db: Session = Depends(get_db)
):

    student = db.query(Student).filter(
        Student.email == login_data.email
    ).first()

    if not student:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not verify_password(
        login_data.password,
        student.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    access_token = create_access_token(
        data={"sub": str(student.id)}
    )

    return {
        "message": "Login Successful!",
        "access_token": access_token,
        "token_type": "bearer",
        "student_id": student.id,
        "name": student.name,
        "email": student.email
    }


# ==============================
# GET CURRENT STUDENT
# ==============================

def get_current_student(
    credentials: HTTPAuthorizationCredentials = Security(
        bearer_scheme
    ),
    db: Session = Depends(get_db)
):

    token = credentials.credentials

    try:
        payload = decode_access_token(token)

        student_id = payload.get("sub")

        if not student_id:
            raise ValueError("Student ID missing")

        student_id = int(student_id)

    except (
        jwt.InvalidTokenError,
        ValueError,
        TypeError
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    student = db.query(Student).filter(
        Student.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=401,
            detail="Student not found",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    return student


# ==============================
# PROTECTED STUDENT PROFILE API
# ==============================

@app.get(
    "/me",
    response_model=StudentResponse
)
def read_current_student(
    current_student: Student = Depends(
        get_current_student
    )
):

    return current_student


# ==============================
# GET ALL STUDENTS API
# ==============================

@app.get(
    "/students",
    response_model=list[StudentResponse]
)
def get_students(
    current_student: Student = Depends(
        get_current_student
    ),
    db: Session = Depends(get_db)
):

    students = db.query(Student).all()

    return students


# ==============================
# GET STUDENT BY ID API
# ==============================

@app.get(
    "/students/{student_id}",
    response_model=StudentResponse
)
def get_student_by_id(
    student_id: int,
    current_student: Student = Depends(
        get_current_student
    ),
    db: Session = Depends(get_db)
):

    student = db.query(Student).filter(
        Student.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student not found"
        )

    return student


# ==============================
# UPDATE STUDENT PROFILE API
# ==============================

@app.put(
    "/students/{student_id}",
    response_model=StudentResponse
)
def update_student(
    student_id: int,
    student_data: StudentUpdate,
    current_student: Student = Depends(
        get_current_student
    ),
    db: Session = Depends(get_db)
):

    # Student can update only their own profile
    if current_student.id != student_id:
        raise HTTPException(
            status_code=403,
            detail="You can only update your own profile"
        )

    student = db.query(Student).filter(
        Student.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student not found"
        )

    update_data = student_data.model_dump(
        exclude_unset=True
    )

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No update data provided"
        )

    if "name" in update_data and update_data["name"] is None:
        raise HTTPException(
            status_code=422,
            detail="Name cannot be null"
        )

    if "email" in update_data and update_data["email"] is None:
        raise HTTPException(
            status_code=422,
            detail="Email cannot be null"
        )

    if "email" in update_data:
        existing_student = db.query(Student).filter(
            Student.email == update_data["email"],
            Student.id != student_id
        ).first()

        if existing_student:
            raise HTTPException(
                status_code=409,
                detail="Email already registered"
            )

    for key, value in update_data.items():
        setattr(student, key, value)

    db.commit()
    db.refresh(student)

    return student


# ==============================
# DELETE STUDENT ACCOUNT API
# ==============================

@app.delete("/students/{student_id}")
def delete_student(
    student_id: int,
    current_student: Student = Depends(
        get_current_student
    ),
    db: Session = Depends(get_db)
):

    # Student can delete only their own account
    if current_student.id != student_id:
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own account"
        )

    student = db.query(Student).filter(
        Student.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student not found"
        )

    db.delete(student)
    db.commit()

    return {
        "message": "Student account deleted successfully",
        "student_id": student_id
    }
