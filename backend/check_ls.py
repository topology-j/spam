from dotenv import load_dotenv
import os
load_dotenv('.env', override=True)
from langsmith import Client
client = Client(api_key=os.getenv("LANGSMITH_API_KEY"))
projects = list(client.list_projects())
for p in projects:
    print(p.name)
