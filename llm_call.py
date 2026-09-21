from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import os

load_dotenv()

llm = ChatOpenAI(
    model=os.getenv("MODEL"),
    max_tokens=None,
    base_url=os.getenv("BASE_URL"),
    api_key=os.getenv("API_KEY"),
)

response = llm.invoke(input("Hi! I am an AI assistant. Ask me anything! : \n"))

print(response.content)
