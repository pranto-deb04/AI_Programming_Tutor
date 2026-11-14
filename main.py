
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

# Student Registration Schema
class StudentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)


# Student Login Schema
class StudentLogin(BaseModel):
    email: EmailStr
    password: str


# Student Response Schema
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

    # Check existing email
    existing_student = db.query(Student).filter(
        Student.email == student_data.email
    ).first()

    if existing_student:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    # Hash password
    hashed_password = hash_password(
        student_data.password
    )

    # Create student
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

    # Find student by email
    student = db.query(Student).filter(
        Student.email == login_data.email
    ).first()

    # Check student exists
    if not student:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    # Verify password
    if not verify_password(
        login_data.password,
        student.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    # Generate JWT Access Token
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
        # Decode JWT Token
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

    # Find student in database
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
