import os
import json
import gc
import asyncio
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

class KnowledgeProcessor:
    def __init__(self, main_query, knowledge_bases):
        self.main_query = main_query
        self.knowledge_bases = knowledge_bases
        self.topic_summaries = {}
        self.model, self.tokenizer = self.load_gemma_model()
        
    def load_gemma_model(self):
        """Load the Gemma model with memory optimization for MPS"""
        model_name = "google/gemma-2-2b-it"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="mps" if torch.backends.mps.is_available() else "cpu",
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
            max_memory={0: "4GB"}  # Adjusted for safety
        )
        model.eval()  # Set to evaluation mode to reduce memory usage
        return model, tokenizer
    
    async def process_all_knowledge_bases(self):
        """Process all knowledge bases with a semaphore to limit concurrency"""
        semaphore = asyncio.Semaphore(1)  # Limit to 1 task at a time
        async def sem_task(sub_query, kb_info):
            async with semaphore:
                return await self.process_single_knowledge_base(sub_query, kb_info)
        
        tasks = [sem_task(sub_query, kb_info) for sub_query, kb_info in self.knowledge_bases.items()]
        await asyncio.gather(*tasks)
        return self.topic_summaries
        
    async def process_single_knowledge_base(self, sub_query, kb_info):
        """Process a single knowledge base and generate topic summaries"""
        kb_path = kb_info["kb_path"]
        purpose = kb_info["purpose"]
        query_id = kb_info["query_id"]
        
        topics = await self.generate_topics(kb_path, sub_query)
        del kb_path  # Free up memory
        
        topic_insights = {}
        for topic in topics:
            insight = await self.extract_topic_information(kb_path, topic, sub_query)
            topic_insights[topic] = insight
            del insight  # Free up memory after use
            gc.collect()  # Force garbage collection
            torch.mps.empty_cache() if torch.backends.mps.is_available() else None
            
        self.topic_summaries[sub_query] = {
            "purpose": purpose,
            "topics": topic_insights
        }
        del topics, topic_insights  # Clean up
        gc.collect()
        torch.mps.empty_cache() if torch.backends.mps.is_available() else None
        
        return self.topic_summaries[sub_query]
        
    async def generate_topics(self, kb_path, sub_query):
        """Generate key topics from the knowledge base"""
        with open(kb_path, 'r') as f:
            kb_content = f.read()
            
        if len(kb_content) > 20000:  # Reduced from 50000
            kb_content = kb_content[:20000]
        
        system_prompt = f"""
        Analyze the provided knowledge base about "{sub_query}" and identify 3-5 key topics or themes that should be explored.
        Return the result as a JSON array of topic strings.
        Example: ["Historical Context", "Key Figures", "Social Impact", "Technological Aspects"]
        """
        
        input_text = system_prompt + "\n\n" + kb_content
        inputs = self.tokenizer(input_text, return_tensors="pt").to(self.model.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=100,  # Reduced from 200
                temperature=0.7,
                do_sample=True
            )
        
        result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        del inputs, outputs  # Free memory
        gc.collect()
        torch.mps.empty_cache() if torch.backends.mps.is_available() else None
        
        try:
            json_start = result.find('[')
            json_end = result.rfind(']') + 1
            json_str = result[json_start:json_end]
            topics = json.loads(json_str)
            return topics
        except (json.JSONDecodeError, ValueError):
            print(f"[SERVER]: Error parsing topics JSON for {sub_query}, using default topics")
            return ["General Information", "Key Points", "Analysis"]
    
    async def extract_topic_information(self, kb_path, topic, sub_query):
        """Extract insights for a specific topic from the knowledge base"""
        with open(kb_path, 'r') as f:
            kb_content = f.read()
            
        chunks = self.chunk_text(kb_content, chunk_size=1000, overlap=50)  # Reduced from 2000
        
        scored_chunks = []
        for chunk in chunks:
            relevance_score = self.calculate_relevance(chunk, topic)
            scored_chunks.append((chunk, relevance_score))
            
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        top_chunks = [chunk for chunk, score in scored_chunks[:2]]  # Reduced to 2 chunks
        del chunks, scored_chunks  # Free memory
        
        rag_content = f"Topic: {topic}\nQuery: {sub_query}\n\n" + "\n\n".join(top_chunks)
        
        system_prompt = f"""
        Extract and synthesize information specifically about the topic "{topic}" related to "{sub_query}" from the provided knowledge base excerpts.
        Focus only on this specific topic, providing a comprehensive but concise summary in markdown format.
        """
        
        input_text = system_prompt + "\n\n" + rag_content
        inputs = self.tokenizer(input_text, return_tensors="pt").to(self.model.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=150,  # Reduced from 300
                temperature=0.7,
                do_sample=True
            )
        
        result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        del inputs, outputs, input_text, rag_content  # Free memory
        gc.collect()
        torch.mps.empty_cache() if torch.backends.mps.is_available() else None
        
        try:
            json_start = result.find('{')
            json_end = result.rfind('}') + 1
            json_str = result[json_start:json_end]
            return json.loads(json_str)['markdown']
        except (json.JSONDecodeError, KeyError):
            return "Error processing this topic."
    
    def chunk_text(self, text, chunk_size=1000, overlap=50):
        """Split text into smaller chunks"""
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
        """Calculate relevance score of text to a topic"""
        topic_terms = topic.lower().split()
        text_lower = text.lower()
        
        score = 0
        for term in topic_terms:
            score += text_lower.count(term)
            
        return score / (len(text) / 1000)

# Knowledge bases dictionary (unchanged)
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

async def test_knowledge_base_and_report():
    """Test the knowledge processor and save results"""
    main_query = "Making money with Crypto"
    processor = KnowledgeProcessor(main_query, knowledge_bases)
    topic_summaries = await processor.process_all_knowledge_bases()
    print(f"Generated topic summaries for {len(topic_summaries)} sub-queries")
    
    with open("topic_summaries.json", "w") as f:
        json.dump(topic_summaries, f, indent=4)

if __name__ == "__main__":
    asyncio.run(test_knowledge_base_and_report())