import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import random

class SmartHomeTools:
    """Tools for smart home device control and virtual assistant capabilities"""
    
    def __init__(self, devices_path: str = "devices.json"):
        self.devices_path = devices_path
        self.load_devices()
    
    def load_devices(self):
        """Load device data from JSON"""
        with open(self.devices_path, "r") as f:
            self.data = json.load(f)
        self.gadgets = {g["id"]: g for g in self.data["gadgets"]}
        self.rooms = {r["name"]: r for r in self.data["rooms"]}
    
    def save_devices(self):
        """Save device data to JSON"""
        self.data["gadgets"] = list(self.gadgets.values())
        with open(self.devices_path, "w") as f:
            json.dump(self.data, f, indent=2)
    
    # ========== DEVICE CONTROL TOOLS ==========
    
    def get_all_devices(self) -> str:
        """Get a list of all smart home devices and their current states"""
        self.load_devices()
        device_list = []
        for gid, g in self.gadgets.items():
            status = self._get_device_status(g)
            device_list.append(f"- {gid} ({g['type']} in {g['room']}): {status}")
        return "\n".join(device_list)
    
    def _get_device_status(self, device: Dict) -> str:
        """Get human-readable status of a device"""
        if device["type"] == "light":
            return f"{device['color_modes'][device['state']]}"
        elif device["type"] == "ac":
            return f"{'ON' if device['on'] else 'OFF'}, {device['temperature']}°C"
        elif device["type"] == "tv":
            ch = device["channels"][device["channel"]]
            return f"Channel {ch['id']}: {ch['name']}"
        elif device["type"] == "door_lock":
            return f"{'Locked' if device['locked'] else 'Unlocked'}"
        return "unknown"
    
    def control_light(self, device_id: str, mode: str) -> str:
        """
        Control a light device
        Args:
            device_id: ID of the light (e.g., 'light_living', 'light_bedroom')
            mode: one of 'off', 'warm_white', 'bright_yellow', 'cool_blue'
        """
        self.load_devices()
        if device_id not in self.gadgets:
            return f"Device {device_id} not found"
        
        device = self.gadgets[device_id]
        if device["type"] != "light":
            return f"{device_id} is not a light"
        
        if mode not in device["color_modes"]:
            return f"Invalid mode. Available: {', '.join(device['color_modes'])}"
        
        device["state"] = device["color_modes"].index(mode)
        self.save_devices()
        return f"Set {device_id} to {mode}"
    
    def control_ac(self, device_id: str, power: str, temperature: Optional[int] = None) -> str:
        """
        Control an AC device
        Args:
            device_id: ID of the AC (e.g., 'ac_living')
            power: 'on' or 'off'
            temperature: Temperature to set (18-28), optional
        """
        self.load_devices()
        if device_id not in self.gadgets:
            return f"Device {device_id} not found"
        
        device = self.gadgets[device_id]
        if device["type"] != "ac":
            return f"{device_id} is not an AC"
        
        device["on"] = power.lower() == "on"
        
        if temperature is not None:
            min_temp, max_temp = device["range"]
            if min_temp <= temperature <= max_temp:
                device["temperature"] = temperature
            else:
                return f"Temperature must be between {min_temp}°C and {max_temp}°C"
        
        self.save_devices()
        status = f"{'ON' if device['on'] else 'OFF'}"
        if device["on"] and temperature:
            status += f" at {temperature}°C"
        return f"Set {device_id} to {status}"
    
    def control_tv(self, device_id: str, channel: str) -> str:
        """
        Control a TV device
        Args:
            device_id: ID of the TV (e.g., 'tv_living')
            channel: Channel name ('Off', 'News', 'Cartoon', 'Sports', 'Movies')
        """
        self.load_devices()
        if device_id not in self.gadgets:
            return f"Device {device_id} not found"
        
        device = self.gadgets[device_id]
        if device["type"] != "tv":
            return f"{device_id} is not a TV"
        
        channels = {ch["name"].lower(): ch["id"] for ch in device["channels"]}
        channel_lower = channel.lower()
        
        if channel_lower not in channels:
            available = ", ".join([ch["name"] for ch in device["channels"]])
            return f"Invalid channel. Available: {available}"
        
        device["channel"] = channels[channel_lower]
        self.save_devices()
        return f"Set {device_id} to channel: {channel}"
    
    def control_door_lock(self, device_id: str, action: str) -> str:
        """
        Control a door lock
        Args:
            device_id: ID of the door lock (e.g., 'door_bedroom')
            action: 'lock' or 'unlock'
        """
        self.load_devices()
        if device_id not in self.gadgets:
            return f"Device {device_id} not found"
        
        device = self.gadgets[device_id]
        if device["type"] != "door_lock":
            return f"{device_id} is not a door lock"
        
        device["locked"] = action.lower() == "lock"
        self.save_devices()
        return f"{device_id} is now {'locked' if device['locked'] else 'unlocked'}"
    
    # ========== VIRTUAL ASSISTANT TOOLS ==========
    
    def get_time(self) -> str:
        """Get current time"""
        now = datetime.now()
        return f"Current time: {now.strftime('%I:%M %p')}"
    
    def get_date(self) -> str:
        """Get current date"""
        now = datetime.now()
        return f"Today is {now.strftime('%A, %B %d, %Y')}"
    
    def get_weather(self, location: str = "Dubai") -> str:
        """
        Get weather information (simulated)
        Args:
            location: City name
        """
        # Simulated weather data
        conditions = ["Sunny", "Partly Cloudy", "Cloudy", "Hot"]
        temp = random.randint(25, 42)
        condition = random.choice(conditions)
        return f"Weather in {location}: {condition}, {temp}°C"
    
    def set_timer(self, duration_minutes: int, label: str = "Timer") -> str:
        """
        Set a timer (simulated)
        Args:
            duration_minutes: Duration in minutes
            label: Optional label for the timer
        """
        return f"Timer set: {label} for {duration_minutes} minutes"
    
    def set_reminder(self, message: str, time: str) -> str:
        """
        Set a reminder (simulated)
        Args:
            message: Reminder message
            time: Time for reminder (e.g., '3:00 PM')
        """
        return f"Reminder set: '{message}' at {time}"
    
    def play_music(self, song_or_artist: str) -> str:
        """
        Play music (simulated)
        Args:
            song_or_artist: Song name or artist name
        """
        return f"Now playing: {song_or_artist}"
    
    def search_web(self, query: str) -> str:
        """
        Search the web (simulated)
        Args:
            query: Search query
        """
        return f"Searching for: {query}. Here are some results... (simulated)"
    
    def calculate(self, expression: str) -> str:
        """
        Perform calculations
        Args:
            expression: Mathematical expression (e.g., '25 * 4')
        """
        try:
            result = eval(expression)
            return f"{expression} = {result}"
        except Exception as e:
            return f"Error calculating: {str(e)}"
    
    # ========== AWARENESS/CONTEXT TOOLS ==========
    
    def get_room_status(self, room_name: str) -> str:
        """
        Get status of all devices in a specific room
        Args:
            room_name: Name of the room ('living' or 'bedroom')
        """
        self.load_devices()
        if room_name not in self.rooms:
            return f"Room '{room_name}' not found. Available: {', '.join(self.rooms.keys())}"
        
        room_devices = [g for g in self.gadgets.values() if g["room"] == room_name]
        if not room_devices:
            return f"No devices found in {room_name}"
        
        status_list = [f"- {g['id']}: {self._get_device_status(g)}" for g in room_devices]
        return f"Status of {room_name}:\n" + "\n".join(status_list)
    
    def get_energy_usage(self) -> str:
        """Get estimated energy usage of active devices (simulated)"""
        self.load_devices()
        active_devices = []
        total_watts = 0
        
        for g in self.gadgets.values():
            if g["type"] == "light" and g["state"] != 0:
                active_devices.append(f"{g['id']}: ~10W")
                total_watts += 10
            elif g["type"] == "ac" and g["on"]:
                active_devices.append(f"{g['id']}: ~1500W")
                total_watts += 1500
            elif g["type"] == "tv" and g["channel"] != 0:
                active_devices.append(f"{g['id']}: ~100W")
                total_watts += 100
        
        if not active_devices:
            return "No devices currently consuming energy"
        
        return f"Active devices:\n" + "\n".join(active_devices) + f"\n\nTotal: ~{total_watts}W"
    
    def get_security_status(self) -> str:
        """Get security status (door locks)"""
        self.load_devices()
        locks = [g for g in self.gadgets.values() if g["type"] == "door_lock"]
        
        if not locks:
            return "No door locks found"
        
        status_list = []
        all_locked = True
        for lock in locks:
            status = "🔒 Locked" if lock["locked"] else "🔓 Unlocked"
            status_list.append(f"{lock['id']}: {status}")
            if not lock["locked"]:
                all_locked = False
        
        security_level = "Secure - all doors locked" if all_locked else "Warning - some doors unlocked"
        return f"{security_level}\n" + "\n".join(status_list)
    
    def create_scene(self, scene_name: str) -> str:
        """
        Create/activate predefined scenes
        Args:
            scene_name: Scene name ('movie', 'sleep', 'away', 'morning')
        """
        self.load_devices()
        
        scenes = {
            "movie": {
                "description": "Movie night mode",
                "actions": [
                    ("light_living", {"state": 0}),  # Lights off
                    ("tv_living", {"channel": 4}),  # Movies channel
                    ("ac_living", {"on": True, "temperature": 22})
                ]
            },
            "sleep": {
                "description": "Sleep mode",
                "actions": [
                    ("light_living", {"state": 0}),
                    ("light_bedroom", {"state": 0}),
                    ("tv_living", {"channel": 0}),
                    ("door_bedroom", {"locked": True})
                ]
            },
            "away": {
                "description": "Away mode - secure home",
                "actions": [
                    ("light_living", {"state": 0}),
                    ("light_bedroom", {"state": 0}),
                    ("tv_living", {"channel": 0}),
                    ("ac_living", {"on": False}),
                    ("door_bedroom", {"locked": True})
                ]
            },
            "morning": {
                "description": "Morning mode",
                "actions": [
                    ("light_living", {"state": 2}),  # Bright yellow
                    ("light_bedroom", {"state": 1}),  # Warm white
                    ("tv_living", {"channel": 1}),  # News
                    ("door_bedroom", {"locked": False})
                ]
            }
        }
        
        if scene_name.lower() not in scenes:
            available = ", ".join(scenes.keys())
            return f"Scene '{scene_name}' not found. Available: {available}"
        
        scene = scenes[scene_name.lower()]
        for device_id, changes in scene["actions"]:
            if device_id in self.gadgets:
                self.gadgets[device_id].update(changes)
        
        self.save_devices()
        return f"Activated scene: {scene['description']}"


def get_tool_descriptions():
    """Return tool descriptions for LangChain"""
    return {
        "get_all_devices": "Get a list of all smart home devices and their current states",
        "control_light": "Control a light device. Parameters: device_id (e.g., 'light_living'), mode (off/warm_white/bright_yellow/cool_blue)",
        "control_ac": "Control an AC device. Parameters: device_id (e.g., 'ac_living'), power (on/off), temperature (18-28, optional)",
        "control_tv": "Control a TV device. Parameters: device_id (e.g., 'tv_living'), channel (Off/News/Cartoon/Sports/Movies)",
        "control_door_lock": "Control a door lock. Parameters: device_id (e.g., 'door_bedroom'), action (lock/unlock)",
        "get_time": "Get the current time",
        "get_date": "Get the current date",
        "get_weather": "Get weather information. Parameters: location (city name)",
        "set_timer": "Set a timer. Parameters: duration_minutes (number), label (optional text)",
        "set_reminder": "Set a reminder. Parameters: message (text), time (e.g., '3:00 PM')",
        "play_music": "Play music. Parameters: song_or_artist (name)",
        "search_web": "Search the web. Parameters: query (search text)",
        "calculate": "Perform calculations. Parameters: expression (e.g., '25 * 4')",
        "get_room_status": "Get status of all devices in a room. Parameters: room_name (living/bedroom)",
        "get_energy_usage": "Get estimated energy usage of active devices",
        "get_security_status": "Get security status of door locks",
        "create_scene": "Activate a predefined scene. Parameters: scene_name (movie/sleep/away/morning)"
    }