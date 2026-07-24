from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# We will use ChatOpenAI as a placeholder, but you can swap this for Anthropic, Llama 3, etc.
# from langchain_openai import ChatOpenAI  //for openai

# from langchain_moonshot import ChatMoonshot //for kimi

# --- 1. Import Groq instead of OpenAI ---
from langchain_groq import ChatGroq

class NewsGenerationEngine:
    def __init__(self, llm_model=None):
        """
        Initializes the RAG Engine and constructs the LCEL pipeline.
        """
        # Initialize the LLM (Defaults to OpenAI if none is provided)
        # self.llm = llm_model or ChatOpenAI(model="gpt-4o-mini", temperature=0) // if we are using openai
        # self.llm = llm_model or ChatMoonshot(model="kimi-k3", temperature=0) //if we are using kimi

        self.llm = llm_model or ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
        self.output_parser = StrOutputParser()
        
        # Define the strict instructions for the LLM
        self.prompt_template = PromptTemplate(
            template="""You are a highly analytical News Intelligence Agent. 
Your task is to synthesize a factual, unbiased news briefing based ONLY on the provided context.

Context Articles:
{context}

User Query: {question}

Trust Score Warning: {trust_score_warning}

Instructions:
1. Do not use outside knowledge. If the answer is not in the context, state that you do not have enough information.
2. Synthesize the different perspectives from the provided articles.
3. If there is a Trust Score warning, clearly state it at the very beginning of your briefing.

Briefing:""",
            input_variables=["context", "question", "trust_score_warning"]
        )

        # LangChain Expression Language (LCEL) Pipeline
        self.chain = self.prompt_template | self.llm | self.output_parser


    def generate_briefing(self, question: str, retrieved_articles: list, trust_score: int):
        """
        Takes the user's question, the articles from Ammu's ChromaDB, and Sudha's trust score,
        formats them, and runs the LLM chain.
        """
        # 1. Format the context text
        # Assuming Ammu's database returns a list of dictionaries containing 'title' and 'text'
        # Format the retrieved articles into a clean text block
        formatted_docs = []
        for idx, doc in enumerate(retrieved_articles, 1):
            if isinstance(doc, str):
                title = f"Article {idx}"
                content = doc
            elif isinstance(doc, dict):
                title = doc.get("title", f"Article {idx}")
                content = doc.get("text", doc.get("content", str(doc)))
            else:
                title = f"Article {idx}"
                content = str(doc)
                
            formatted_docs.append(f"--- {title} ---\n{content}")
            
        context_text = "\n\n".join(formatted_docs) if formatted_docs else "No relevant articles found."
        
        # 2. Mocking Sudha's Trust Engine Logic
        # If the score is low, we generate a warning string. If high, we leave it blank.
        warning = ""
        if trust_score < 5:
            warning = "WARNING: The following briefing is based on sources with highly contradictory reports."
            
        # 3. Invoke the LCEL Chain
        response = self.chain.invoke({
            "context": context_text,
            "question": question,
            "trust_score_warning": warning
        })
        
        return response