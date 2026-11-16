from database import init_db
import models

try:
    init_db()
    print("Student Table Created Successfully!")

except Exception as e:
    print("Database Error:", e)