import asyncio
from fastmcp import Client

async def main():
    async with Client("http://localhost:8001/mcp") as client:
        tools = await client.list_tools()
        print("Outils disponibles :")
        for tool in tools:
            print(f"- {tool.name}: {tool.description}")

asyncio.run(main())
