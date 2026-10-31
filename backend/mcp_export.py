import sys
import asyncio
import json
from typing import Dict, Any, List
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import the core backend JobAggregator
from scraper import JobAggregator

# Create the outward-facing MCP Server
app = Server("job-hunt-aggregator")
aggregator = JobAggregator()

@app.list_tools()
async def list_tools() -> list[Tool]:
    """Exposes the core aggregation pipeline to local LLM clients (Cursor, Claude Desktop, etc.)"""
    return [
        Tool(
            name="search_aggregated_jobs",
            description="Searches for software engineering and tech jobs by simultaneously aggregating data across JobSpy (LinkedIn/Indeed/Glassdoor), Playwright (LinkedIn Live Search), HackerNews, XML RSS Feeds, and SearxNG web search.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string", 
                        "description": "The job title, tech stack, or keywords (e.g. 'Senior Python Backend Developer')"
                    },
                    "location": {
                        "type": "string", 
                        "description": "The target location (e.g. 'Remote', 'San Francisco, CA')"
                    }
                },
                "required": ["keywords", "location"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handles execution when the local LLM client invokes our aggregation tool."""
    if name == "search_aggregated_jobs":
        keywords = arguments.get("keywords", "Software Engineer")
        location = arguments.get("location", "Remote")
        
        try:
            # aggregator.search_all is synchronous, run in a separate thread so we don't block the MCP asyncio loop
            jobs = await asyncio.to_thread(aggregator.search_all, keywords, location)
            
            # Formatting the output for the LLM context
            if not jobs:
                return [TextContent(type="text", text="No jobs found matching your criteria across any engines.")]
                
            result_str = f"Successfully extracted and deduplicated {len(jobs)} jobs (Aggregated via Playwright, JobSpy, HN, RSS & SearxNG):\n\n"
            
            # Limit to top 25 to avoid context bloat in the client LLM
            for i, j in enumerate(jobs[:25]): 
                result_str += f"{i+1}. {j['title']} at {j['company']} ({j['location']})\n   Source: {j.get('source', 'Unknown')}\n   URL: {j['url']}\n   Preview: {str(j.get('description', ''))[:150]}...\n\n"
                
            return [TextContent(type="text", text=result_str)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error executing aggregation pipeline: {str(e)}")]
            
    raise ValueError(f"Unknown tool requested: {name}")

async def main():
    """Starts the standard I/O MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
