
from security import create_access_token, decode_access_token

# Create JWT Token
token = create_access_token({
    "sub": "2"
})

print("JWT Token Created Successfully!")
print(token)

# Verify JWT Token
payload = decode_access_token(token)

print("\nJWT Token Verified Successfully!")
print("Student ID:", payload["sub"])
print("Expiration:", payload["exp"])
