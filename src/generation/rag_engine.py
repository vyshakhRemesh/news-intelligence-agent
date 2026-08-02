from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.contradiction.contradiction_service import ContradictionService
from src.recommendation.trust_score import TrustScore
import logging
# We will use ChatOpenAI as a placeholder, but you can swap this for Anthropic, Llama 3, etc.
# from langchain_openai import ChatOpenAI  //for openai

# from langchain_moonshot import ChatMoonshot //for kimi

# --- 1. Import Groq instead of OpenAI ---
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)

class NewsGenerationEngine:
    def __init__(self, db = None,llm_model=None):
        """
        Initializes the RAG Engine and constructs the LCEL pipeline.
        """
        # Initialize the LLM (Defaults to OpenAI if none is provided)
        # self.llm = llm_model or ChatOpenAI(model="gpt-4o-mini", temperature=0) // if we are using openai
        # self.llm = llm_model or ChatMoonshot(model="kimi-k3", temperature=0) //if we are using kimi

        self.llm = llm_model or ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
        self.output_parser = StrOutputParser()
        self.db = db
        self.contradiction_service = ContradictionService(db=db)

        # Define the strict instructions for the LLM
        self.prompt_template = PromptTemplate(
    template="""You are a highly analytical News Intelligence Agent.
Your task is to synthesize a factual, unbiased news briefing based ONLY on the provided context.

Context Articles:
{context}

Contradiction Analysis:
{contradiction_context}

User Query: {question}

Trust Score Warning:
{trust_score_warning}

Previous Critic Feedback:
{critique_feedback}

Use this feedback only to improve the briefing.
Do NOT mention, summarize, or refer to the critic, the review process, revisions, previous drafts, or internal feedback in the final response.
Return only the final improved briefing.

Instructions:

1. Do not use outside knowledge. If the answer is not in the context, state that you do not have enough information.
2. Synthesize the different perspectives from the provided articles.
3. If there is a Trust Score warning, clearly state it at the beginning of your briefing.
4. Use the contradiction analysis to clearly explain disagreements between the articles.
5. Do not claim a contradiction unless it is marked as detected in the contradiction analysis.
6. If Previous Critic Feedback is not "None", revise the briefing by addressing every issue mentioned while preserving factual accuracy.
7. If Previous Critic Feedback is "None", generate the briefing normally.

Briefing:""",
   input_variables=[
        "context",
        "contradiction_context",
        "question",
        "trust_score_warning",
        "critique_feedback",
    ],
)

        # LangChain Expression Language (LCEL) Pipeline
        self.chain = self.prompt_template | self.llm | self.output_parser


    # **********************************
    def analyse_articles(self,retrieved_articles: list,contradiction_threshold: float = 0.70,):
        """
        Calculates trust scores, performs contradiction analysis,
        and prepares metadata for generation.
        """

        # Calculate trust score
        # for article in retrieved_articles:
        #     if isinstance(article, dict):
        #         article["trust_score"] = TrustScore.calculate(article)

        for article in retrieved_articles:

            if not isinstance(article, dict):
                continue

            # Reuse stored trust score if available
            if article.get("trust_score") is None:

                article["trust_score"] = TrustScore.calculate(article)
            else:
                logger.info(
                    "Using stored trust score %.2f for '%s'",
                    article["trust_score"],
                    article.get("title")
                )

        # trust_scores = [
        #     article.get("trust_score", 0)
        #     for article in retrieved_articles
        #     if isinstance(article, dict)
        # ]
        trust_scores = [
            article["trust_score"]
            for article in retrieved_articles
            if isinstance(article, dict)
            and article.get("trust_score") is not None
        ]

        average_trust_score = (
            sum(trust_scores) / len(trust_scores)
            if trust_scores
            else 0
        )

        contradiction_result = (
            self.contradiction_service
            .analyse_against_most_trusted(
                articles=retrieved_articles,
                threshold=contradiction_threshold,
                save_results=True,
            )
        )

        warnings = []

        if average_trust_score < 70:
            warnings.append(
                "WARNING: Some retrieved articles are from sources with low credibility scores."
            )

        if contradiction_result.get("contradiction_count", 0) > 0:
            warnings.append(
                f"WARNING: The retrieved articles contain "
                f"{contradiction_result['contradiction_count']} potentially contradictory report(s)."
            )

        return {
            "articles": retrieved_articles,
            "trust_warning": "\n".join(warnings),
            "average_trust_score": average_trust_score,
            "contradiction_result": contradiction_result,
        }
    # ***********************************

    def build_context(self,analysed_result: dict,):
        """
        Converts analysed articles into prompt-ready context.
        """

        formatted_docs = []

        for idx, doc in enumerate(analysed_result["articles"], start=1):

            if isinstance(doc, str):
                title = f"Article {idx}"
                content = doc

            elif isinstance(doc, dict):
                title = doc.get("title", f"Article {idx}")
                content = doc.get(
                    "text",
                    doc.get("content", "")
                )

            else:
                title = f"Article {idx}"
                content = str(doc)

            formatted_docs.append(
                f"--- {title} ---\n{content}"
            )

        context_text = (
            "\n\n".join(formatted_docs)
            if formatted_docs
            else "No relevant articles found."
        )

        contradiction_context = (
            self._format_contradiction_comparisons(
                analysed_result["contradiction_result"]
            )
        )

        return {
            "context": context_text,
            "contradiction_context": contradiction_context,
            "trust_warning": analysed_result["trust_warning"],
        }

    # ************************************

    @staticmethod
    def _format_contradiction_comparisons(
        contradiction_result: dict,
    ) -> str:
        reference = contradiction_result.get(
            "reference_article"
        )

        if not reference:
            return "No reference article was available."

        lines = [
            (
                "Most trusted reference article: "
                f"{reference['title']} "
                f"(trust score: {reference['trust_score']})"
            )
        ]

        comparisons = contradiction_result.get(
            "comparisons",
            [],
        )

        for comparison in comparisons:
            status = (
                "Contradiction detected"
                if comparison["is_contradiction"]
                else "No contradiction detected"
            )

            lines.append(
                f"- Compared with "
                f"{comparison['compared_article_title']}: "
                f"contradiction score "
                f"{comparison['contradiction_score']:.4f}; "
                f"{status}."
            )

        return "\n".join(lines)
    
    # def generate_briefing(
    # self,
    # question: str,
    # retrieved_articles: list,
    # contradiction_threshold: float = 0.70,
    # ):
    #     """
    #     Formats retrieved articles, evaluates source credibility,
    #     detects contradictions, and generates a briefing.
    #     """

    #     formatted_docs = []

    #     for idx, doc in enumerate(retrieved_articles, 1):
    #         if isinstance(doc, str):
    #             title = f"Article {idx}"
    #             content = doc

    #         elif isinstance(doc, dict):
    #             title = doc.get("title", f"Article {idx}")
    #             content = doc.get(
    #                 "text",
    #                 doc.get("content", str(doc)),
    #             )

    #         else:
    #             title = f"Article {idx}"
    #             content = str(doc)

    #         formatted_docs.append(
    #             f"--- {title} ---\n{content}"
    #         )

    #     context_text = (
    #         "\n\n".join(formatted_docs)
    #         if formatted_docs
    #         else "No relevant articles found."
    #     )

    #     # Calculate and attach trust score to every article
    #     for article in retrieved_articles:
    #         if isinstance(article, dict):
    #             article["trust_score"] = TrustScore.calculate(article)

    #     # Use the calculated trust scores
    #     trust_scores = [
    #         article.get("trust_score", 0)
    #         for article in retrieved_articles
    #         if isinstance(article, dict)
    #     ]

    #     average_trust_score = (
    #         sum(trust_scores) / len(trust_scores)
    #         if trust_scores
    #         else 0
    #     )

    #     contradiction_result = (
    #         self.contradiction_service
    #         .analyse_against_most_trusted(
    #             articles=retrieved_articles,
    #             threshold=contradiction_threshold,
    #             save_results=True,
    #         )
    #     )

    #     contradiction_context = (
    #         self._format_contradiction_comparisons(
    #             contradiction_result
    #         )
    #     )

    #     reference = contradiction_result.get(
    #         "reference_article"
    #     )

    #     if reference:
    #         logger.info(
    #             "Most trusted reference article: %s "
    #             "| Trust score: %s",
    #             reference["title"],
    #             reference["trust_score"],
    #         )

    #     for comparison in contradiction_result.get(
    #         "comparisons",
    #         [],
    #     ):
    #         logger.info(
    #             "Reference: %s | Compared with: %s | "
    #             "Contradiction: %.4f | "
    #             "Entailment: %.4f | Neutral: %.4f | "
    #             "Detected: %s",
    #             comparison["reference_article_title"],
    #             comparison["compared_article_title"],
    #             comparison["contradiction_score"],
    #             comparison["entailment_score"],
    #             comparison["neutral_score"],
    #             comparison["is_contradiction"],
    #         )

    #     logger.info(
    #         "Contradiction result: %s",
    #         contradiction_result,
    #     )

    #     logger.info(
    #         "Contradiction count: %s",
    #         contradiction_result.get("contradiction_count", 0)
    #     )

    #     comparisons = contradiction_result.get(
    #         "comparisons",
    #         [],
    #     )

    #     detected_contradictions = [
    #         comparison
    #         for comparison in comparisons
    #         if comparison["is_contradiction"]
    #     ]

    #     if not detected_contradictions:
    #         logger.info(
    #             "No contradictions exceeded threshold %.2f",
    #             contradiction_threshold,
    #         )
    #     else:
    #         for index, comparison in enumerate(
    #             detected_contradictions,
    #             start=1,
    #         ):
    #             logger.info(
    #                 "Contradiction %d:",
    #                 index,
    #             )

    #             logger.info(
    #                 "   Reference article: %s",
    #                 comparison.get(
    #                     "reference_article_title",
    #                     "Untitled",
    #                 ),
    #             )

    #             logger.info(
    #                 "   Compared article: %s",
    #                 comparison.get(
    #                     "compared_article_title",
    #                     "Untitled",
    #                 ),
    #             )

    #             logger.info(
    #                 "   Contradiction score: %.4f",
    #                 comparison.get(
    #                     "contradiction_score",
    #                     0.0,
    #                 ),
    #             )

    #     warnings = []

    #     if average_trust_score < 70:
    #         warnings.append(
    #             "WARNING: Some retrieved articles are from "
    #             "sources with low credibility scores."
    #         )

    #     if contradiction_result["contradiction_count"] > 0:
    #         warnings.append(
    #             "WARNING: The retrieved articles contain "
    #             f"{contradiction_result['contradiction_count']} "
    #             "potentially contradictory report(s)."
    #         )

    #     warning = "\n".join(warnings)

    #     response = self.chain.invoke({
    #         "context": context_text,
    #         "contradiction_context": contradiction_context,
    #         "question": question,
    #         "trust_score_warning": warning,
    #     })

    #     return response

    # *************************************

    def generate_briefing(
        self,
        question: str,
        retrieved_articles: list,
        critique_feedback: str = "",
        contradiction_threshold: float = 0.70,):
        """
        Generates a news briefing using analysed articles.
        """

        analysed = self.analyse_articles(
            retrieved_articles=retrieved_articles,
            contradiction_threshold=contradiction_threshold,
        )

        prompt_context = self.build_context(analysed)

        feedback_text = (
            critique_feedback
            if critique_feedback
            else "None"
        )

        # response = self.chain.invoke({
        #     "context": prompt_context["context"],
        #     "contradiction_context": prompt_context["contradiction_context"],
        #     "question": question,
        #     "trust_score_warning": prompt_context["trust_warning"],
        # })

        response = self.chain.invoke({
            "context": prompt_context["context"],
            "contradiction_context": prompt_context["contradiction_context"],
            "question": question,
            "trust_score_warning": prompt_context["trust_warning"],
            "critique_feedback": feedback_text,
        })

        return response

    # ***************************************