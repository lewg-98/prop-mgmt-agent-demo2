import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def test_connection():
    try:
        # Print connection details for debugging (remove in production)
        print(f"Attempting to connect to:")
        print(f"Host: {os.getenv('DB_HOST')}")
        print(f"Database: {os.getenv('DB_NAME')}")
        print(f"User: {os.getenv('DB_USER')}")
        
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT', '5432')
        )
        print("Successfully connected to database!")
        
        # Test query
        cur = conn.cursor()
        cur.execute("SELECT * FROM properties;")
        properties = cur.fetchall()
        print("Found properties:", properties)
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error connecting to database: {e}")

if __name__ == "__main__":
    test_connection()