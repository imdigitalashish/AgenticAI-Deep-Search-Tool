from pydantic_ai import Agent, RunContext
import groq
from dotenv import load_dotenv
import datetime
from pydantic import BaseModel
from pydantic_ai.models import groq

load_dotenv()


async def fetch_creator_username(ctx: RunContext):
    return "My creator is imdigitalashish"

class ProgrammingDefinition(BaseModel):
    definition: str


agent = Agent(
    model="groq:llama3-70b-8192",
    tools=[fetch_creator_username],
    result_type=ProgrammingDefinition
)



result = agent.run_sync("Who's your creator? respond with coolness")

print(result.data.definition)