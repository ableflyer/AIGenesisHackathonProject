import asyncio, json
from SHAgent import SmartHomeController, SmartHomeAgent

async def main():
    with open('smart_devices.json','r') as f:
        data = json.load(f)
    ctrl = SmartHomeController(data)
    # Use rule based only for deterministic test
    agent = SmartHomeAgent(ctrl, use_llm=False)
    tests = [
        "unlock the front door",
        "lock all doors",
        "set living room temperature to 25",
        "increase the living room temperature by 2",
        "make the living room warmer",
        "decrease bedroom temperature by 3",
    ]
    for t in tests:
        resp = await agent.process_command(t)
        print(f"CMD: {t}\nRESP: {resp}\nINTENT: {agent.last_intent}\n--")

if __name__ == '__main__':
    asyncio.run(main())
