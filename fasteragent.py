import os
import json
import re
from langchain_community.llms import Ollama

# Path to JSON file
json_path = "devices.json"

# Check if file exists
if not os.path.exists(json_path):
    print(f"Error: File '{json_path}' not found.")
    exit(1)

# ⚡ FAST MODEL - Choose one:
# qwen2.5:0.5b (fastest), llama3.2:1b (good balance), or home-3b-v2
llm = Ollama(
    model="fixt/home-3b-v2:latest",  # Change to "qwen2.5:0.5b" for maximum speed
    temperature=0
)

# Preload JSON into memory (only load once!)
devices_cache = None

def load_json():
    """Load the JSON file into memory"""
    global devices_cache
    with open(json_path, 'r', encoding='utf-8') as file:
        devices_cache = json.load(file)
    return devices_cache

def save_json(data):
    """Save data back to JSON file"""
    global devices_cache
    devices_cache = data
    with open(json_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=2)

def create_system_prompt(data):
    """Create Home Assistant format system prompt"""
    devices_list = []
    services = []
    
    for gadget in data["gadgets"]:
        if gadget['type'] == 'light':
            state = "on" if gadget['state'] > 0 else "off"
            mode = gadget['color_modes'][gadget['state']] if gadget['state'] < len(gadget['color_modes']) else "off"
            room_name = gadget['room'].replace('_', ' ').title()
            devices_list.append(f"light.{gadget['id']} '{room_name} Light' = {state};{mode}")
            
        elif gadget['type'] == 'ac':
            state = "on" if gadget['on'] else "off"
            room_name = gadget['room'].replace('_', ' ').title()
            devices_list.append(f"climate.{gadget['id']} '{room_name} AC' = {state};{gadget['temperature']}°C")
            
        elif gadget['type'] == 'tv':
            channel_name = gadget['channels'][gadget['channel']]['name']
            room_name = gadget['room'].replace('_', ' ').title()
            devices_list.append(f"media_player.{gadget['id']} '{room_name} TV' = channel_{gadget['channel']};{channel_name}")
            
        elif gadget['type'] == 'door_lock':
            state = "locked" if gadget['locked'] else "unlocked"
            room_name = gadget['room'].replace('_', ' ').title()
            devices_list.append(f"lock.{gadget['id']} '{room_name} Door Lock' = {state}")
    
    # Define available services
    services = [
        "light.turn_on(state)",
        "light.turn_off()",
        "climate.set_temperature(temperature)",
        "climate.turn_on(temperature)",
        "climate.turn_off()",
        "media_player.select_source(channel)",
        "media_player.turn_on()",
        "media_player.turn_off()",
        "lock.lock()",
        "lock.unlock()"
    ]
    
    system_prompt = f"""You are 'Al', a helpful AI Assistant that controls devices in a house. Complete the task as instructed with the information provided only.

Services: {', '.join(services)}

Devices:
{chr(10).join(devices_list)}

When controlling devices, respond naturally and then output commands in a homeassistant code block:
```homeassistant
{{"service": "light.turn_on", "target_device": "light.light_living", "parameters": {{"state": 2}}}}
```

For multiple devices, you can use "target_devices" with an array:
```homeassistant
{{"service": "light.turn_on", "target_devices": ["light.light_living", "light.light_bedroom"], "parameters": {{"state": 1}}}}
```

Remember:
- Light states: 0=off, 1=warm_white, 2=bright_yellow, 3=cool_blue
- TV channels: 0=Off, 1=News, 2=Cartoon, 3=Sports, 4=Movies
- AC temperature range: 18-28°C"""
    
    return system_prompt

def parse_homeassistant_commands(answer, data):
    """Parse homeassistant code blocks and apply changes using robust regex"""
    modified = False
    changes_made = []
    
    # Pattern 1: Extract homeassistant code blocks (with or without backticks)
    patterns = [
        r'```homeassistant\s*\n(.*?)\n```',  # Standard code block
        r'```json\s*\n(.*?)\n```',            # Sometimes uses json tag
        r'```\s*\n(\{.*?"service".*?\})\n```', # Generic code block with service
        r'(\{.*?"service".*?"target_device.*?\})',  # Raw JSON in text (single device)
        r'(\{.*?"service".*?"target_devices".*?\})', # Raw JSON in text (multiple devices)
    ]
    
    all_matches = []
    for pattern in patterns:
        matches = re.findall(pattern, answer, re.DOTALL | re.IGNORECASE)
        all_matches.extend(matches)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_matches = []
    for match in all_matches:
        match_normalized = match.strip()
        if match_normalized not in seen:
            seen.add(match_normalized)
            unique_matches.append(match_normalized)
    
    for match in unique_matches:
        try:
            # Clean up the JSON
            match = match.strip()
            
            # Try to parse as JSON
            command = json.loads(match)
            
            service = command.get('service', '')
            
            # Handle both single target_device and multiple target_devices
            targets = []
            if 'target_device' in command:
                targets = [command['target_device']]
            elif 'target_devices' in command:
                targets = command['target_devices']
            
            params = command.get('parameters', {})
            
            # Process each target device
            for target in targets:
                # Parse device type and id from target
                if '.' in target:
                    device_type, device_id = target.split('.', 1)
                    
                    # Find the device
                    for gadget in data["gadgets"]:
                        if gadget["id"] == device_id:
                            
                            # Handle light commands
                            if 'light' in service:
                                if 'turn_on' in service:
                                    gadget['state'] = params.get('state', 1)
                                    mode = gadget['color_modes'][gadget['state']]
                                    changes_made.append(f"{device_id}: state = {gadget['state']} ({mode})")
                                    modified = True
                                elif 'turn_off' in service:
                                    gadget['state'] = 0
                                    changes_made.append(f"{device_id}: state = 0 (off)")
                                    modified = True
                            
                            # Handle AC/Climate commands
                            elif 'climate' in service:
                                if 'turn_on' in service or 'set_temperature' in service:
                                    gadget['on'] = True
                                    if 'temperature' in params:
                                        gadget['temperature'] = params['temperature']
                                    changes_made.append(f"{device_id}: on = True, temp = {gadget['temperature']}°C")
                                    modified = True
                                elif 'turn_off' in service:
                                    gadget['on'] = False
                                    changes_made.append(f"{device_id}: on = False")
                                    modified = True
                            
                            # Handle TV/Media Player commands
                            elif 'media_player' in service:
                                if 'select_source' in service or 'turn_on' in service:
                                    if 'channel' in params:
                                        gadget['channel'] = params['channel']
                                    elif gadget['channel'] == 0:  # If TV is off, turn it on to News
                                        gadget['channel'] = 1
                                    channel_name = gadget['channels'][gadget['channel']]['name']
                                    changes_made.append(f"{device_id}: channel = {gadget['channel']} ({channel_name})")
                                    modified = True
                                elif 'turn_off' in service:
                                    gadget['channel'] = 0
                                    changes_made.append(f"{device_id}: channel = 0 (Off)")
                                    modified = True
                            
                            # Handle lock commands
                            elif 'lock' in service:
                                if service == 'lock.lock':
                                    gadget['locked'] = True
                                    changes_made.append(f"{device_id}: locked = True")
                                    modified = True
                                elif service == 'lock.unlock':
                                    gadget['locked'] = False
                                    changes_made.append(f"{device_id}: locked = False")
                                    modified = True
                            
                            break
                        
        except json.JSONDecodeError:
            # If JSON parsing fails, try regex patterns as fallback
            continue
    
    # FALLBACK: Regex-based parsing if JSON parsing didn't work
    if not modified:
        # Pattern for service calls in text format
        service_patterns = [
            # Match: "service": "light.turn_on", "target_device": "light.light_living"
            r'"service"\s*:\s*"([\w.]+)".*?"target_device"\s*:\s*"([\w.]+)"',
            # Match: "service": "light.turn_on", "target_devices": ["light.light_living", ...]
            r'"service"\s*:\s*"([\w.]+)".*?"target_devices"\s*:\s*\[(.*?)\]',
        ]
        
        for pattern in service_patterns:
            matches = re.findall(pattern, answer, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if len(match) == 2:
                    service, target = match[0], match[1]
                    
                    # Handle target_devices array
                    if '[' in target or ',' in target or '"' in target:
                        # Extract device names from array
                        device_names = re.findall(r'"([\w.]+)"', target)
                        targets = device_names
                    else:
                        targets = [target]
                    
                    # Process each target
                    for target in targets:
                        if '.' in target:
                            device_type, device_id = target.split('.', 1)
                            
                            for gadget in data["gadgets"]:
                                if gadget["id"] == device_id:
                                    # Apply changes based on service
                                    if 'light' in service and 'turn_on' in service:
                                        gadget['state'] = 1
                                        changes_made.append(f"{device_id}: state = 1 (warm_white)")
                                        modified = True
                                    elif 'light' in service and 'turn_off' in service:
                                        gadget['state'] = 0
                                        changes_made.append(f"{device_id}: state = 0 (off)")
                                        modified = True
                                    elif 'climate' in service and 'turn_on' in service:
                                        gadget['on'] = True
                                        changes_made.append(f"{device_id}: on = True")
                                        modified = True
                                    elif 'climate' in service and 'turn_off' in service:
                                        gadget['on'] = False
                                        changes_made.append(f"{device_id}: on = False")
                                        modified = True
                                    elif 'media_player' in service and 'turn_on' in service:
                                        gadget['channel'] = 1
                                        changes_made.append(f"{device_id}: channel = 1 (News)")
                                        modified = True
                                    elif 'media_player' in service and 'turn_off' in service:
                                        gadget['channel'] = 0
                                        changes_made.append(f"{device_id}: channel = 0 (Off)")
                                        modified = True
                                    elif 'lock.lock' in service:
                                        gadget['locked'] = True
                                        changes_made.append(f"{device_id}: locked = True")
                                        modified = True
                                    elif 'lock.unlock' in service:
                                        gadget['locked'] = False
                                        changes_made.append(f"{device_id}: locked = False")
                                        modified = True
                                    break
    
    return modified, changes_made

def handle_scenes(question, data):
    """Handle predefined scenes for instant execution"""
    question_lower = question.lower()
    changes_made = []
    
    # Movie scene
    if 'movie' in question_lower or 'watch' in question_lower:
        for gadget in data["gadgets"]:
            if gadget["id"] == "light_living":
                gadget["state"] = 0
                changes_made.append("light_living: state = 0 (off)")
            elif gadget["id"] == "tv_living":
                gadget["channel"] = 4
                changes_made.append("tv_living: channel = 4 (Movies)")
            elif gadget["id"] == "ac_living":
                gadget["on"] = True
                gadget["temperature"] = 22
                changes_made.append("ac_living: on = True, temp = 22°C")
        if changes_made:
            return True, changes_made, "Setting up movie mode for you! 🎬"
    
    # Sleep scene
    if 'sleep' in question_lower or 'bedtime' in question_lower or 'goodnight' in question_lower:
        for gadget in data["gadgets"]:
            if gadget["type"] == "light":
                gadget["state"] = 0
                changes_made.append(f"{gadget['id']}: state = 0 (off)")
            elif gadget["id"] == "tv_living":
                gadget["channel"] = 0
                changes_made.append("tv_living: channel = 0 (Off)")
            elif gadget["id"] == "door_bedroom":
                gadget["locked"] = True
                changes_made.append("door_bedroom: locked = True")
        if changes_made:
            return True, changes_made, "Goodnight! Setting sleep mode. 😴"
    
    # Away/Security scene
    if 'away' in question_lower or 'leave' in question_lower or 'security' in question_lower:
        for gadget in data["gadgets"]:
            if gadget["type"] == "light":
                gadget["state"] = 0
                changes_made.append(f"{gadget['id']}: state = 0 (off)")
            elif gadget["type"] == "tv":
                gadget["channel"] = 0
                changes_made.append(f"{gadget['id']}: channel = 0 (Off)")
            elif gadget["type"] == "ac":
                gadget["on"] = False
                changes_made.append(f"{gadget['id']}: on = False")
            elif gadget["type"] == "door_lock":
                gadget["locked"] = True
                changes_made.append(f"{gadget['id']}: locked = True")
        if changes_made:
            return True, changes_made, "Activating security mode. All devices secured. 🔒"
    
    # Morning scene
    if 'morning' in question_lower or 'wake up' in question_lower:
        for gadget in data["gadgets"]:
            if gadget["id"] == "light_living":
                gadget["state"] = 2
                changes_made.append("light_living: state = 2 (bright_yellow)")
            elif gadget["id"] == "light_bedroom":
                gadget["state"] = 1
                changes_made.append("light_bedroom: state = 1 (warm_white)")
            elif gadget["id"] == "tv_living":
                gadget["channel"] = 1
                changes_made.append("tv_living: channel = 1 (News)")
            elif gadget["id"] == "door_bedroom":
                gadget["locked"] = False
                changes_made.append("door_bedroom: locked = False")
        if changes_made:
            return True, changes_made, "Good morning! Starting your day. ☀️"
    
    return False, [], ""

def home_agent_main(data, question):
    """Main function for the Ultra-Fast Smart Home Assistant"""
    system_prompt = create_system_prompt(data)
    full_prompt = f"{system_prompt}\n\nUser: {question}\nAssistant:"
    
    # Get LLM response (⚡ FAST!)
    answer = llm.invoke(full_prompt)
    print(answer)
    
    # Parse and apply changes
    modified, changes = parse_homeassistant_commands(answer, data)
    return modified, changes, answer

# try:
#     # Load JSON ONCE into memory
#     print("Loading devices...")
#     data = load_json()
#     print(f"✅ Loaded {len(data['gadgets'])} devices")
    
#     print("\n" + "="*60)
#     print("🏠 Ultra-Fast Smart Home Assistant (Home Assistant Format)")
#     print("="*60)
#     print(f"⚡ Model: {llm.model}")
#     print("⚡ Optimized for 1-2 second responses")
#     print("⚡ Home Assistant compatible services")
#     print("\nExamples:")
#     print("  - 'turn on all lights'")
#     print("  - 'I want to watch a movie'")
#     print("  - 'set AC to 24 degrees'")
#     print("  - 'lock all doors'")
#     print("  - 'goodnight' (sleep scene)")
#     print("\nType 'quit' to exit")
#     print("="*60)
    
#     # Interactive loop
#     while True:
#         question = input("\n💬 You: ").strip()
        
#         if not question:
#             continue
            
#         if question.lower() in ['quit', 'exit', 'bye', 'goodbye']:
#             print("👋 Goodbye!")
#             break
        
#         # Check for instant scene activation (no LLM needed!)
#         # is_scene, scene_changes, scene_msg = handle_scenes(question, data)
#         # if is_scene:
#         #     print(f"\n🤖 Assistant: {scene_msg}")
#         #     save_json(data)
#         #     print(f"\n✅ Applied {len(scene_changes)} changes:")
#         #     for change in scene_changes:
#         #         print(f"   • {change}")
#         #     continue
        
#         # Otherwise, use LLM
#         print("\n🤖 Assistant: ", end="", flush=True)
        
#         # Create prompt with current device states
#         modified, changes, answer = home_agent_main(data, question)
        
#         if modified:
#             save_json(data)
#             print(f"\n✅ Applied {len(changes)} changes:")
#             for change in changes:
#                 print(f"   • {change}")
#             print("\n💡 Changes saved to devices.json!")
#         else:
#             print("\n   ℹ️  No device modifications detected.")
        
# except json.JSONDecodeError as e:
#     print(f"Error: Invalid JSON format - {e}")
# except Exception as e:
#     print(f"Error occurred: {e}")
#     import traceback
#     traceback.print_exc()