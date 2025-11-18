import os
import json
import re
from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.schema import Document
from langchain.prompts import PromptTemplate

# Path to JSON file
json_path = "devices.json"

# Check if file exists
if not os.path.exists(json_path):
    print(f"Error: File '{json_path}' not found.")
    exit(1)

# Loading the LLM
llm = Ollama(
    model="fixt/home-3b-v2:latest",
    temperature=0
)

def load_json():
    """Load the JSON file"""
    with open(json_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def save_json(data):
    """Save data back to JSON file"""
    with open(json_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=2)
    print(f"✅ Saved changes to {json_path}")

def parse_and_apply_changes(answer):
    """Parse the AI's answer and apply changes to JSON"""
    data = load_json()
    modified = False
    changes_made = []
    
    # Pattern 1: "light_living: state = 2"
    pattern1 = r'(\w+):\s*(\w+)\s*=\s*(\w+|true|false|\d+)'
    matches1 = re.findall(pattern1, answer)
    
    for match in matches1:
        device_id = match[0]
        field = match[1]
        value = match[2]
        
        # Find the device
        for gadget in data["gadgets"]:
            if gadget["id"] == device_id:
                # Convert value to appropriate type
                if value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                elif value.isdigit():
                    value = int(value)
                
                # Update the field
                gadget[field] = value
                modified = True
                changes_made.append(f"{device_id}.{field} = {value}")
                print(f"  🔧 Modified {device_id}: {field} = {value}")
    
    # Pattern 2: "device_id: {field: value}"
    pattern2 = r'(\w+):\s*\{([^}]+)\}'
    matches2 = re.findall(pattern2, answer)
    
    for match in matches2:
        device_id = match[0]
        fields_str = match[1]
        
        # Parse fields
        field_pattern = r'(\w+):\s*(\w+|true|false|\d+)'
        field_matches = re.findall(field_pattern, fields_str)
        
        for gadget in data["gadgets"]:
            if gadget["id"] == device_id:
                for field_match in field_matches:
                    field = field_match[0]
                    value = field_match[1]
                    
                    # Convert value
                    if value.lower() == 'true':
                        value = True
                    elif value.lower() == 'false':
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    
                    gadget[field] = value
                    modified = True
                    changes_made.append(f"{device_id}.{field} = {value}")
                    print(f"  🔧 Modified {device_id}: {field} = {value}")
    
    # Pattern 3: More lenient - "set light_living state to 2"
    pattern3 = r'set\s+(\w+)\s+(\w+)\s+to\s+(\w+|true|false|\d+)'
    matches3 = re.findall(pattern3, answer, re.IGNORECASE)
    
    for match in matches3:
        device_id = match[0]
        field = match[1]
        value = match[2]
        
        for gadget in data["gadgets"]:
            if gadget["id"] == device_id:
                if value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                elif value.isdigit():
                    value = int(value)
                
                gadget[field] = value
                modified = True
                changes_made.append(f"{device_id}.{field} = {value}")
                print(f"  🔧 Modified {device_id}: {field} = {value}")
    
    if modified:
        save_json(data)
        return True, changes_made
    
    return False, []

try:
    # Load JSON data
    json_data = load_json()
    print(f"Successfully loaded JSON data from {json_path}")
    
    # Convert JSON to documents
    documents = []
    
    # Create detailed documents for each device
    if "gadgets" in json_data:
        for gadget in json_data["gadgets"]:
            content = f"""
Device ID: {gadget['id']}
Type: {gadget['type']}
Room: {gadget['room']}
Full Details: {json.dumps(gadget, indent=2)}

Control Instructions:
"""
            if gadget['type'] == 'light':
                content += f"- To control: Set 'state' to 0 (off), 1 (warm_white), 2 (bright_yellow), or 3 (cool_blue)\n"
                content += f"- Current state: {gadget['state']} ({gadget['color_modes'][gadget['state']]})\n"
            elif gadget['type'] == 'ac':
                content += f"- To control: Set 'on' to true/false, 'temperature' to 18-28\n"
                content += f"- Current: {'ON' if gadget['on'] else 'OFF'} at {gadget['temperature']}°C\n"
            elif gadget['type'] == 'tv':
                content += f"- To control: Set 'channel' to 0 (Off), 1 (News), 2 (Cartoon), 3 (Sports), 4 (Movies)\n"
                content += f"- Current channel: {gadget['channel']} ({gadget['channels'][gadget['channel']]['name']})\n"
            elif gadget['type'] == 'door_lock':
                content += f"- To control: Set 'locked' to true/false\n"
                content += f"- Current: {'Locked' if gadget['locked'] else 'Unlocked'}\n"
            
            doc = Document(page_content=content, metadata={"device_id": gadget["id"]})
            documents.append(doc)
    
    # Add rooms information
    if "rooms" in json_data:
        rooms_content = "Available Rooms:\n"
        for room in json_data["rooms"]:
            rooms_content += f"- {room['name']}\n"
        documents.append(Document(page_content=rooms_content, metadata={"type": "rooms"}))
    
    # Add scenes information
    scenes_doc = Document(page_content="""
Available Scenes and How to Activate Them:

MOVIE SCENE:
- light_living: state = 0 (off)
- tv_living: channel = 4 (Movies)
- ac_living: on = true, temperature = 22

SLEEP SCENE:
- light_living: state = 0 (off)
- light_bedroom: state = 0 (off)
- tv_living: channel = 0 (Off)
- door_bedroom: locked = true

AWAY SCENE (Security):
- light_living: state = 0 (off)
- light_bedroom: state = 0 (off)
- tv_living: channel = 0 (Off)
- ac_living: on = false
- door_bedroom: locked = true

MORNING SCENE:
- light_living: state = 2 (bright_yellow)
- light_bedroom: state = 1 (warm_white)
- tv_living: channel = 1 (News)
- door_bedroom: locked = false

To activate a scene, you need to modify each device listed above with the specified values.
""", metadata={"type": "scenes"})
    documents.append(scenes_doc)
    
    print(f"Created {len(documents)} documents from JSON.")
    
    # Create document chunks
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=1000,
        chunk_overlap=200
    )
    text_chunks = text_splitter.split_documents(documents)
    print(f"Split into {len(text_chunks)} chunks.")
    
    # Create vector embeddings
    print("Creating embeddings (this may take a moment)...")
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={"device": "cuda"})
    knowledge_base = FAISS.from_documents(text_chunks, embeddings)
    print("✅ Knowledge base created successfully!")
    
    # Create QA chain with custom prompt
    prompt_template = """You are a smart home AI assistant. Use the provided context to understand the devices and answer questions.

CRITICAL INSTRUCTIONS - YOU MUST FOLLOW THIS FORMAT:
1. When asked to control devices, you MUST provide modifications in this EXACT format:
   device_id: field = value
   
2. Examples of CORRECT format:
   - light_living: state = 2
   - ac_living: on = true
   - ac_living: temperature = 22
   - tv_living: channel = 4
   - door_bedroom: locked = true

3. For "turn on all lights", respond with:
   light_living: state = 1
   light_bedroom: state = 1

4. For "I want to watch a movie", respond with:
   light_living: state = 0
   tv_living: channel = 4
   ac_living: on = true
   ac_living: temperature = 22

5. Always use the exact device IDs: light_living, light_bedroom, ac_living, tv_living, door_bedroom

Context: {context}

Question: {question}

Answer with the exact device modifications in the format "device_id: field = value":"""

    PROMPT = PromptTemplate(
        template=prompt_template, input_variables=["context", "question"]
    )
    
    qa_chain = RetrievalQA.from_chain_type(
        llm,
        retriever=knowledge_base.as_retriever(search_kwargs={"k": 5}),
        chain_type_kwargs={"prompt": PROMPT}
    )
    
    print("\n" + "="*60)
    print("🏠 Smart Home AI Assistant (Auto-Modifying)")
    print("="*60)
    print("I can help you control your smart home!")
    print("I will AUTOMATICALLY modify devices.json based on your commands!")
    print("\nExamples:")
    print("  - 'turn on all the lights'")
    print("  - 'I want to watch a movie'")
    print("  - 'what would you recommend me to watch'")
    print("  - 'lock all doors'")
    print("  - 'set AC to 24 degrees'")
    print("\nType 'quit' to exit")
    print("="*60)
    
    # Interactive loop
    while True:
        question = input("\n💬 You: ").strip()
        
        if not question:
            continue
            
        if question.lower() in ['quit', 'exit', 'bye', 'goodbye']:
            print("👋 Goodbye!")
            break
        
        print("\n🤖 Assistant: ", end="", flush=True)
        response = qa_chain.invoke({"query": question})
        answer = response['result']
        print(answer)
        
        # Automatically parse and apply changes
        print("\n📝 Analyzing response for device modifications...")
        modified, changes = parse_and_apply_changes(answer)
        
        if modified:
            print(f"\n✅ Applied {len(changes)} changes:")
            for change in changes:
                print(f"   • {change}")
            print("\n💡 Changes are now live in devices.json and will reflect in your Pygame simulation!")
        else:
            print("\n   ℹ️  No device modifications detected in this response.")
        
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON format - {e}")
except Exception as e:
    print(f"Error occurred: {e}")
    import traceback
    traceback.print_exc()