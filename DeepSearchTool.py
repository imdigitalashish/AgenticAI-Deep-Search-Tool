import asyncio
import json
import os
import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel
import serpapi
from google import genai
from dotenv import load_dotenv
from crawl4ai import AsyncWebCrawler

load_dotenv()

class MarkdownResponse(BaseModel):
    markdown: str

class ResearchPlanner:
    def __init__(self, query, client):
        self.query = query
        self.client = client
        
    def generate_action_plan(self):
        system_prompt = """
        You are a research planning assistant. Given a research query, create a structured action plan with 3-5 specific sub-queries that will help gather comprehensive information about the topic.
        
        For each sub-query:
        1. Make it specific and searchable
        2. Ensure it explores a different dimension of the main query
        3. Format as a JSON array with objects containing 'sub_query' and 'purpose' fields
        
        Example:
        For query "Panipat Battle":
        [
            {"sub_query": "What were the causes of the Third Battle of Panipat?", "purpose": "Understanding historical context"},
            {"sub_query": "What were the military strategies used in the Battle of Panipat?", "purpose": "Analyzing tactical aspects"},
            {"sub_query": "What were the consequences of the Battle of Panipat on the Maratha Empire?", "purpose": "Evaluating historical impact"},
            {"sub_query": "How is the Battle of Panipat portrayed in historical accounts?", "purpose": "Examining historical perspectives"}
        ]
        """
        
        result = self.client.models.generate_content(
            model="gemini-2.0-pro-exp-02-05",
            contents=[system_prompt, self.query],
            config={
                'response_mime_type': 'application/json'
            }
        )
        
        try:
            action_plan = json.loads(result.text)
            return action_plan
        except json.JSONDecodeError:
            print("[SERVER]: Error parsing action plan JSON, using fallback approach")
            return [{"sub_query": self.query, "purpose": "Main research query"}]

class DeepSearchTool:
    def __init__(self, query):
        self.query = query
        self.engine = "google"
        self.num_links = 5  
        self.kb_id = str(uuid.uuid4())
        self.knowledge_file = f"knowledge_{self.kb_id}.md"
        self.links = []
        
    def search_different_websites_serpapi(self) -> List[str]:
        params = {
            "q": self.query,
            "api_key": os.getenv("SERPAPI_API_KEY"),
            "engine": self.engine,
        }

        if not params["api_key"]:
            raise ValueError("SERPAPI_API_KEY environment variable not set.")

        search = serpapi.search(params)
        results = search.get("organic_results", [])
        print(f"[SERVER]: Found {len(results)} results for query: {self.query}")

        links: List[str] = []
        for result in results:
            if "link" in result:
                links.append(result["link"])
        
        self.links = links[:self.num_links]
        return self.links

    async def crawl_and_create_knowledge_file(self):
        if not self.links:
            self.search_different_websites_serpapi()
            
        if not self.links:
            print(f"[SERVER]: No URLs found to crawl for query: {self.query}")
            return None
        
        print(f"[SERVER]: Starting crawl of {len(self.links)} websites for: {self.query}")
        
        with open(self.knowledge_file, "w") as f:
            f.write(f"# Knowledge Base for: {self.query}\n\n")
            f.write(f"Generated on: {asyncio.get_running_loop().time()}\n\n")
            f.write("---\n\n")
        
        async def crawl():
            async with AsyncWebCrawler() as crawler:
                for i, link in enumerate(self.links):
                    try:
                        print(f"[SERVER]: Crawling {i+1}/{len(self.links)}: {link}")
                        result = await crawler.arun(url=link)
                        
                        with open(self.knowledge_file, "a") as f:
                            f.write(f"## Source {i+1}: {link}\n\n")
                            f.write(result.markdown)
                            f.write("\n\n---\n\n")
                            
                        print(f"[SERVER]: Successfully added {link} to knowledge file")
                    except Exception as e:
                        print(f"[SERVER]: Error crawling {link}: {str(e)}")
                        with open(self.knowledge_file, "a") as f:
                            f.write(f"## Source {i+1}: {link}\n\n")
                            f.write(f"*Error crawling this source: {str(e)}*\n\n")
                            f.write("---\n\n")
        
        await crawl()
        print(f"[SERVER]: Knowledge file created at: {os.path.abspath(self.knowledge_file)}")
        return os.path.abspath(self.knowledge_file)
    
    def clean_up(self):
        if os.path.exists(self.knowledge_file):
            os.remove(self.knowledge_file)
            print(f"[SERVER]: Cleaned up knowledge file: {self.knowledge_file}")

class ParallelResearcher:
    def __init__(self, main_query, action_plan):
        self.main_query = main_query
        self.action_plan = action_plan
        self.search_results = {}
        self.knowledge_bases = {}
        self.kb_base_dir = f"research_{uuid.uuid4()}"
        
        os.makedirs(self.kb_base_dir, exist_ok=True)
        
    async def execute_all_research_tasks(self):
        tasks = []
        for item in self.action_plan:
            tasks.append(self.execute_single_research_task(item))
            
        await asyncio.gather(*tasks)
        return self.knowledge_bases
        
    async def execute_single_research_task(self, query_item):
        sub_query = query_item["sub_query"]
        purpose = query_item["purpose"]
        
        query_id = str(uuid.uuid4())[:8]
        kb_filename = f"{self.kb_base_dir}/knowledge_{query_id}.md"
        
        print(f"[SERVER]: Researching sub-query: {sub_query}")
        
        search_tool = DeepSearchTool(sub_query)
        search_tool.knowledge_file = kb_filename  
        
        links = search_tool.search_different_websites_serpapi()
        self.search_results[sub_query] = links
        
        kb_path = await search_tool.crawl_and_create_knowledge_file()
        self.knowledge_bases[sub_query] = {
            "purpose": purpose,
            "kb_path": kb_path,
            "query_id": query_id
        }
        
        return kb_path

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
        query_id = kb_info["query_id"]
        
        topics = await self.generate_topics(kb_path, sub_query)
        
        topic_insights = {}
        for topic in topics:
            insight = await self.extract_topic_information(kb_path, topic, sub_query)
            topic_insights[topic] = insight
            
        self.topic_summaries[sub_query] = {
            "purpose": purpose,
            "topics": topic_insights
        }
        
        return topic_insights
        
    async def generate_topics(self, kb_path, sub_query):
        with open(kb_path, 'r') as f:
            kb_content = f.read()
            
        if len(kb_content) > 100000:  
            kb_content = kb_content[:100000]  
        
        system_prompt = f"""
        Analyze the provided knowledge base about "{sub_query}" and identify 3-5 key topics or themes that should be explored.
        Return the result as a JSON array of topic strings.
        Example: ["Historical Context", "Key Figures", "Social Impact", "Technological Aspects"]
        """
        
        result = self.client.models.generate_content(
            model="gemini-2.0-pro-exp-02-05",
            contents=[system_prompt, kb_content],
            config={
                'response_mime_type': 'application/json'
            }
        )
        
        try:
            topics = json.loads(result.text)
            return topics
        except json.JSONDecodeError:
            print(f"[SERVER]: Error parsing topics JSON for {sub_query}, using default topics")
            return ["General Information", "Key Points", "Analysis"]
    
    async def extract_topic_information(self, kb_path, topic, sub_query):
        with open(kb_path, 'r') as f:
            kb_content = f.read()
            
        chunks = self.chunk_text(kb_content, chunk_size=4000, overlap=100)
        
        scored_chunks = []
        for chunk in chunks:
            relevance_score = self.calculate_relevance(chunk, topic)
            scored_chunks.append((chunk, relevance_score))
            
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        top_chunks = [chunk for chunk, score in scored_chunks[:3]]
        
        rag_content = f"Topic: {topic}\nQuery: {sub_query}\n\n" + "\n\n".join(top_chunks)
        
        system_prompt = f"""
        Extract and synthesize information specifically about the topic "{topic}" related to "{sub_query}" from the provided knowledge base excerpts.
        Focus only on this specific topic, providing a comprehensive but concise summary in markdown format.
        """
        
        result = self.client.models.generate_content(
            model="gemini-2.0-pro-exp-02-05",
            contents=[system_prompt, rag_content],
            config={
                'response_mime_type': 'application/json',
                'response_schema': MarkdownResponse
            }
        )
        
        try:
            return json.loads(result.text)['markdown']
        except (json.JSONDecodeError, KeyError):
            return "Error processing this topic."
    
    def chunk_text(self, text, chunk_size=8000, overlap=200):
        if len(text) <= chunk_size:
            return [text]
            
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            if end >= len(text):
                chunks.append(text[start:])
            else:
                paragraph_break = text.rfind("\n\n", start, end)
                sentence_break = text.rfind(". ", start, end)
                
                if paragraph_break > start + chunk_size // 2:
                    end = paragraph_break + 2
                elif sentence_break > start + chunk_size // 2:
                    end = sentence_break + 2
                    
                chunks.append(text[start:end])
                start = end - overlap  
                
        return chunks
    
    def calculate_relevance(self, text, topic):
        topic_terms = topic.lower().split()
        text_lower = text.lower()
        
        score = 0
        for term in topic_terms:
            score += text_lower.count(term)
            
        return score / (len(text) / 1000)

class ReportGenerator:
    def __init__(self, main_query, topic_summaries, client):
        self.main_query = main_query
        self.topic_summaries = topic_summaries
        self.client = client
        
    def generate_final_report(self):
        report_sections = []
        
        report_sections.append(f"# Comprehensive Research Report: {self.main_query}\n\n")
        report_sections.append("## Introduction\n\n")
        
        for sub_query, summary_info in self.topic_summaries.items():
            purpose = summary_info["purpose"]
            section_title = f"## {sub_query}\n\n"
            section_purpose = f"*Purpose: {purpose}*\n\n"
            
            report_sections.append(section_title)
            report_sections.append(section_purpose)
            
            for topic, content in summary_info["topics"].items():
                report_sections.append(f"### {topic}\n\n")
                report_sections.append(f"{content}\n\n")
        
        report_content = "".join(report_sections)
        
        system_prompt = f"""
        You are a research synthesis expert. Review this structured research report on "{self.main_query}" and enhance it:
        
        1. Add a concise executive summary at the beginning
        2. Add a conclusion section that synthesizes key insights
        3. Ensure consistent formatting and flow between sections
        4. Fix any redundancies or inconsistencies
        5. Keep all the substantive content but improve organization and connections
        
        Return the improved report in Markdown format.
        """
        
        result = self.client.models.generate_content(
            model="gemini-2.0-pro-exp-02-05",
            contents=[system_prompt, report_content],
            config={
                'response_mime_type': 'application/json',
                'response_schema': MarkdownResponse
            }
        )
        
        try:
            final_report = json.loads(result.text)['markdown']
            
            report_filename = f"report_{uuid.uuid4()}.md"
            with open(report_filename, "w") as f:
                f.write(final_report)
                
            return {
                "report": final_report,
                "filename": report_filename
            }
        except (json.JSONDecodeError, KeyError):
            print("[SERVER]: Error generating final report")
            return {
                "report": report_content,
                "filename": None
            }


class EnhancedDeepSearchTool:
    def __init__(self, query):
        self.query = query
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.research_dir = f"research_{uuid.uuid4()}"
        os.makedirs(self.research_dir, exist_ok=True)
        
    async def execute_full_research(self):
        print(f"[SERVER]: Starting enhanced research for query: {self.query}")
        
        planner = ResearchPlanner(self.query, self.client)
        action_plan = planner.generate_action_plan()
        print(f"[SERVER]: Generated action plan with {len(action_plan)} sub-queries")
        
        researcher = ParallelResearcher(self.query, action_plan)
        knowledge_bases = await researcher.execute_all_research_tasks()
        print(f"[SERVER]: Completed crawling for all sub-queries")
        
        
        with open(f"{self.research_dir}/knowledge_bases.json", "w") as f:
            json.dump(knowledge_bases, f)
            
        
        processor = KnowledgeProcessor(self.query, knowledge_bases, self.client)
        topic_summaries = await processor.process_all_knowledge_bases()
        print(f"[SERVER]: Processed all knowledge bases into topic summaries")
        
        report_gen = ReportGenerator(self.query, topic_summaries, self.client)
        final_report = report_gen.generate_final_report()
        print(f"[SERVER]: Generated final comprehensive report")
        
        return {
            "action_plan": action_plan,
            "knowledge_bases": knowledge_bases,
            "topic_summaries": topic_summaries,
            "final_report": final_report
        }
        
    def execute_research(self):
        return asyncio.run(self.execute_full_research())
        
    def clean_up(self):
        import shutil
        if os.path.exists(self.research_dir):
            shutil.rmtree(self.research_dir)
            print(f"[SERVER]: Cleaned up research directory: {self.research_dir}")


if __name__ == "__main__":
    query = "Making money with Crypto"
    enhanced_tool = EnhancedDeepSearchTool(query)
    results = enhanced_tool.execute_research()
    
    print(f"Final report saved to: {results['final_report']['filename']}")
    