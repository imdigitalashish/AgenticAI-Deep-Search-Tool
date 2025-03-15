import os
import json
import uuid
from google import genai
from dotenv import load_dotenv
from pydantic import BaseModel
import asyncio

# Import necessary classes from your project
from DeepSearchTool import  ReportGenerator

import asyncio
import json
from collections import Counter
import aiofiles  # Use aiofiles for asynchronous file I/O

class KnowledgeProcessor:
    def __init__(self, main_query, knowledge_bases, client):
        self.main_query = main_query
        self.knowledge_bases = knowledge_bases
        self.client = client
        self.topic_summaries = {}

    async def process_all_knowledge_bases(self):
        tasks = []
        for sub_query, kb_info in self.knowledge_bases.items():
            tasks.append(self.process_single_knowledge_base(sub_query, kb_info))

        async def run_in_batches(tasks, batch_size=3):
            for i in range(0, len(tasks), batch_size):
                await asyncio.gather(*tasks[i:i + batch_size])

        await run_in_batches(tasks)
        return self.topic_summaries

    async def process_single_knowledge_base(self, sub_query, kb_info):
        kb_path = kb_info["kb_path"]
        purpose = kb_info["purpose"]

        topics = await self.generate_topics(kb_path, sub_query)  # Use the regular generate_topics
        topic_insights = {}

        for topic in topics:
            insight = await self.extract_topic_information(kb_path, topic, sub_query)
            topic_insights[topic] = insight

        self.topic_summaries[sub_query] = {
            "purpose": purpose,
            "topics": topic_insights
        }

    async def generate_topics(self, kb_path, sub_query):
        #  Read a limited portion of the file for topic generation.
        try:
            async with aiofiles.open(kb_path, 'r', encoding='utf-8') as f:
                kb_content = await f.read(100000)  # Read only the first 100,000 characters
        except FileNotFoundError:
            print(f"[SERVER]: File not found: {kb_path}")
            return ["General Information", "Key Points", "Analysis"]
        except Exception as e:
            print(f"[SERVER]: Error reading file {kb_path}: {e}")
            return ["General Information", "Key Points", "Analysis"]
        
        system_prompt = f"""
        Analyze the provided knowledge base about "{sub_query}" and identify 3-5 key topics or themes that should be explored.
        Return the result as a JSON array of topic strings.
        Example: ["Historical Context", "Key Figures", "Social Impact", "Technological Aspects"]
        """

        try:
             result = await self.client.models.generate_content(
                model="gemini-2.0-pro-exp-02-05",
                contents=[system_prompt, kb_content],
                config={
                    'response_mime_type': 'application/json'
                }
            )
             topics = json.loads(result.text)
             return topics
        except json.JSONDecodeError:
            print(f"[SERVER]: Error parsing topics JSON for {sub_query}, using default topics")
            return ["General Information", "Key Points", "Analysis"]
        except Exception as e:
            print(f"[SERVER]: Error generating topics for {sub_query}: {e}")
            return ["General Information", "Key Points", "Analysis"]
        
        


    async def extract_topic_information(self, kb_path, topic, sub_query):
        
        best_chunks = []
        best_score = -1

        async for chunk in self.chunk_text_stream(kb_path):
            relevance_score = self.calculate_relevance(chunk, topic)
            if relevance_score > best_score:
                best_chunks = [chunk]
                best_score = relevance_score
            elif relevance_score == best_score:
                best_chunks.append(chunk)

        # Limit to top 3 chunks
        top_chunks = best_chunks[:3]

        
        rag_content = f"Topic: {topic}\nQuery: {sub_query}\n\n" + "\n\n".join(top_chunks)

        system_prompt = f"""
        Extract and synthesize information specifically about the topic "{topic}" related to "{sub_query}" from the provided knowledge base excerpts.
        Focus only on this specific topic, providing a comprehensive but concise summary in markdown format.
        """

        try:
            result = await self.client.models.generate_content(
                model="gemini-2.0-pro-exp-02-05",
                contents=[system_prompt, rag_content],
                config={
                    'response_mime_type': 'application/json',
                   # 'response_schema': MarkdownResponse  # Assuming MarkdownResponse is defined
                }
            )
            return json.loads(result.text)['markdown'] # Make sure the structure is as needed
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[SERVER]: Error processing topic {topic}: {e}")
            return "Error processing this topic."
        except Exception as e:  # Catch other potential errors
            print(f"[SERVER]: Unexpected error processing topic {topic}: {e}")
            return "Error processing this topic."

    async def chunk_text_stream(self, kb_path, chunk_size=4000, overlap=100):
        """
        Asynchronously reads and yields chunks of text from a file.
        """
        try:
            async with aiofiles.open(kb_path, 'r', encoding='utf-8') as f:
                text = ""
                async for line in f:  # Asynchronously iterate through lines
                    text += line
                    while len(text) >= chunk_size:
                        end = chunk_size
                        paragraph_break = text.rfind("\n\n", 0, end)
                        sentence_break = text.rfind(". ", 0, end)

                        if paragraph_break > chunk_size // 2:
                            end = paragraph_break + 2
                        elif sentence_break > chunk_size // 2:
                            end = sentence_break + 2
                        
                        yield text[:end]
                        text = text[end - overlap:]
                if text:
                    yield text  # Yield any remaining text

        except FileNotFoundError:
            print(f"[SERVER]: File not found: {kb_path}")
            yield ""  # Yield an empty string to avoid errors down the line
        except Exception as e:
            print(f"[SERVER]: Error during chunking: {e}")
            yield ""



    def calculate_relevance(self, text, topic):
        topic_terms = [t.lower() for t in topic.split()]
        text_lower = text.lower()
        word_counts = Counter(text_lower.split())

        score = 0
        for term in topic_terms:
            score += word_counts[term]

        return score / (len(text) / 1000) if text else 0  # Avoid division by zero
load_dotenv()

knowledge_bases = {
    "What are the most popular and reputable cryptocurrency platforms and exchanges for trading, staking, and lending?": {
        "purpose": "To identify reliable and trustworthy services for engaging in cryptocurrency-related income generation.",
        "kb_path": "/Users/imdigitalashish/Projects/Ashish/AgenticProjects/research_df22a5e7-a1e8-43e2-8b5d-a539a2d86c4e/knowledge_cf5f5192.md",
        "query_id": "cf5f5192"
    },
    "What are the risks and potential downsides associated with each method of making money with cryptocurrency?": {
        "purpose": "To assess the potential losses and challenges involved in each approach, enabling informed decision-making.",
        "kb_path": "/Users/imdigitalashish/Projects/Ashish/AgenticProjects/research_df22a5e7-a1e8-43e2-8b5d-a539a2d86c4e/knowledge_61cc84b5.md",
        "query_id": "61cc84b5"
    },
    "What are the different methods of earning income with cryptocurrencies (e.g., trading, staking, mining, lending)?": {
        "purpose": "To understand the range of available income-generating strategies in the cryptocurrency space.",
        "kb_path": "/Users/imdigitalashish/Projects/Ashish/AgenticProjects/research_df22a5e7-a1e8-43e2-8b5d-a539a2d86c4e/knowledge_ff2c50b0.md",
        "query_id": "ff2c50b0"
    },
    "What tax regulations and legal considerations apply to cryptocurrency income in different jurisdictions?": {
        "purpose": "To understand the legal and financial obligations associated with earning money from cryptocurrencies.",
        "kb_path": "/Users/imdigitalashish/Projects/Ashish/AgenticProjects/research_df22a5e7-a1e8-43e2-8b5d-a539a2d86c4e/knowledge_370b8d57.md",
        "query_id": "370b8d57"
    },
    "What are some successful case studies or examples of individuals or entities making substantial income with cryptocurrency?": {
        "purpose": "To gain insights from real-world examples and learn from successful strategies, while also understanding the potential for survivorship bias.",
        "kb_path": "/Users/imdigitalashish/Projects/Ashish/AgenticProjects/research_df22a5e7-a1e8-43e2-8b5d-a539a2d86c4e/knowledge_e1908553.md",
        "query_id": "e1908553"
    }
}

class MarkdownResponse(BaseModel):
    markdown: str

async def test_knowledge_base_and_report():
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    
    main_query = "Making money with Crypto"
    

    processor = KnowledgeProcessor(main_query, knowledge_bases, client)
    topic_summaries = await processor.process_all_knowledge_bases()
    print(f"Generated topic summaries for {len(topic_summaries)} sub-queries")
    
    report_generator = ReportGenerator(main_query, topic_summaries, client)
    final_report = report_generator.generate_final_report()
    
    print(f"Final report generated and saved to: {final_report['filename']}")
    
    report_preview = final_report['report'][:500] + "..."
    print(f"\nReport Preview:\n{report_preview}")
    
    return final_report

if __name__ == "__main__":
    final_report = asyncio.run(test_knowledge_base_and_report())