"""Pygame demo to showcase the SmartHomeAgent.

Features:
- Displays rooms and key devices with simplified states
- Text input box to type natural language commands (press Enter to run)
- Shows last intent JSON, results, and response from the agent
- Hybrid AI + rule-based parsing (falls back automatically if LLM disabled)

Run:
    python demo_pygame.py

Requires:
    pip install pygame
"""
import json
import pygame
import threading
import queue
import time
from pathlib import Path
from typing import Dict, Any

from SHAgent import SmartHomeController, SmartHomeAgent

ASSETS = {}
WIDTH, HEIGHT = 1100, 680
BG_COLOR = (24, 26, 30)
PANEL_BG = (36, 39, 45)
TEXT_COLOR = (230, 230, 235)
ACCENT = (90, 160, 255)
ERROR = (255, 90, 90)
SUCCESS = (90, 200, 120)
FONT_NAME = "consolas"

pygame.init()
FONT = pygame.font.SysFont(FONT_NAME, 18)
FONT_SMALL = pygame.font.SysFont(FONT_NAME, 14)
FONT_TITLE = pygame.font.SysFont(FONT_NAME, 24, bold=True)

class CommandExecutor(threading.Thread):
    def __init__(self, agent: SmartHomeAgent):
        super().__init__(daemon=True)
        self.agent = agent
        self.in_q: queue.Queue[str] = queue.Queue()
        self.out_q: queue.Queue[Dict[str, Any]] = queue.Queue()
        self._stop = False

    def run(self):
        while not self._stop:
            try:
                cmd = self.in_q.get(timeout=0.1)
            except queue.Empty:
                continue
            start = time.time()
            response = self.agent.process_command_sync(cmd)
            duration = time.time() - start
            self.out_q.put({
                "command": cmd,
                "response": response,
                "intent": self.agent.last_intent,
                "results": self.agent.last_results,
                "time_ms": int(duration * 1000)
            })

    def submit(self, cmd: str):
        self.in_q.put(cmd)

    def poll(self):
        try:
            return self.out_q.get_nowait()
        except queue.Empty:
            return None

    def stop(self):
        self._stop = True


def draw_text(surface, text, x, y, font=FONT, color=TEXT_COLOR):
    surf = font.render(text, True, color)
    surface.blit(surf, (x, y))
    return surf.get_height()


def wrap_text(text: str, width: int, font=FONT_SMALL):
    words = text.split()
    lines = []
    line = []
    current_width = 0
    for w in words:
        w_width = font.size(w + ' ')[0]
        if current_width + w_width > width and line:
            lines.append(' '.join(line))
            line = [w]
            current_width = w_width
        else:
            line.append(w)
            current_width += w_width
    if line:
        lines.append(' '.join(line))
    return lines


def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Smart Home AI Agent Demo")
    clock = pygame.time.Clock()

    # Load devices
    data_path = Path(__file__).parent / 'smart_devices.json'
    devices_config = json.loads(data_path.read_text(encoding='utf-8'))
    controller = SmartHomeController(devices_config)
    agent = SmartHomeAgent(controller, model_name="gemma3:latest", use_llm=True)

    executor = CommandExecutor(agent)
    executor.start()

    input_buffer = ""
    history: list[Dict[str, Any]] = []  # store last few command results

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RETURN:
                    cmd = input_buffer.strip()
                    if cmd:
                        executor.submit(cmd)
                        input_buffer = ""
                elif event.key == pygame.K_BACKSPACE:
                    input_buffer = input_buffer[:-1]
                else:
                    if event.unicode.isprintable():
                        input_buffer += event.unicode

        # Poll executor for finished commands
        result = executor.poll()
        if result:
            history.append(result)
            history = history[-6:]

        screen.fill(BG_COLOR)

        # Panels layout
        left_w = 380
        mid_w = 360
        right_w = WIDTH - left_w - mid_w - 40

        # LEFT PANEL: Rooms / Devices
        pygame.draw.rect(screen, PANEL_BG, (20, 20, left_w, HEIGHT-40), border_radius=8)
        draw_text(screen, "Rooms & Devices", 32, 30, FONT_TITLE, ACCENT)

        rooms = {}
        for dev in controller.devices.values():
            rooms.setdefault(dev['location']['room'], []).append(dev)

        y = 70
        for room, devs in rooms.items():
            draw_text(screen, room.replace('_',' ').title(), 32, y, FONT, ACCENT)
            y += 22
            for d in devs:
                state_frag = []
                st = d.get('state', {})
                if d['type'] == 'light':
                    state_frag.append(st.get('status','?'))
                    state_frag.append(f"bri={st.get('brightness','?')}")
                elif d['type'] == 'thermostat':
                    state_frag.append(f"cur={st.get('current_temperature','?')}")
                    state_frag.append(f"target={st.get('target_temperature','?')}")
                elif d['type'] == 'fan':
                    state_frag.append(st.get('status','?'))
                    state_frag.append(f"spd={st.get('speed','?')}")
                elif d['type'] == 'blind':
                    state_frag.append(f"pos={st.get('position','?')}")
                else:
                    state_frag.append(st.get('status', ''))
                line = f"- {d['name']} [{d['type']}] {' '.join(state_frag)}"
                for wrapped in wrap_text(line, left_w-60):
                    draw_text(screen, wrapped, 48, y, FONT_SMALL)
                    y += 16
            y += 10
            if y > HEIGHT - 160:
                break

        # MIDDLE PANEL: Command Input & Last Response
        pygame.draw.rect(screen, PANEL_BG, (20+left_w+10, 20, mid_w, HEIGHT-40), border_radius=8)
        draw_text(screen, "Command Console", 20+left_w+22, 30, FONT_TITLE, ACCENT)

        # Input box
        pygame.draw.rect(screen, (50, 55, 65), (20+left_w+30, 70, mid_w-60, 32), border_radius=6)
        draw_text(screen, "> " + input_buffer, 20+left_w+38, 78, FONT)
        draw_text(screen, "Press Enter to send", 20+left_w+34, 108, FONT_SMALL, (160,160,170))

        # Last response
        if history:
            last = history[-1]
            draw_text(screen, f"Last Command ({last['time_ms']} ms):", 20+left_w+22, 140, FONT, ACCENT)
            resp_lines = wrap_text(last['response'], mid_w-60)
            yy = 164
            for ln in resp_lines:
                draw_text(screen, ln, 20+left_w+30, yy, FONT_SMALL)
                yy += 16
        else:
            draw_text(screen, "No commands yet.", 20+left_w+22, 140, FONT_SMALL, (150,150,155))

        # RIGHT PANEL: Intents & History
        px = 20+left_w+10+mid_w+10
        pygame.draw.rect(screen, PANEL_BG, (px, 20, right_w, HEIGHT-40), border_radius=8)
        draw_text(screen, "Intents & History", px+12, 30, FONT_TITLE, ACCENT)

        yy = 70
        for item in reversed(history):
            draw_text(screen, f"Command: {item['command']}", px+14, yy, FONT_SMALL, ACCENT)
            yy += 16
            draw_text(screen, "Intent:", px+18, yy, FONT_SMALL, (180,180,190))
            yy += 16
            intent_json = json.dumps(item.get('intent', {}), ensure_ascii=False)
            for ln in wrap_text(intent_json, right_w-40):
                draw_text(screen, ln, px+26, yy, FONT_SMALL)
                yy += 14
            if item['results']:
                draw_text(screen, "Results:", px+18, yy, FONT_SMALL, (180,180,190))
                yy += 16
                for r in item['results']:
                    for ln in wrap_text(r, right_w-40):
                        draw_text(screen, ln, px+26, yy, FONT_SMALL, SUCCESS)
                        yy += 14
            yy += 10
            if yy > HEIGHT - 80:
                break

        pygame.display.flip()
        clock.tick(30)

    executor.stop()
    pygame.quit()

if __name__ == "__main__":
    main()
