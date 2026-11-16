from database import SessionLocal
from models import Student

db = SessionLocal()

try:
    student = db.query(Student).filter(
        Student.email == "test@example.com"
    ).first()

    if student is None:
        student = Student(
            name="Test Student",
            email="test@example.com",
            password="temporary-test-only"
        )

        db.add(student)
        db.commit()
        db.refresh(student)

    print("Student Added Successfully!")
    print("Student ID:", student.id)
    print("Student Name:", student.name)
    print("Student Email:", student.email)

except Exception as e:
    db.rollback()
    print("Error:", e)

finally:
    db.close()