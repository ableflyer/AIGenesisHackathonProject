import os
import json
import re
from langchain_community.llms import Ollama

# Path to JSON file
json_path = "devices.json"

class HomeAgent:
    def __init__(self):
        # Check if file exists
        if not os.path.exists(json_path):
            print(f"Error: File '{json_path}' not found.")
        
        # ⚡ FAST MODEL initialization
        # Suggest qwen2.5:0.5b for real-time game performance
        self.llm = Ollama(
            model="fixt/home-3b-v2:latest", 
            temperature=0
        )
        self.devices_cache = None

    def load_json(self):
        """Load the JSON file into memory"""
        with open(json_path, 'r', encoding='utf-8') as file:
            self.devices_cache = json.load(file)
        return self.devices_cache

    def save_json(self, data):
        """Save data back to JSON file"""
        self.devices_cache = data
        with open(json_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2)

    def create_system_prompt(self, data):
        """Create Home Assistant format system prompt"""
        devices_list = []
        
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
        
        services = [
            "light.turn_on(state)", "light.turn_off()",
            "climate.set_temperature(temp)", "climate.turn_on()", "climate.turn_off()",
            "media_player.select_source(ch)", "media_player.turn_on()", "media_player.turn_off()",
            "lock.lock()", "lock.unlock()"
        ]
        
        system_prompt = f"""You are 'Al', a helpful AI Assistant that controls devices in a house.
Services: {', '.join(services)}
Devices:
{chr(10).join(devices_list)}

Respond nicely, then use homeassistant code blocks:
```homeassistant
{{"service": "light.turn_on", "target_device": "light.light_living", "parameters": {{"state": 2}}}}
Light states: 0=off, 1=warm, 2=yellow, 3=blue. TV: 0=Off, 1=News, 2=Cartoon, 3=Sports, 4=Movies."""
        return system_prompt
    
    def parse_homeassistant_commands(self, answer, data):
        """Parse output and apply changes"""
        modified = False
        changes_made = []
        
        # Simple regex for JSON extraction for speed
        patterns = [r'```homeassistant\s*\n(.*?)\n```', r'(\{.*?"service".*?\})']
        
        all_matches = []
        for pattern in patterns:
            matches = re.findall(pattern, answer, re.DOTALL | re.IGNORECASE)
            all_matches.extend(matches)
        
        for match in all_matches:
            try:
                command = json.loads(match.strip())
                service = command.get('service', '')
                
                targets = []
                if 'target_device' in command: targets = [command['target_device']]
                elif 'target_devices' in command: targets = command['target_devices']
                
                params = command.get('parameters', {})
                
                for target in targets:
                    if '.' in target:
                        _, device_id = target.split('.', 1)
                        for gadget in data["gadgets"]:
                            if gadget["id"] == device_id:
                                # (Logic condensed for brevity, same logic as original)
                                if 'light' in service:
                                    if 'turn_on' in service:
                                        gadget['state'] = params.get('state', 1)
                                        modified = True
                                    elif 'turn_off' in service:
                                        gadget['state'] = 0
                                        modified = True
                                elif 'climate' in service:
                                    if 'turn_on' in service:
                                        gadget['on'] = True
                                        if 'temperature' in params: gadget['temperature'] = params['temperature']
                                        modified = True
                                    elif 'turn_off' in service:
                                        gadget['on'] = False
                                        modified = True
                                elif 'media_player' in service:
                                    if 'turn_on' in service or 'select_source' in service:
                                        if 'channel' in params: gadget['channel'] = params['channel']
                                        elif gadget['channel'] == 0: gadget['channel'] = 1
                                        modified = True
                                    elif 'turn_off' in service:
                                        gadget['channel'] = 0
                                        modified = True
                                elif 'lock' in service:
                                    if 'lock.lock' in service:
                                        gadget['locked'] = True
                                        modified = True
                                    elif 'lock.unlock' in service:
                                        gadget['locked'] = False
                                        modified = True
                                break
            except: continue
            
        return modified, changes_made

    def handle_scenes(self, question, data):
        """Quick logic for common scenes"""
        q = question.lower()
        mod = False
        msg = ""
        
        if 'movie' in q:
            for g in data['gadgets']:
                if g['id'] == 'light_living': g['state'] = 0
                if g['id'] == 'tv_living': g['channel'] = 4
            mod, msg = True, "Movie mode activated! 🎬"
            
        elif 'sleep' in q or 'goodnight' in q:
            for g in data['gadgets']:
                if g['type'] == 'light': g['state'] = 0
                if g['type'] == 'tv': g['channel'] = 0
                if g['id'] == 'door_bedroom': g['locked'] = True
            mod, msg = True, "Goodnight! House secured. 😴"
            
        elif 'morning' in q:
            for g in data['gadgets']:
                if g['id'] == 'light_living': g['state'] = 2
                if g['id'] == 'tv_living': g['channel'] = 1
            mod, msg = True, "Good morning! ☀️"
            
        return mod, [], msg

    def process_command(self, question):
        """Main entry point for external scripts"""
        data = self.load_json()
        
        # 1. Check scenes first
        is_scene, _, msg = self.handle_scenes(question, data)
        if is_scene:
            self.save_json(data)
            return msg

        # 2. Use LLM
        system_prompt = self.create_system_prompt(data)
        full_prompt = f"{system_prompt}\n\nUser: {question}\nAssistant:"
        
        try:
            answer = self.llm.invoke(full_prompt)
            modified, _ = self.parse_homeassistant_commands(answer, data)
            
            if modified:
                self.save_json(data)
                # Extract just the text part for the user
                text_response = answer.split("```")[0].strip()
                return text_response if text_response else "Devices updated."
            else:
                return answer.split("```")[0].strip()
        except Exception as e:
            return f"Error: {str(e)}"

if __name__ == "__main__":
    agent = HomeAgent()
    print("🤖 Agent Ready (Terminal Mode). Type 'quit' to exit.")
    while True:
        q = input("You: ")
        if q.lower() == "quit":
            break
        print("Agent:", agent.process_command(q))