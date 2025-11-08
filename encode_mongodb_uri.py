import urllib.parse

username = "mokshagnaande55"
password = "Moksha256@"
cluster = "cluster0.tkhcz.mongodb.net"

# URL encode the username and password
encoded_username = urllib.parse.quote_plus(username)
encoded_password = urllib.parse.quote_plus(password)

# Create the connection string
uri = f"mongodb+srv://{encoded_username}:{encoded_password}@{cluster}/"
print("Your encoded MongoDB URI:")
print(uri)