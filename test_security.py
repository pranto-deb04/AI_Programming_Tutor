from security import hash_password, verify_password

password = "MySecurePassword123"

hashed = hash_password(password)

print("Original Password:", password)
print("Hashed Password:", hashed)

if verify_password(password, hashed):
    print("Password Verification Successful!")
else:
    print("Password Verification Failed!")