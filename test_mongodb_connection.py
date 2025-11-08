from pymongo import MongoClient
import urllib.parse
import sys

def test_connection(username, password, host, database_name):
    try:
        # Encode credentials
        encoded_username = urllib.parse.quote_plus(username)
        encoded_password = urllib.parse.quote_plus(password)
        
        # Construct connection string
        uri = f"mongodb+srv://{encoded_username}:{encoded_password}@{host}/?retryWrites=true&w=majority"
        print(f"Testing connection with URI: {uri}")
        print(f"Database name: {database_name}")
        
        # Try to connect
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        
        # Test database access
        db = client[database_name]
        
        # List collections (this will test database access)
        collections = db.list_collection_names()
        print(f"Available collections: {list(collections)}")
        
        print("Connection successful! Database is accessible.")
        return True
        
    except Exception as e:
        print(f"Connection failed with error: {str(e)}")
        return False

if __name__ == "__main__":
    # Your MongoDB Atlas credentials
    username = "mokshagnaande55"
    password = "Moksha256@"
    host = "cluster0.tkhcz.mongodb.net"
    database_name = "Cluster0"
    
    # Test connection
    print("\nTesting connection to MongoDB Atlas...")
    test_connection(username, password, host, database_name)