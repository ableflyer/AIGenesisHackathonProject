import pygame
import sys
import json
import random
import os
import time
import fasteragent       # <-- NEW: Import your agent
import asyncio

pygame.init()

# ===============================
# File watching
# ===============================
json_path = "devices.json"
last_modified = os.path.getmtime(json_path)

def load_devices():
    with open("/assets/"+json_path, "r") as f:
        return json.load(f)

def check_for_updates():
    global last_modified, data, gadgets
    try:
        current_modified = os.path.getmtime(json_path)
        if current_modified != last_modified:
            last_modified = current_modified
            data = load_devices()
            gadgets = {g["id"]: g for g in data["gadgets"]}
            print("🔄 Reloaded devices.json - changes detected!")
            return True
    except Exception as e:
        print(f"Error checking for updates: {e}")
    return False

# ===============================
# Load JSON Data
# ===============================
data = load_devices()

rooms = {room["name"]: pygame.Rect(*room["area"]) for room in data["rooms"]}
gadgets = {g["id"]: g for g in data["gadgets"]}

# Screen setup
WIDTH, HEIGHT = 900, 650   # <-- Increased height for command bar
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Smart Home Simulation (AI Command Bar)")

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

font = pygame.font.SysFont(None, 28)
small_font = pygame.font.SysFont(None, 22)

# Player
player_pos = [150, 300]
player_speed = 4
player_radius = 15


# ===============================
# Command Bar (NEW)
# ===============================

command_text = ""      # What the user is typing
typing_active = True   # Always active for simplicity

def draw_command_bar():
    pygame.draw.rect(screen, (30, 30, 30), (0, HEIGHT - 50, WIDTH, 50))
    txt_surface = small_font.render("> " + command_text, True, (255, 255, 255))
    screen.blit(txt_surface, (10, HEIGHT - 40))


# ===============================
# Utility Functions
# ===============================

def draw_text(text, x, y, color=(0,0,0), font_obj=None):
    if font_obj is None:
        font_obj = font
    screen.blit(font_obj.render(text, True, color), (x, y))

def near(player, rect, distance=60):
    px, py = player
    return rect.collidepoint(px, py) or (rect.centerx - distance < px < rect.centerx + distance and
                                         rect.centery - distance < py < rect.centery + distance)

def save_json():
    with open("/assets/"+json_path, "w") as f:
        json.dump({"gadgets": list(gadgets.values()), "rooms": data["rooms"]}, f, indent=2)


# ===============================
# Drawing Functions
# ===============================

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
            pygame.draw.circle(screen,
                (255,255,0) if g["state"] > 0 else (100,100,100),
                (rect.centerx, rect.centery), 15)

        elif g["type"] == "ac":
            color = (100,150,255) if g["on"] else COLORS["gray"]
            pygame.draw.rect(screen, color, rect)
            if g["on"]:
                draw_text(f"{g['temperature']}°C", rect.x + 5, rect.y + 20)

        elif g["type"] == "tv":
            channel = g["channels"][g["channel"]]
            pygame.draw.rect(screen, COLORS[channel["color"]], rect)
            draw_text(channel["name"], rect.x + 5, rect.y + 20, font_obj=small_font)

        elif g["type"] == "door_lock":
            pygame.draw.rect(screen, (255,100,100) if g["locked"] else (100,255,150), rect)
            draw_text("🔒" if g["locked"] else "🔓", rect.x + 15, rect.y + 15)

    # Player
    pygame.draw.circle(screen, (0,100,200), player_pos, player_radius)

    # Command bar (NEW)
    draw_command_bar()


# ===============================
# Movement
# ===============================

def move_player(keys):
    dx = (keys[pygame.K_d] - keys[pygame.K_a]) * player_speed
    dy = (keys[pygame.K_s] - keys[pygame.K_w]) * player_speed

    new_x = player_pos[0] + dx
    new_y = player_pos[1] + dy

    new_rect = pygame.Rect(new_x - player_radius, new_y - player_radius, player_radius*2, player_radius*2)

    # Prevent walking into locked doors
    for g in gadgets.values():
        if g["type"] == "door_lock" and g["locked"]:
            door_rect = pygame.Rect(g["position"][0], g["position"][1], g["size"][0], g["size"][1])
            if new_rect.colliderect(door_rect):
                return

    if any(rect.collidepoint(new_x, new_y) for rect in rooms.values()):
        player_pos[0] = new_x
        player_pos[1] = new_y


# ===============================
# MAIN LOOP
# ===============================

async def main():
    global command_text
    clock = pygame.time.Clock()
    running = True
    frame_count = 0
    CHECK_INTERVAL = 30
    while running:
        dt = clock.tick(60)
        keys = pygame.key.get_pressed()
        frame_count += 1

        if frame_count % CHECK_INTERVAL == 0:
            check_for_updates()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                save_json()
                pygame.quit()
                sys.exit()

            # -----------------------------------
            # Text input handler (NEW)
            # -----------------------------------
            if event.type == pygame.KEYDOWN:

                if event.key == pygame.K_BACKSPACE:
                    command_text = command_text[:-1]

                elif event.key == pygame.K_RETURN:
                    if command_text.strip():
                        print(f"\nUser typed: {command_text}")

                        # RUN YOUR AI AGENT HERE
                        modified, changes, answer = fasteragent.home_agent_main(data, command_text)
                        fasteragent.save_json(data)

                        print("AI:", answer)

                        # Save JSON after agent modifies it
                        with open(json_path, "w") as f:
                            json.dump(data, f, indent=2)

                        command_text = ""   # clear bar

                else:
                    if len(command_text) < 120:
                        command_text += event.unicode

        move_player(keys)
        draw_scene()
        pygame.display.flip()
        await asyncio.sleep(0)  # Allow other tasks to run

if __name__ == "__main__":
    asyncio.run(main())