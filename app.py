import streamlit as st
import fasteragent
import json
import time
import os

st.set_page_config(page_title="Smart Home AI", layout="wide")

# ============================================================
# Helper: ALWAYS load latest JSON (like pygame)
# ============================================================
def load_devices():
    with open("devices.json", "r") as f:
        return json.load(f)

# Auto-reload devices.json every run
devices_data = load_devices()
gadgets = devices_data["gadgets"]

# ============================================================
# TITLE
# ============================================================
st.title("🏠 Smart Home AI Assistant")


# ============================================================
# DEVICE DASHBOARD (AUTO-REFRESHING)
# ============================================================
st.header("📊 Device Dashboard")

# Group by room
rooms = {}
for g in gadgets:
    rooms.setdefault(g["room"], []).append(g)

def device_card(g):
    st.markdown(f"### {g['id'].replace('_', ' ').title()}")

    if g["type"] == "light":
        color = g["color_modes"][g["state"]]
        st.write(f"💡 State: `{color}`")
        st.progress(g["state"] / (len(g["color_modes"]) - 1))

    elif g["type"] == "ac":
        st.write(f"❄️ Status: **{'On' if g['on'] else 'Off'}**")
        st.metric("Temperature", f"{g['temperature']}°C")

    elif g["type"] == "tv":
        ch = g["channels"][g["channel"]]
        st.write(f"📺 Channel: `{ch['name']}`")

    elif g["type"] == "door_lock":
        st.write("🚪 Door: " + ("Locked 🔒" if g["locked"] else "Unlocked 🔓"))


# Render dashboard
for room, gadget_list in rooms.items():
    st.subheader(f"🛏 Room: {room.title()}")
    cols = st.columns(3)
    for i, g in enumerate(gadget_list):
        with cols[i % 3]:
            device_card(g)

st.markdown("---")


# ============================================================
# CHAT PANEL
# ============================================================
st.header("🤖 AI Assistant")

if "history" not in st.session_state:
    st.session_state["history"] = []

# Show chat
for sender, msg in st.session_state["history"]:
    st.markdown(f"**{sender}:** {msg}")

user_prompt = st.text_input("Say something to your smart home:")

if st.button("Send"):
    if user_prompt.strip():
        st.session_state["history"].append(("You", user_prompt))

        # IMPORTANT: Load fresh data before sending to the agent
        latest_data = load_devices()

        # Run agent (same as smart_home_demo)
        modified, changes, answer = fasteragent.home_agent_main(latest_data, user_prompt)

        # Save effects applied by agent
        if modified:
            with open("devices.json", "w") as f:
                json.dump(latest_data, f, indent=2)

        st.session_state["history"].append(("Assistant", answer))

        st.rerun()
