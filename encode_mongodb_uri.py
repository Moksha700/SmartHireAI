import urllib.parse

# Original credentials
username = "mokshagnaande55"
password = "Moksha256@"  # Note: removed the extra @ symbols
host = "cluster0.tkhcz.mongodb.net"

# Encode the username and password
encoded_username = urllib.parse.quote_plus(username)
encoded_password = urllib.parse.quote_plus(password)

# Construct the URI
uri = f"mongodb+srv://{encoded_username}:{encoded_password}@{host}/?retryWrites=true&w=majority"

print("Encoded MongoDB URI:")
print(uri)