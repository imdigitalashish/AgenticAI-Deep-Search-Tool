import os
import json
import asyncio
from groq import Groq
import re
import logging
from sentence_transformers import SentenceTransformer
import numpy as np

# Initialize Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Initialize sentence transformer model for embeddings
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Configure logging

class KnowledgeProcessor:
    def __init__(self, main_query, knowledge_bases, cache_file="topic_summaries.json"):
        self.main_query = main_query
        self.knowledge_bases = knowledge_bases
        self.topic_summaries = {}
        self.cache_file = cache_file
        print(f"Initialized KnowledgeProcessor with main query: {main_query}")

    async def process_all_knowledge_bases(self):
        """Process all knowledge bases in parallel."""
        # Check if cached results exist and are valid
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                cached_summaries = json.load(f)
            if self._is_cache_valid(cached_summaries):
                print("Using cached results.")
                self.topic_summaries = cached_summaries
                return self.topic_summaries

        print("Starting parallel processing of all knowledge bases.")
        tasks = [self.process_single_knowledge_base(sub_query, kb_info) 
                 for sub_query, kb_info in self.knowledge_bases.items()]
        results = await asyncio.gather(*tasks)
        self.topic_summaries = {sub_query: result for sub_query, result in zip(self.knowledge_bases.keys(), results)}
        
        # Cache results
        with open(self.cache_file, 'w') as f:
            json.dump(self.topic_summaries, f, indent=4)
        print("Finished processing and cached results.")
        return self.topic_summaries

    def _is_cache_valid(self, cached_summaries):
        """Check if cached results are still valid based on file modification times."""
        if cached_summaries.keys() != self.knowledge_bases.keys():
            return False
        for sub_query, kb_info in self.knowledge_bases.items():
            kb_path = kb_info["kb_path"]
            if os.path.getmtime(kb_path) > os.path.getctime(self.cache_file):
                return False
        return True

    async def process_single_knowledge_base(self, sub_query, kb_info):
        """Process a single knowledge base and generate topic summaries."""
        kb_path = kb_info["kb_path"]
        purpose = kb_info["purpose"]

        print(f"Processing knowledge base: {sub_query} (path: {kb_path})")
        
        # Read and clean the full text
        full_text = "".join(self.read_and_clean_file_in_chunks(kb_path))
        
        # Generate topics from the full text
        topics = await self.generate_topics(full_text, sub_query)
        print(f"Generated topics for {sub_query}: {topics}")

        # Extract insights for each topic
        topic_insights = {}
        chunks = list(self.read_and_clean_file_in_chunks(kb_path, chunk_size=5000))  # Smaller chunks for embeddings
        for topic in topics.get("response", []):
            insight = await self.extract_topic_information(chunks, topic, sub_query)
            topic_insights[topic] = insight
            print(f"Extracted insight for topic '{topic}' in {sub_query}.")

        result = {"purpose": purpose, "topics": topic_insights}
        return result

    async def generate_topics(self, text, sub_query):
        """Generate key topics from the full text."""
        system_prompt = f"""
        Analyze the provided knowledge base about "{sub_query}" and identify 3-5 key topics or themes.
        Return the result as a JSON object with a single key "response" containing an array of topic strings.
        Example: {{"response": ["Historical Context", "Key Figures", "Social Impact"]}}
        """
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text[:20000]}],  # Truncate to avoid token limits
                model="llama-3.1-8b-instant",
                max_tokens=200,
                temperature=0.7,
                stream=False,
            )
            result = json.loads(chat_completion.choices[0].message.content.strip())
            return result
        except Exception as e:
            logging.error(f"Error generating topics for {sub_query}: {e}")
            return {"response": ["General Information", "Key Points", "Analysis"]}

    async def extract_topic_information(self, chunks, topic, sub_query):
        """Extract insights for a topic using vector embeddings for efficiency."""
        system_prompt = f"""
        Extract and synthesize information specifically about the topic "{topic}" related to "{sub_query}".
        Provide a concise summary based on the provided text.
        """
        # Generate embeddings for chunks and topic
        chunk_embeddings = embedding_model.encode(chunks)
        topic_embedding = embedding_model.encode([topic])[0]
        
        # Find top 3 most relevant chunks
        similarities = np.dot(chunk_embeddings, topic_embedding) / (np.linalg.norm(chunk_embeddings, axis=1) * np.linalg.norm(topic_embedding))
        top_k_indices = similarities.argsort()[-3:][::-1]
        relevant_chunks = [chunks[i] for i in top_k_indices]
        
        # Summarize relevant chunks
        summary = ""
        for chunk in relevant_chunks:
            try:
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": chunk},
                    ],
                    model="llama-3.1-8b-instant",
                    max_tokens=150,
                    temperature=0.7,
                    stream=False,
                )
                summary += " " + chat_completion.choices[0].message.content.strip()
            except Exception as e:
                logging.error(f"Error summarizing chunk for topic '{topic}': {e}")
        return summary.strip() or "No relevant information found."

    def read_and_clean_file_in_chunks(self, file_path, chunk_size=5000):
        """Read and clean a file in chunks."""
        with open(file_path, 'r', encoding='utf-8') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                cleaned_chunk = self.clean_text(chunk)
                if cleaned_chunk.strip():
                    yield cleaned_chunk

    def clean_text(self, text):
        """Remove unwanted patterns from text."""
        text = re.sub(r'\s*\*\s*\[[^\]]+\]\([^)]+\)', '', text)  # Remove markdown links
        text = re.sub(r'###\s*\[[^\]]+\]\([^)]+\)', '', text)    # Remove headers with links
        return text.strip()

# Example knowledge bases (replace with your actual paths)
knowledge_bases = {
    "What are the key metrics used to measure the financial performance and growth of a SaaS company?": {
        "purpose": "To identify crucial indicators for assessing the financial health and potential of a SaaS business (e.g., MRR, ARR, Churn, CAC, LTV).",
        "kb_path": "/Users/imdigitalashish/Projects/Ashish/AgenticProjects/research_5d404a6c-11fb-40eb-876e-32b2de9a5c06/knowledge_4c42ba08.md",
        "query_id": "4c42ba08"
    },
    "What are the most common marketing and sales strategies employed by profitable SaaS companies to acquire and retain customers?": {
        "purpose": "To understand customer acquisition and retention techniques for revenue generation.",
        "kb_path": "/Users/imdigitalashish/Projects/Ashish/AgenticProjects/research_5d404a6c-11fb-40eb-876e-32b2de9a5c06/knowledge_5dc686fa.md",
        "query_id": "5dc686fa"
    },
    "What are the different pricing models commonly used in successful SaaS businesses?": {
        "purpose": "To understand various revenue generation strategies in SaaS.",
        "kb_path": "/Users/imdigitalashish/Projects/Ashish/AgenticProjects/research_5d404a6c-11fb-40eb-876e-32b2de9a5c06/knowledge_2dee47c1.md",
        "query_id": "2dee47c1"
    },
    "What are the legal and regulatory considerations for operating a SaaS business and monetizing it?": {
        "purpose": "To ensure legal compliance and avoid potential issues related to data privacy, intellectual property, and payments.",
        "kb_path": "/Users/imdigitalashish/Projects/Ashish/AgenticProjects/research_5d404a6c-11fb-40eb-876e-32b2de9a5c06/knowledge_707e9ff9.md",
        "query_id": "707e9ff9"
    },
    "What are some successful case studies of SaaS businesses, and what were their key strategies for earning money?": {
        "purpose": "To learn from real-world examples and identify effective monetization approaches.",
        "kb_path": "/Users/imdigitalashish/Projects/Ashish/AgenticProjects/research_5d404a6c-11fb-40eb-876e-32b2de9a5c06/knowledge_8cedfb70.md",
        "query_id": "8cedfb70"
    }
}

async def test_knowledge_base_and_report():
    """Test the knowledge processor and save results."""
    main_query = "Making money with SaaS"
    processor = KnowledgeProcessor(main_query, knowledge_bases)
    topic_summaries = await processor.process_all_knowledge_bases()
    print(f"Generated topic summaries for {len(topic_summaries)} sub-queries")
    print(json.dumps(topic_summaries, indent=4))

if __name__ == "__main__":
    asyncio.run(test_knowledge_base_and_report())