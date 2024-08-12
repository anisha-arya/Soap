import sqlite3
from werkzeug.security import generate_password_hash

# Connect to your SQLite database
conn = sqlite3.connect('Soap.db')
cursor = conn.cursor()

# Fetch all users and their plain text passwords
cursor.execute("SELECT userid, password FROM User")
users = cursor.fetchall()

# Loop through users, hash their passwords, and update the database
for user in users:
    userid, plain_text_password = user
    
    # Hash the plain text password
    hashed_password = generate_password_hash(plain_text_password)
    
    # Update the database with the hashed password
    cursor.execute("UPDATE User SET password = ? WHERE userid = ?", (hashed_password, userid))

# Commit the changes and close the connection
conn.commit()
conn.close()

print("All passwords have been hashed and updated in the database.")
