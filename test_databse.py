from database import engine

try:
    with engine.connect() as connection:
        result = connection.exec_driver_sql("SELECT 1")
        print("Database Connected Successfully!")
        print("Test Result:", result.scalar())

except Exception as e:
    print("Database Connection Failed!")
    print("Error:", e)