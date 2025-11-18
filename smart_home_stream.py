import pygame
import json
import os
import time
import numpy as np

pygame.display.init()
pygame.font.init()

json_path = "devices.json"

# Load JSON
def load_devices():
    with open(json_path, "r") as f:
        return json.load(f)

data = load_devices()

# Pygame virtual screen
WIDTH, HEIGHT = 900, 600
screen = pygame.Surface((WIDTH, HEIGHT))  # NO WINDOW
font = pygame.font.SysFont(None, 28)
small_font = pygame.font.SysFont(None, 20)

# Colors
COLORS = {
    "off": (180, 180, 180),
    "warm_white": (255, 240, 200),
    "bright_yellow": (255, 255, 100),
    "cool_blue": (180, 220, 255),
    "blue": (100, 150, 255),
    "green": (100, 255, 150),
    "red": (255, 100, 100),
    "purple": (190, 130, 255),
    "gray": (200, 200, 200)
}

rooms = {room["name"]: pygame.Rect(*room["area"]) for room in data["rooms"]}
gadgets = {g["id"]: g for g in data["gadgets"]}

player_pos = [150, 300]
player_radius = 15


def draw_text(text, x, y, color=(0,0,0)):
    screen.blit(font.render(text, True, color), (x, y))


def draw_scene():
    screen.fill((245, 245, 245))

    # Rooms
    for name, rect in rooms.items():
        pygame.draw.rect(screen, (180, 180, 180), rect, 5)
        draw_text(name.capitalize(), rect.x + 20, rect.y + 10)

    # Gadgets
    for g in gadgets.values():
        rect = pygame.Rect(g["position"][0], g["position"][1], g["size"][0], g["size"][1])

        if g["type"] == "light":
            color = COLORS[g["color_modes"][g["state"]]]
            pygame.draw.rect(screen, color, rect)
            pygame.draw.circle(screen, (255,255,0) if g["state"] > 0 else (100,100,100),
                               (rect.centerx, rect.centery), 15)

        elif g["type"] == "ac":
            color = (100,150,255) if g["on"] else COLORS["gray"]
            pygame.draw.rect(screen, color, rect)
            if g["on"]:
                draw_text(f"{g['temperature']}°C", rect.x+5, rect.y+20)

        elif g["type"] == "tv":
            channel = g["channels"][g["channel"]]
            pygame.draw.rect(screen, COLORS[channel["color"]], rect)
            draw_text(channel["name"], rect.x+5, rect.y+20, color=(0,0,0))

        elif g["type"] == "door_lock":
            pygame.draw.rect(screen, (255,100,100) if g["locked"] else (100,255,150), rect)
            draw_text("🔒" if g["locked"] else "🔓", rect.x+15, rect.y+15)

    pygame.draw.circle(screen, (0,100,200), player_pos, player_radius)

    draw_text("Streamlit Mode - AI changes auto-sync", 10, HEIGHT-30)


def run_pygame_stream():
    """Yields frames for Streamlit."""
    clock = pygame.time.Clock()

    while True:
        draw_scene()

        # Convert pygame surface → numpy → streamlit
        frame = pygame.surfarray.array3d(screen).swapaxes(0,1)

        yield frame

        clock.tick(30)
