import asyncio
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic_ai import Agent

load_dotenv()

app = FastAPI()

class ManimCode(BaseModel):
    code: str

agent = Agent(
    "gemini-2.0-flash-exp",
    result_type=ManimCode,
    system_prompt="Write only the Raw Manim code nothing else to create an intuitive animation for",
)

@app.post('/chat/')
async def post_chat(prompt: str):
    result = await agent.run(prompt)
    return JSONResponse(content=result.data.code)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("searchgemini:app", host="0.0.0.0", port=8000)
