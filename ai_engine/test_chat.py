import requests

URL = "http://localhost:8001/api/v1/chat"

print("🤖 ALITA Offline RAG Chat Terminal")
print("Type 'exit' or 'quit' to stop.\n")

while True:
    question = input("You: ")
    if question.lower() in ['exit', 'quit']:
        break
        
    print("ALITA is thinking...")
    
    payload = {"question": question}
    response = requests.post(URL, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\nALITA: {data['answer']}")
        print(f"(Sources used: {len(data['sources'])})\n")
    else:
        print(f"\n❌ Error: {response.text}\n")