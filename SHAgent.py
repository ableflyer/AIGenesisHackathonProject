import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass
from enum import Enum

from langchain_community.llms import Ollama
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import re
import asyncio

# Device Types and States
class DeviceType(Enum):
    LIGHT = "light"
    THERMOSTAT = "thermostat"
    LOCK = "lock"
    CAMERA = "camera"
    SPEAKER = "speaker"
    BLIND = "blind"
    FAN = "fan"
    OUTLET = "outlet"

class DeviceState(Enum):
    ON = "on"
    OFF = "off"
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    OPEN = "open"
    CLOSED = "closed"

@dataclass
class CommandHistory:
    timestamp: datetime
    command: str
    devices_affected: List[str]
    action: str
    success: bool

class SmartHomeController:
    """Main controller for smart home devices"""
    
    def __init__(self, devices_config: Dict):
        self.devices = devices_config
        self.command_history: List[CommandHistory] = []
        
    def get_device(self, device_id: str) -> Optional[Dict]:
        """Get device by ID"""
        return self.devices.get(device_id)
    
    def get_devices_by_room(self, room: str) -> List[Dict]:
        """Get all devices in a specific room"""
        return [d for d in self.devices.values() if d['location']['room'].lower() == room.lower()]
    
    def get_devices_by_type(self, device_type: str) -> List[Dict]:
        """Get all devices of a specific type"""
        return [d for d in self.devices.values() if d['type'] == device_type]
    
    def update_device_state(self, device_id: str, new_state: Dict) -> bool:
        """Update device state"""
        if device_id in self.devices:
            self.devices[device_id]['state'].update(new_state)
            self.devices[device_id]['last_updated'] = datetime.now().isoformat()
            return True
        return False
    
    def log_command(self, command: str, devices: List[str], action: str, success: bool):
        """Log command to history"""
        self.command_history.append(
            CommandHistory(
                timestamp=datetime.now(),
                command=command,
                devices_affected=devices,
                action=action,
                success=success
            )
        )

# Tools for LangGraph
@tool
def control_lights(room: str, action: Literal["on", "off"], controller: SmartHomeController) -> str:
    """Control lights in a specific room"""
    devices = controller.get_devices_by_room(room)
    lights = [d for d in devices if d['type'] == DeviceType.LIGHT.value]
    
    if not lights:
        return f"No lights found in {room}"
    
    affected_devices = []
    for light in lights:
        new_state = {"power": action, "status": action}
        if controller.update_device_state(light['id'], new_state):
            affected_devices.append(light['id'])
    
    controller.log_command(
        f"Turn {action} lights in {room}",
        affected_devices,
        action,
        len(affected_devices) > 0
    )
    
    return f"Turned {action} {len(affected_devices)} lights in {room}"

@tool
def set_thermostat(room: str, temperature: float, controller: SmartHomeController) -> str:
    """Set thermostat temperature in a room"""
    devices = controller.get_devices_by_room(room)
    thermostats = [d for d in devices if d['type'] == DeviceType.THERMOSTAT.value]
    
    if not thermostats:
        return f"No thermostat found in {room}"
    
    thermostat = thermostats[0]
    new_state = {"target_temperature": temperature, "status": "on"}
    
    if controller.update_device_state(thermostat['id'], new_state):
        controller.log_command(
            f"Set thermostat in {room} to {temperature}",
            [thermostat['id']],
            f"set_temperature_{temperature}",
            True
        )
        return f"Set thermostat in {room} to {temperature}°C"
    
    return f"Failed to set thermostat in {room}"

@tool
def control_device(device_id: str, action: Dict, controller: SmartHomeController) -> str:
    """Control a specific device by ID"""
    device = controller.get_device(device_id)
    if not device:
        return f"Device {device_id} not found"
    
    if controller.update_device_state(device_id, action):
        controller.log_command(
            f"Control device {device_id}",
            [device_id],
            str(action),
            True
        )
        return f"Successfully updated {device['name']}"
    
    return f"Failed to update {device['name']}"

@tool
def get_room_status(room: str, controller: SmartHomeController) -> str:
    """Get status of all devices in a room"""
    devices = controller.get_devices_by_room(room)
    if not devices:
        return f"No devices found in {room}"
    
    status = f"Status of devices in {room}:\n"
    for device in devices:
        status += f"- {device['name']} ({device['type']}): {device['state']}\n"
    
    return status

from tools import build_tools


class SmartHomeAgent:
    """Main AI agent for smart home control.

    Provides hybrid intent understanding (LLM first, rule-based fallback) and
    exposes last_intent / last_results for UI layers (e.g., pygame demo).
    """
    
    def __init__(self, controller: SmartHomeController, model_name: str = "gemma3:latest", use_llm: bool = True):
        self.controller = controller
        self.use_llm = use_llm
        self.llm = Ollama(model=model_name, temperature=0.3) if use_llm else None
        self.memory = ConversationBufferMemory(return_messages=True)
        self.last_intent: Optional[Dict[str, Any]] = None
        self.last_results: List[str] = []
        self.last_response: Optional[str] = None
        
        # Build tool set and tool-using agent (ReAct)
        self.tools = build_tools(self.controller)
        if self.llm is not None:
            # Local ReAct-style prompt to avoid network dependency
            react_prompt = ChatPromptTemplate.from_messages([
                (
                    "system",
                    (
                        "You are a smart home assistant. You can use tools to control devices, retrieve room/device status, and make changes.\n"
                        "Use the following tools when helpful.\n\n"
                        "TOOLS AVAILABLE:\n{tools}\n\n"
                        "When you need to use a tool, follow EXACTLY this format:\n"
                        "Question: {input}\n"
                        "Thought: you should always think about what to do\n"
                        "Action: one of [{tool_names}]\n"
                        "Action Input: the input to the action\n"
                        "Observation: the result of the action\n"
                        "... (this Thought/Action/Action Input/Observation can repeat N times) ...\n"
                        "Thought: I now know the final answer\n"
                        "Final Answer: a concise answer for the user.\n"
                    ),
                ),
                ("human", "Question: {input}\nIf the user asks to control 'all lights' without a specific room, call control_lights with room='all'."),
                ("assistant", "{agent_scratchpad}"),
            ])
            self.agent = create_react_agent(self.llm, self.tools, react_prompt)
            self.agent_executor = AgentExecutor(
                agent=self.agent,
                tools=self.tools,
                verbose=False,
                handle_parsing_errors=True,
                max_iterations=6,
            )
        else:
            self.agent = None
            self.agent_executor = None

        # Build the LangGraph workflow (simplified: parse->execute->respond)
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(dict)
        
        # Define nodes
        workflow.add_node("parse_intent", self.parse_intent)
        workflow.add_node("execute_action", self.execute_action)
        workflow.add_node("learn_pattern", self.learn_from_history)
        workflow.add_node("respond", self.generate_response)
        
        # Define edges
        workflow.add_edge("parse_intent", "execute_action")
        workflow.add_edge("execute_action", "learn_pattern")
        workflow.add_edge("learn_pattern", "respond")
        workflow.add_edge("respond", END)
        
        # Set entry point
        workflow.set_entry_point("parse_intent")
        
        return workflow.compile()
    
    async def parse_intent(self, state: Dict) -> Dict:
        """For tool-using mode, the 'intent' is the natural language command itself."""
        state["intent"] = {"action": "tool_agent", "parameters": {"command": state.get("command", "")}}
        self.last_intent = state["intent"]
        return state

    def _available_rooms(self) -> List[str]:
        rooms = sorted({v["location"]["room"] for v in self.controller.devices.values()})
        return rooms

    def _normalize_room(self, text: str) -> Optional[str]:
        if not text:
            return None
        t = text.strip().lower()
        # Remove common fillers
        t = re.sub(r"\b(the|all|devices|in|on|of|room|rooms)\b", "", t).strip()
        # Normalize spaces/underscores
        t = re.sub(r"\s+", " ", t)
        candidates = [t, t.replace(" ", "_"), t.replace("_", " ")]
        # Common synonyms
        synonyms = {
            "living room": "living_room",
            "master bedroom": "master_bedroom",
            "bedroom": "master_bedroom",
        }
        for k, v in list(synonyms.items()):
            candidates.extend([k, v])
        available = self._available_rooms()
        for cand in candidates:
            cand_norm = cand.replace(" ", "_")
            if cand_norm in available:
                return cand_norm
        # partial match
        for room in available:
            if room.replace("_", " ") in t or t in room.replace("_", " "):
                return room
        return None

    def _extract_json_object(self, text: str) -> Optional[str]:
        # Extract the first top-level JSON object from text
        start = None
        depth = 0
        for i, ch in enumerate(text):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    return text[start:i+1]
        return None

    def _rule_based_intent(self, command: str) -> Dict[str, Any]:
        c = command.lower()
        # ---------------------------------
        # Temperature (absolute set) intent
        # ---------------------------------
        temp_match = re.search(r"(?:set|adjust|change).{0,40}temp(?:erature)?\s*(?:to|at)?\s*(\d+(?:\.\d+)?)", c)
        if temp_match:
            temp = float(temp_match.group(1))
            room_match = re.search(r"(living\s*room|master\s*bedroom|bedroom|kitchen|entrance|garage)", c)
            room = self._normalize_room(room_match.group(1)) if room_match else None
            return {
                "action": "set_temperature",
                "targets": [],
                "parameters": {"room": room or "living_room", "temperature": temp}
            }

        # ---------------------------------
        # Temperature relative adjustments (increase/decrease/raise/lower/warmer/cooler)
        # ---------------------------------
        rel_match = re.search(r"(increase|decrease|raise|lower|warmer|cooler).{0,20}temp(?:erature)?(?:\s+by\s+(\d+(?:\.\d+)?))?", c)
        if rel_match:
            direction = rel_match.group(1)
            delta_str = rel_match.group(2)
            delta = float(delta_str) if delta_str else 1.0
            if direction in ["decrease", "lower", "cooler"]:
                delta = -delta
            room_match = re.search(r"(living\s*room|master\s*bedroom|bedroom|kitchen|entrance|garage)", c)
            room = self._normalize_room(room_match.group(1)) if room_match else "living_room"
            return {
                "action": "adjust_temperature",
                "targets": [],
                "parameters": {"room": room, "delta": delta}
            }

        # ---------------------------------
        # Lock / Unlock intent
        # ---------------------------------
        if re.search(r"\bunlock\b", c):
            # optional specific door
            door_spec = re.search(r"front\s+door", c)
            scope = "front" if door_spec else "all"
            return {
                "action": "unlock",
                "targets": ["lock_front_door"] if scope == "front" else [],  # empty means all locks
                "parameters": {"scope": scope}
            }
        if re.search(r"\block\b", c) and not re.search(r"unlock", c):
            door_spec = re.search(r"front\s+door", c)
            scope = "front" if door_spec else "all"
            return {
                "action": "lock",
                "targets": ["lock_front_door"] if scope == "front" else [],
                "parameters": {"scope": scope}
            }
        # Lights on/off
        light_on = re.search(r"((?:turn|switch)\s+on|lights?\s+on)", c)
        light_off = re.search(r"((?:turn|switch)\s+off|lights?\s+off)", c)
        if ("light" in c or "lights" in c) and (light_on or light_off):
            action = "light_on" if light_on else "light_off"
            room_match = re.search(r"in\s+the\s+([a-z_\s]+)$|in\s+([a-z_\s]+)$", c)
            room_text = room_match.group(1) if room_match and room_match.group(1) else (room_match.group(2) if room_match else None)
            # also check common rooms in text
            if not room_text:
                room_name_match = re.search(r"(living\s*room|master\s*bedroom|bedroom|kitchen|entrance|garage)", c)
                room_text = room_name_match.group(1) if room_name_match else None
            room = self._normalize_room(room_text or "") or "kitchen"
            return {"action": action, "targets": [], "parameters": {"room": room}}
        # Status
        if any(k in c for k in ["status", "what's", "what is", "show"]):
            room_match = re.search(r"(living\s*room|master\s*bedroom|bedroom|kitchen|entrance|garage)", c)
            room = self._normalize_room(room_match.group(1)) if room_match else None
            targets = [room] if room else []
            return {"action": "status", "targets": targets, "parameters": {}}
        # Generic warmer/cooler fallback (no explicit word temperature)
        if re.search(r"\bwarmer\b", c):
            room_match = re.search(r"(living\s*room|master\s*bedroom|bedroom|kitchen|entrance|garage)", c)
            room = self._normalize_room(room_match.group(1)) if room_match else "living_room"
            return {"action": "adjust_temperature", "targets": [], "parameters": {"room": room, "delta": 1.0}}
        if re.search(r"\bcooler\b", c):
            room_match = re.search(r"(living\s*room|master\s*bedroom|bedroom|kitchen|entrance|garage)", c)
            room = self._normalize_room(room_match.group(1)) if room_match else "living_room"
            return {"action": "adjust_temperature", "targets": [], "parameters": {"room": room, "delta": -1.0}}
        # Unknown
        return {"action": "unknown", "targets": [], "parameters": {}}
    
    async def execute_action(self, state: Dict) -> Dict:
        """Execute the identified action"""
        intent = state.get("intent", {})
        action = intent.get("action", "")
        results: List[str] = []

        if action == "tool_agent" and self.agent_executor is not None:
            command = intent.get("parameters", {}).get("command", "")
            try:
                outcome = await self.agent_executor.ainvoke({"input": command})
                final = outcome.get("output") if isinstance(outcome, dict) else str(outcome)
                if final:
                    results.append(final)
            except Exception as e:
                # Graceful fallback: try answering directly with the LLM (no tools)
                err = str(e)
                try:
                    if self.llm is not None:
                        fallback = self.llm.invoke(
                            f"You are a smart home assistant. Answer the user's request concisely. If you cannot act on devices due to a planning error, still provide a helpful response.\n\nUser: {command}"
                        )
                        # Some LLMs return str, others return objects with .content
                        text = getattr(fallback, "content", None) or str(fallback)
                        results.append(text)
                    else:
                        results.append("I'm unable to process this right now.")
                except Exception:
                    # If fallback fails, surface a friendly error
                    friendly = "Sorry, I hit a parsing hiccup. Please rephrase or try again."
                    results.append(friendly)
        else:
            results.append("No agent available to handle the request.")

        state["results"] = results
        self.last_results = results
        return state
    
    async def learn_from_history(self, state: Dict) -> Dict:
        """Learn patterns from command history"""
        # Analyze patterns in command history
        if len(self.controller.command_history) > 10:
            # Find common command sequences
            recent_commands = self.controller.command_history[-20:]
            
            # Simple pattern detection (can be enhanced with ML)
            time_patterns = {}
            for cmd in recent_commands:
                hour = cmd.timestamp.hour
                if hour not in time_patterns:
                    time_patterns[hour] = []
                time_patterns[hour].append(cmd.command)
            
            # Store learned patterns
            state["learned_patterns"] = time_patterns
        
        return state
    
    async def generate_response(self, state: Dict) -> Dict:
        """Generate final response to user"""
        results = state.get("results", [])
        
        if results:
            response = "\n".join(results)
        else:
            response = "I couldn't understand that command. Please try again."
        
        # Add to memory
        self.memory.chat_memory.add_user_message(state.get("command", ""))
        self.memory.chat_memory.add_ai_message(response)
        
        state["response"] = response
        self.last_response = response
        return state
    
    async def process_command(self, command: str) -> str:
        """Process a user command"""
        initial_state = {"command": command}
        result = await self.workflow.ainvoke(initial_state)
        return result.get("response", "Error processing command")

    def process_command_sync(self, command: str) -> str:
        """Synchronous helper for environments (like pygame) without async loop."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In rare embedded cases, schedule task
                return asyncio.run(self.process_command(command))  # Fallback (may raise)
        except RuntimeError:
            # No loop
            pass
        return asyncio.run(self.process_command(command))

# Example usage
async def main():
    # Load devices configuration
    with open('smart_devices.json', 'r') as f:
        devices_config = json.load(f)
    
    # Initialize controller and agent
    controller = SmartHomeController(devices_config)
    agent = SmartHomeAgent(controller, model_name="gemma3:latest")
    
    # Example commands
    commands = [
        "Turn off all lights in the kitchen",
        "Set living room temperature to 22 degrees",
        "What's the status of bedroom devices?",
        "Turn on the lights in the master bedroom"
    ]
    
    for cmd in commands:
        print(f"\nCommand: {cmd}")
        response = await agent.process_command(cmd)
        print(f"Response: {response}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())