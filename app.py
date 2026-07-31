import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re
import random
import time
import hashlib
from src.database.connection import SessionLocal, init_db
from src.database.models import User

st.set_page_config(page_title="InsightNews AI Portal", page_icon="📰", layout="wide", initial_sidebar_state="expanded")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def user_to_dict(user: User):
    return {
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "interests": user.interests or [],
        "auth_provider": user.auth_provider,
        "bookmarks": user.bookmarks or [],
    }

# One-time DB init + seed default accounts
if "db_initialized" not in st.session_state:
    try:
        init_db()
        db = SessionLocal()
        if db.query(User).count() == 0:
            db.add(User(
                email="admin@news.com",
                name="System Admin",
                role="admin",
                auth_provider="Password",
                interests=["All"],
                bookmarks=[],
                password_hash=hash_password("admin")
            ))
            db.add(User(
                email="user@example.com",
                name="Jane Doe",
                role="user",
                auth_provider="Google",
                interests=["Technology", "AI & ML", "Finance"],
                bookmarks=[],
                password_hash=None
            ))
            db.commit()
        db.close()
        st.session_state.db_initialized = True
    except Exception as e:
        st.error(f"Database initialization failed: {e}")

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "current_user" not in st.session_state: st.session_state.current_user = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "bookmarks" not in st.session_state: st.session_state.bookmarks = []
if "selected_article" not in st.session_state: st.session_state.selected_article = None
if "do_reset" not in st.session_state: st.session_state.do_reset = False
if "daily_briefings" not in st.session_state: st.session_state.daily_briefings = []
if "agent_logs" not in st.session_state: st.session_state.agent_logs = []
if "qa_pipeline_visible" not in st.session_state: st.session_state.qa_pipeline_visible = False
if "last_briefing" not in st.session_state: st.session_state.last_briefing = None
if "platform_agent_running" not in st.session_state: st.session_state.platform_agent_running = False
if "qa_agent_state" not in st.session_state: st.session_state.qa_agent_state = {}

MOCK_NEWS = [
    {"id": 1, "title": "Global AI Safety Accord Signed by 28 Countries", "category": "AI & ML", "trust_score": 96, "source": "Reuters", "date": "2026-07-28", "summary": "Major tech nations agreed on baseline standards for auditing high-risk artificial intelligence models before public release.", "contradictions": ["Source B claims the agreement lacks legally binding enforcement mechanisms and relies on voluntary disclosures.", "Tech Lobby Groups argue the guidelines will disproportionately penalize open-source developers."], "sentiment": "positive", "reading_time": 4, "views": 12400},
    {"id": 2, "title": "Breakthrough in Quantum Battery Density Achieved in Lab Trials", "category": "Technology", "trust_score": 88, "source": "MIT Tech Review", "date": "2026-07-27", "summary": "Researchers demonstrated a prototype charging mechanism that achieves full charge in under two minutes with minimal degradation.", "contradictions": ["Independent physicists state the synthesis costs currently exceed commercial viability by 300%.", "Competing labs report thermal runway issues during continuous fast-charging tests."], "sentiment": "positive", "reading_time": 6, "views": 8900},
    {"id": 3, "title": "Next-Gen Semiconductor Fab to Begin Construction in Arizona", "category": "Technology", "trust_score": 91, "source": "Bloomberg", "date": "2026-07-26", "summary": "A $40 billion investment aims to produce 2nm chips by 2028, reshaping the global semiconductor supply chain.", "contradictions": ["Labor unions warn of potential worker shortages and wage suppression in the region.", "Environmental groups cite water consumption concerns in the drought-prone state."], "sentiment": "neutral", "reading_time": 5, "views": 10200},
    {"id": 4, "title": "Major Cyberattack Exposes Vulnerabilities in Critical Infrastructure", "category": "Technology", "trust_score": 94, "source": "BBC News", "date": "2026-07-25", "summary": "A coordinated ransomware attack targeted energy grids across Eastern Europe, prompting emergency response protocols.", "contradictions": ["Government officials downplay the severity, claiming no lasting damage to core systems.", "Security researchers report the breach had been active for over 8 months undetected."], "sentiment": "negative", "reading_time": 7, "views": 15600},
    {"id": 5, "title": "SpaceX Starship Successfully Completes Orbital Refueling Test", "category": "Technology", "trust_score": 89, "source": "The Verge", "date": "2026-07-24", "summary": "The successful demonstration marks a critical milestone for NASA's Artemis lunar landing missions planned for 2027.", "contradictions": ["Aerospace analysts question the cost-efficiency compared to traditional rocket architectures.", "Former NASA officials express concerns about crew safety protocols during refueling."], "sentiment": "positive", "reading_time": 5, "views": 11300},
    {"id": 6, "title": "Central Banks Announce Next-Gen Digital Currency Framework", "category": "Finance", "trust_score": 92, "source": "Financial Times", "date": "2026-07-29", "summary": "A unified cross-border payment protocol for CBDCs has been introduced to streamline global trade settlements.", "contradictions": ["Privacy Advocates warn the protocol enables full transactional oversight and reduces anonymous spending options.", "Commercial banks argue this will shrink institutional deposit reserves."], "sentiment": "neutral", "reading_time": 6, "views": 9800},
    {"id": 7, "title": "Federal Reserve Signals Potential Rate Cut in September", "category": "Finance", "trust_score": 95, "source": "Wall Street Journal", "date": "2026-07-28", "summary": "Minutes from the latest FOMC meeting suggest easing inflation pressures may open the door for monetary loosening.", "contradictions": ["Some economists argue inflation remains sticky in the services sector and caution against premature cuts.", "Market analysts predict a 50bps cut, double what the Fed is hinting at."], "sentiment": "positive", "reading_time": 4, "views": 14200},
    {"id": 8, "title": "Cryptocurrency Markets Rally as ETF Inflows Reach Record Highs", "category": "Finance", "trust_score": 82, "source": "CoinDesk", "date": "2026-07-27", "summary": "Bitcoin and Ethereum saw double-digit percentage gains as institutional investment vehicles absorbed record capital.", "contradictions": ["Regulatory experts warn that pending SEC lawsuits could invalidate recent ETF approvals.", "Traditional finance critics label the rally as speculative bubble behavior."], "sentiment": "positive", "reading_time": 5, "views": 8700},
    {"id": 9, "title": "Global Banking Regulators Propose Stricter Capital Requirements", "category": "Finance", "trust_score": 93, "source": "Reuters", "date": "2026-07-26", "summary": "Basel III amendments would force systemically important banks to hold 25% more Tier 1 capital against operational risks.", "contradictions": ["Banking associations claim the rules will reduce lending capacity and slow economic growth.", "Consumer advocates argue the requirements are still insufficient to prevent taxpayer bailouts."], "sentiment": "neutral", "reading_time": 6, "views": 7600},
    {"id": 10, "title": "Asian Markets Dip on Manufacturing Slowdown Fears", "category": "Finance", "trust_score": 87, "source": "Nikkei Asia", "date": "2026-07-25", "summary": "Preliminary PMI data from China and South Korea fell below consensus expectations, triggering regional sell-offs.", "contradictions": ["Government spokespeople characterize the data as a temporary seasonal adjustment.", "Supply chain experts see the slowdown as structural rather than cyclical."], "sentiment": "negative", "reading_time": 4, "views": 6900},
    {"id": 11, "title": "New Public Health Guidelines Issued for Urban Air Quality", "category": "Health", "trust_score": 84, "source": "World Health Organization", "date": "2026-07-25", "summary": "Updated safety thresholds for microparticles aim to reduce respiratory complications in densely populated metropolitan areas.", "contradictions": ["Industrial associations argue implementation deadlines are unrealistic for manufacturing hubs.", "Environmental NGOs contend the new limits remain too lenient compared to climate science recommendations."], "sentiment": "neutral", "reading_time": 5, "views": 9200},
    {"id": 12, "title": "mRNA Vaccine Technology Shows Promise Against Pancreatic Cancer", "category": "Health", "trust_score": 90, "source": "Nature Medicine", "date": "2026-07-24", "summary": "Phase II trial results indicate a 40% reduction in tumor progression for patients receiving the personalized vaccine.", "contradictions": ["Oncologists caution that Phase II results often fail to replicate in larger Phase III trials.", "Patient advocacy groups highlight the extreme cost, estimated at $450,000 per treatment course."], "sentiment": "positive", "reading_time": 7, "views": 13500},
    {"id": 13, "title": "Mental Health Apps Face Scrutiny Over Data Privacy Practices", "category": "Health", "trust_score": 86, "source": "The Guardian", "date": "2026-07-23", "summary": "A joint FTC-EU investigation found that several popular therapy apps shared user metadata with third-party advertisers.", "contradictions": ["App developers claim anonymization protocols prevent individual identification.", "Digital rights researchers demonstrate re-identification attacks using the shared datasets."], "sentiment": "negative", "reading_time": 5, "views": 8100},
    {"id": 14, "title": "Study Links Intermittent Fasting to Longevity Markers in Adults", "category": "Health", "trust_score": 79, "source": "Healthline", "date": "2026-07-22", "summary": "A 5-year longitudinal study suggests time-restricted eating correlates with improved cellular autophagy indicators.", "contradictions": ["Nutritionists warn the study did not control for overall caloric intake, a confounding variable.", "Eating disorder specialists express concern about fasting trends among adolescents."], "sentiment": "positive", "reading_time": 4, "views": 10500},
    {"id": 15, "title": "G7 Summit Concludes with Defense Spending Agreement", "category": "Politics", "trust_score": 94, "source": "Associated Press", "date": "2026-07-28", "summary": "Member nations committed to allocating 3% of GDP toward collective security initiatives by 2030.", "contradictions": ["Opposition parties in multiple nations vow to block the budget increases in parliamentary votes.", "Peace advocacy groups argue the spending prioritizes militarization over climate finance."], "sentiment": "neutral", "reading_time": 6, "views": 11800},
    {"id": 16, "title": "Supreme Court Ruling Expands Digital Privacy Protections", "category": "Politics", "trust_score": 93, "source": "Washington Post", "date": "2026-07-26", "summary": "The 6-3 decision requires law enforcement to obtain warrants for all cloud-stored data regardless of server location.", "contradictions": ["Law enforcement agencies warn the ruling will hamper cross-border criminal investigations.", "Tech companies praise the decision but note compliance costs could reach billions."], "sentiment": "positive", "reading_time": 7, "views": 13200},
    {"id": 17, "title": "Border Security Bill Stalls in Senate Amid Partisan Dispute", "category": "Politics", "trust_score": 88, "source": "Politico", "date": "2026-07-24", "summary": "Negotiations collapsed over provisions related to asylum processing timelines, delaying action until the fall session.", "contradictions": ["Republican leadership blames the administration for refusing to reinstate previous detention policies.", "Democratic negotiators cite GOP demands for automatic deportation as a non-starter."], "sentiment": "negative", "reading_time": 5, "views": 9500},
    {"id": 18, "title": "James Webb Telescope Detects Potential Biosignatures on Exoplanet K2-18b", "category": "Science", "trust_score": 91, "source": "NASA", "date": "2026-07-27", "summary": "Spectroscopic analysis reveals dimethyl sulfide in the planet's atmosphere, a molecule strongly associated with biological activity on Earth.", "contradictions": ["Astrobiologists urge caution, noting abiotic processes could theoretically produce the same signature.", "Some researchers question whether the signal-to-noise ratio is sufficient for such claims."], "sentiment": "positive", "reading_time": 8, "views": 18900},
    {"id": 19, "title": "Fusion Energy Experiment Sustains Reaction for 45 Minutes", "category": "Science", "trust_score": 89, "source": "Science Magazine", "date": "2026-07-25", "summary": "The Korean KSTAR tokamak achieved a new record, generating net-positive energy output during the sustained burn.", "contradictions": ["Engineers note the reactor lining sustained significant neutron damage, raising maintenance concerns.", "Energy economists calculate that commercial viability remains at least 20 years away."], "sentiment": "positive", "reading_time": 6, "views": 14400},
    {"id": 20, "title": "Oceanographers Document Unprecedented Atlantic Current Slowdown", "category": "Science", "trust_score": 90, "source": "Nature", "date": "2026-07-23", "summary": "New buoy data indicates the Atlantic Meridional Overturning Circulation has weakened by 25% since 2020.", "contradictions": ["Climate modelers debate whether the slowdown is permanent or part of multi-decadal variability.", "Fishing industry representatives dispute the methodology of the buoy measurements."], "sentiment": "negative", "reading_time": 7, "views": 11200},
    {"id": 21, "title": "Renewable Energy Surpasses Coal in Global Electricity Generation", "category": "Climate", "trust_score": 87, "source": "IEA", "date": "2026-07-26", "summary": "For the first time, solar and wind combined accounted for 38% of global power output in Q2 2026.", "contradictions": ["Grid operators warn that intermittency issues require massive battery investments not yet budgeted.", "Coalition industry reports claim the data excludes captive coal plants powering industrial facilities."], "sentiment": "positive", "reading_time": 5, "views": 10100},
    {"id": 22, "title": "Arctic Temperatures Hit Record Highs for Third Consecutive Year", "category": "Climate", "trust_score": 92, "source": "NOAA", "date": "2026-07-24", "summary": "Satellite measurements show average polar temperatures 4.2C above the 1991-2020 baseline, accelerating ice loss.", "contradictions": ["Climate skeptics point to a single cold weather station in Greenland as evidence of data inconsistency.", "Shipping companies quietly celebrate longer navigable seasons through Arctic routes."], "sentiment": "negative", "reading_time": 6, "views": 12800},
    {"id": 23, "title": "Open-Source LLM Surpasses GPT-5 on Standardized Reasoning Benchmarks", "category": "AI & ML", "trust_score": 85, "source": "Hugging Face", "date": "2026-07-27", "summary": "The community-trained model demonstrates superior performance in mathematical reasoning while requiring 90% less compute.", "contradictions": ["Critics note the benchmark may have been contaminated by training data overlap.", "Enterprise users report the model underperforms on domain-specific legal and medical tasks."], "sentiment": "positive", "reading_time": 5, "views": 9900},
    {"id": 24, "title": "EU AI Act Enforcement Begins with Major Platform Audits", "category": "AI & ML", "trust_score": 93, "source": "EURACTIV", "date": "2026-07-25", "summary": "Regulators initiated compliance reviews of recommendation algorithms at five major social media companies.", "contradictions": ["Affected companies claim the audit criteria are ambiguous and inconsistently applied.", "Digital rights groups argue the Act does not go far enough in banning biometric surveillance."], "sentiment": "neutral", "reading_time": 6, "views": 8400},
]

ALL_INTEREST_TOPICS = ["Technology", "AI & ML", "Finance", "Health", "Politics", "Climate", "Science"]

# -----------------------------------------------------------------------------
# 3. CHATBOT INTELLIGENCE ENGINE
# -----------------------------------------------------------------------------

def detect_query_intent(query: str) -> dict:
    q = query.lower().strip()
    greetings = ['hello', 'hi', 'hey', 'greetings', 'good morning', 'good afternoon', 'good evening', 'howdy']
    identity_qs = ['who are you', 'what are you', 'what can you do', 'what do you do', 'your name', 'introduce yourself', 'how do you work', 'what is insightnews']
    thanks = ['thank', 'thanks', 'appreciate', 'grateful']
    goodbye = ['bye', 'goodbye', 'see you', 'later', 'cya']
    jokes = ['joke', 'funny', 'humor', 'laugh', 'bored']
    help_qs = ['help', 'assist', 'guide', 'how to use', 'how does this work', 'what should i ask']
    trending_keywords = ['trending', 'trend', 'top news', 'top stories', 'headlines', 'latest', 'whats happening', 'today', 'this week', 'current events', 'breaking', 'news', 'happening', 'update']
    contradiction_keywords = ['contradict', 'conflict', 'disagree', 'opposing', 'counter', 'dispute', 'debate', 'controversy', 'different views', 'opposite', 'both sides', 'argument']
    summary_keywords = ['summarize', 'summary', 'brief', 'overview', 'roundup', 'recap', 'digest']
    trust_qs = ['trust', 'credibility', 'reliable', 'fake news', 'veracity', 'score']
    return {
        'is_greeting': any(g in q for g in greetings),
        'is_identity': any(iq in q for iq in identity_qs),
        'is_thanks': any(t in q for t in thanks),
        'is_goodbye': any(g in q for g in goodbye),
        'is_joke': any(j in q for j in jokes),
        'is_help': any(h in q for h in help_qs),
        'is_trending': any(kw in q for kw in trending_keywords),
        'is_contradiction': any(kw in q for kw in contradiction_keywords),
        'is_summary': any(kw in q for kw in summary_keywords),
        'is_trust': any(t in q for t in trust_qs),
        'is_specific': not any([any(g in q for g in greetings), any(iq in q for iq in identity_qs), any(t in q for t in thanks), any(g in q for g in goodbye), any(j in q for j in jokes), any(h in q for h in help_qs)])
    }


def get_conversational_response(query: str, intent: dict) -> str:
    q = query.lower().strip()
    if intent['is_greeting']:
        greetings = [
            "Hello! I am your InsightNews AI Assistant. I can help you with today's news, analyze contradictions between sources, check trust scores, or just chat. What would you like to know?",
            "Hey there! Welcome to InsightNews. I am here to help you navigate the news landscape, spot contradictions, and find trustworthy reporting. What is on your mind?",
            "Hi! I am your news intelligence companion. Ask me about trending topics, conflicting reports, or anything else — I will do my best to help!"
        ]
        return random.choice(greetings)
    if intent['is_identity']:
        return "I am **InsightNews AI**, your personal news intelligence assistant. I can find trending stories, detect contradictions between sources, score article credibility, and synthesize briefings from verified feeds. Just ask me anything!"
    if intent['is_thanks']:
        return random.choice(["You are welcome! Feel free to ask if you need anything else.", "Happy to help! Let me know if you want to dive deeper into any topic.", "Anytime! I am here 24/7 for your news intelligence needs."])
    if intent['is_goodbye']:
        return random.choice(["Goodbye! Stay informed and stay curious.", "See you later! Come back anytime for your news briefing.", "Bye for now! The news never stops, and neither do I."])
    if intent['is_joke']:
        jokes = [
            "Why did the journalist bring a ladder to the newsroom? Because they wanted to get to the top of the story!",
            "I asked my AI friend for news about electricity. They said it was shocking.",
            "Why don't secrets last long in the newspaper industry? Because every issue has a leak!",
            "I tried to write a story about a broken pencil... but it was pointless."
        ]
        return random.choice(jokes)
    if intent['is_help']:
        return "Here are some things you can ask me:\n\n**News & Discovery:**\n• What is trending today?\n• Show me the latest in AI and technology\n• Give me a summary of finance news\n\n**Contradictions & Analysis:**\n• What are the contradictions in the AI Safety Accord?\n• Show me opposing views on cryptocurrency\n\n**Trust & Credibility:**\n• How is trust score calculated?\n• Which sources are most reliable?\n\n**General:**\n• Hello / Who are you?\n• Tell me a joke"
    if intent['is_trust'] and not intent['is_trending'] and not intent['is_contradiction']:
        return "**Trust Scoring Explained** — Our trust scores are calculated based on: (1) Source Reputation — Reuters (98%), BBC (96%), Nature (99%), (2) Content Completeness — metadata, author info, word count, (3) Freshness — recent articles get a boost, (4) Cross-Reference Verification — corroborated by multiple sources scores higher, (5) Contradiction Penalty — contradicted by higher-trust sources lowers score. Score ranges: 90-100% Highly credible, 80-89% Credible but monitor, Below 80% Exercise caution."
    return None


def retrieve_relevant_articles(query: str, top_k: int = 3):
    query_lower = query.lower().strip()
    scored = []
    intent = detect_query_intent(query)
    if not intent['is_specific'] and not intent['is_trending'] and not intent['is_contradiction'] and not intent['is_summary'] and not intent['is_trust']:
        return []
    for article in MOCK_NEWS:
        score = 0
        text = f"{article['title']} {article['summary']} {article['category']}".lower()
        if query_lower in text:
            score += 15
        query_words = set(re.findall(r'\w+', query_lower))
        text_words = set(re.findall(r'\w+', text))
        overlap = len(query_words & text_words)
        score += overlap * 3
        for topic in ALL_INTEREST_TOPICS:
            if topic.lower() in query_lower and article['category'].lower() == topic.lower():
                score += 8
        if intent['is_trending'] or intent['is_summary']:
            try:
                article_date = datetime.strptime(article['date'], '%Y-%m-%d')
                days_old = (datetime(2026, 7, 30) - article_date).days
                score += max(0, 10 - days_old)
            except:
                score += 5
            score += article.get('views', 0) // 5000
            score += article['trust_score'] // 20
        if intent['is_contradiction'] and article['contradictions']:
            score += 10 + len(article['contradictions']) * 3
        topic_keywords = {
            'ai': ['ai', 'artificial intelligence', 'machine learning', 'llm', 'gpt', 'neural', 'algorithm'],
            'tech': ['tech', 'technology', 'quantum', 'chip', 'semiconductor', 'cyber', 'space', 'battery'],
            'finance': ['finance', 'money', 'bank', 'stock', 'market', 'crypto', 'bitcoin', 'fed', 'economy', 'trade'],
            'health': ['health', 'medical', 'vaccine', 'disease', 'hospital', 'mental', 'fitness', 'diet'],
            'politics': ['politic', 'government', 'election', 'vote', 'senate', 'court', 'law', 'policy', 'defense'],
            'climate': ['climate', 'environment', 'green', 'carbon', 'renewable', 'solar', 'warming', 'arctic'],
            'science': ['science', 'space', 'planet', 'fusion', 'research', 'telescope', 'ocean', 'physics']
        }
        for topic, keywords in topic_keywords.items():
            if any(kw in query_lower for kw in keywords):
                if article['category'].lower() in topic or any(kw in text for kw in keywords):
                    score += 5
        if score > 0:
            scored.append((score, article))
    if not scored and (intent['is_trending'] or intent['is_summary']):
        for article in MOCK_NEWS:
            try:
                article_date = datetime.strptime(article['date'], '%Y-%m-%d')
                days_old = (datetime(2026, 7, 30) - article_date).days
                recency_score = max(0, 10 - days_old)
            except:
                recency_score = 5
            composite = recency_score + article.get('views', 0) // 3000 + article['trust_score'] // 15
            scored.append((composite, article))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [article for _, article in scored[:top_k]]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [article for _, article in scored[:top_k]]


def generate_rag_response(query: str, retrieved_articles: list) -> str:
    query_lower = query.lower().strip()
    intent = detect_query_intent(query)
    convo_response = get_conversational_response(query, intent)
    if convo_response and not retrieved_articles:
        return convo_response
    if not retrieved_articles:
        fallbacks = [
            f"I do not see any specific articles matching '{query}' in our current feed. But I can still help! Try asking about:",
            f"Hmm, I could not find direct matches for '{query}' right now. Here are some topics I cover well:",
            f"No exact matches for '{query}' in today's feed. Want to explore these areas instead?"
        ]
        fallback = random.choice(fallbacks)
        topics = "• **Technology & AI** — Quantum computing, AI safety, cybersecurity\n• **Finance** — CBDCs, crypto, Fed policy, markets\n• **Health** — Vaccines, mental health, medical breakthroughs\n• **Politics** — Elections, policy, international relations\n• **Climate** — Renewable energy, Arctic warming, emissions\n• **Science** — Space exploration, fusion energy, oceanography"
        return f"{fallback}\n\n{topics}\n\nOr just say **hello** or **what can you do** to learn more about me!"
    context_parts = []
    contradiction_notes = []
    trust_warnings = []
    for idx, article in enumerate(retrieved_articles, 1):
        context_parts.append(f"[{idx}] {article['title']} (Source: {article['source']}, Trust: {article['trust_score']}%)")
        context_parts.append(f"    Summary: {article['summary']}")
        if article['contradictions']:
            contradiction_notes.append(f"Article '{article['title']}' has {len(article['contradictions'])} reported counter-perspective(s).")
        if article['trust_score'] < 85:
            trust_warnings.append(f"Note: {article['title']} has a moderate trust score ({article['trust_score']}%)")
    response_lines = []
    if intent['is_contradiction']:
        response_lines.append("Based on the retrieved reports, here is the contradiction analysis:")
    elif intent['is_trending']:
        response_lines.append(f"Trending News Briefing — Here are the top {len(retrieved_articles)} stories from our high-trust feeds:")
    elif intent['is_summary']:
        response_lines.append(f"News Summary — Synthesized from {len(retrieved_articles)} verified sources:")
    elif intent['is_trust']:
        response_lines.append("Here is the trust and credibility analysis for the retrieved articles:")
    else:
        response_lines.append(f"Based on {len(retrieved_articles)} retrieved high-trust articles, here is what I found:")
    response_lines.append("")
    for article in retrieved_articles:
        response_lines.append(f"• **{article['title']}** — {article['summary']}")
    if contradiction_notes and intent['is_contradiction']:
        response_lines.append("\n**Contradiction & Counter-Perspective Analysis:**")
        for note in contradiction_notes:
            response_lines.append(f"- {note}")
        response_lines.append("\n**Key Counter-Claims:**")
        seen_contras = set()
        for article in retrieved_articles:
            for contra in article['contradictions']:
                if contra not in seen_contras:
                    response_lines.append(f"• {contra}")
                    seen_contras.add(contra)
    if trust_warnings:
        response_lines.append("\n**Trust Score Advisory:**")
        for warning in trust_warnings:
            response_lines.append(f"- {warning}")
    sources = list(set(a['source'] for a in retrieved_articles))
    if len(sources) > 1:
        response_lines.append(f"\n*Sources referenced: {', '.join(sources)}*")
    response_lines.append("\n*This briefing is synthesized exclusively from the retrieved context articles. No external knowledge was used.*")
    return "\n".join(response_lines)

# -----------------------------------------------------------------------------
# 4. AGENT FLOW VISUALIZATION HELPERS
# -----------------------------------------------------------------------------

def render_flow_step(number: int, title: str, status: str, detail: str = "", icon: str = ""):
    """Render a single step in an agent pipeline flow."""
    colors = {"pending": "#555", "running": "#0099FF", "complete": "#00C853", "error": "#FF5252"}
    color = colors.get(status, "#555")
    icons = {"pending": "○", "running": "◐", "complete": "✓", "error": "✗"}
    status_icon = icons.get(status, "○")
    st.markdown(f"""
    <div style="display:flex;align-items:flex-start;margin-bottom:8px;padding:10px;border-left:3px solid {color};background:rgba(0,0,0,0.2);border-radius:0 8px 8px 0;">
        <div style="min-width:28px;font-size:18px;color:{color};font-weight:bold;">{status_icon}</div>
        <div style="flex:1;">
            <div style="font-weight:600;color:#E0E0E0;">{number}. {title}</div>
            {f'<div style="font-size:12px;color:#888;margin-top:2px;">{detail}</div>' if detail else ''}
        </div>
        <div style="font-size:11px;color:{color};text-transform:uppercase;">{status}</div>
    </div>
    """, unsafe_allow_html=True)


def render_pipeline_connector():
    st.markdown("<div style='width:2px;height:16px;background:#444;margin-left:13px;'></div>", unsafe_allow_html=True)


def simulate_platform_agent_pipeline(user_prefs: list) -> dict:
    """Simulate the Platform Agent pipeline from platform_agent.py."""
    pipeline = {
        "steps": [],
        "articles": [],
        "briefing": "",
        "saved": False,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    # Step 1: Retrieve User Preferences
    pipeline["steps"].append({"name": "Retrieve User Preferences", "status": "complete", "detail": f"Preferences: {', '.join(user_prefs)}"})
    # Step 2: PostgreSQL Personalized Retrieval
    articles = [a for a in MOCK_NEWS if a["category"] in user_prefs or "All" in user_prefs]
    articles.sort(key=lambda x: x["trust_score"], reverse=True)
    pipeline["articles"] = articles[:5]
    pipeline["steps"].append({"name": "PostgreSQL Personalized Retrieval", "status": "complete", "detail": f"Retrieved {len(pipeline['articles'])} articles matching preferences"})
    # Step 3: NewsGenerationEngine (Groq/Llama simulation)
    context = "\n\n".join([f"Title: {a['title']}\nSource: {a['source']}\nContent: {a['summary']}" for a in pipeline["articles"]])
    pipeline["steps"].append({"name": "NewsGenerationEngine (Groq Llama-3.3-70b)", "status": "complete", "detail": "Synthesizing personalized briefing from retrieved context"})
    # Step 4: Critic / Reflection
    pipeline["steps"].append({"name": "Critic / Reflection", "status": "complete", "detail": "Evaluating factual consistency and source diversity"})
    # Step 5: Save Daily Briefing
    briefing = f"**Your Daily Briefing — {datetime.now().strftime('%B %d, %Y')}**\n\n"
    briefing += f"Based on your interests in **{', '.join(user_prefs)}**, here are the top stories today:\n\n"
    for idx, article in enumerate(pipeline["articles"], 1):
        briefing += f"{idx}. **{article['title']}** ({article['source']}, Trust: {article['trust_score']}%)\n   {article['summary']}\n\n"
    if any(a['contradictions'] for a in pipeline["articles"]):
        briefing += "**Contradictions Detected:**\n"
        for article in pipeline["articles"]:
            if article['contradictions']:
                briefing += f"• *{article['title']}* has {len(article['contradictions'])} opposing viewpoint(s).\n"
    pipeline["briefing"] = briefing
    pipeline["steps"].append({"name": "Save Daily Briefing", "status": "complete", "detail": "Saved to PostgreSQL DailyBriefings table"})
    # Step 6: Delivery
    pipeline["steps"].append({"name": "Email / App Notification / API", "status": "complete", "detail": "Briefing queued for delivery channels"})
    pipeline["saved"] = True
    return pipeline


def simulate_qa_agent_pipeline(query: str, retrieved: list) -> dict:
    """Simulate the Q&A Agent pipeline from the second image."""
    pipeline = {
        "steps": [],
        "query": query,
        "retrieved": retrieved,
        "generated_answer": "",
        "critic_feedback": "",
        "final_answer": "",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }
    # Step 1: User Ask Question
    pipeline["steps"].append({"name": "User Ask Question", "status": "complete", "detail": f"Query: '{query}'"})
    # Step 2: Q&A Agent receives
    pipeline["steps"].append({"name": "Q&A Agent Receives", "status": "complete", "detail": "Intent detected, routing to retrieval module"})
    # Step 3: Retrieve from Chroma
    if retrieved:
        pipeline["steps"].append({"name": "Retrieve from ChromaDB", "status": "complete", "detail": f"Vector search returned {len(retrieved)} articles (MiniLM embeddings, cosine similarity > 0.75)"})
    else:
        pipeline["steps"].append({"name": "Retrieve from ChromaDB", "status": "complete", "detail": "No semantic matches found — falling back to keyword search"})
    # Step 4: Generate Answer
    intent = detect_query_intent(query)
    answer = generate_rag_response(query, retrieved)
    pipeline["generated_answer"] = answer
    pipeline["steps"].append({"name": "Generate Answer (Groq LLM)", "status": "complete", "detail": "Synthesizing response from retrieved context only"})
    # Step 5: Critic / Reflection
    critique_lines = []
    if retrieved:
        avg_trust = sum(a['trust_score'] for a in retrieved) / len(retrieved)
        critique_lines.append(f"Average trust score of sources: {avg_trust:.1f}%")
        if avg_trust < 85:
            critique_lines.append("Warning: Some sources have moderate credibility.")
        sources = list(set(a['source'] for a in retrieved))
        if len(sources) < 2:
            critique_lines.append("Warning: Low source diversity — only one outlet represented.")
        else:
            critique_lines.append(f"Source diversity check passed: {len(sources)} outlets.")
        contra_count = sum(len(a['contradictions']) for a in retrieved)
        if contra_count > 0:
            critique_lines.append(f"Contradictions noted: {contra_count} counter-claim(s) detected.")
    else:
        critique_lines.append("No articles retrieved — answer is conversational fallback only.")
    pipeline["critic_feedback"] = "\n".join(critique_lines)
    pipeline["steps"].append({"name": "Critic / Reflection", "status": "complete", "detail": "Evaluating source credibility, diversity, and contradiction coverage"})
    # Step 6: Return Answer
    pipeline["final_answer"] = answer
    pipeline["steps"].append({"name": "Return Answer", "status": "complete", "detail": "Final response delivered to user"})
    return pipeline


# -----------------------------------------------------------------------------
# 5. ARTICLE CARD RENDERER
# -----------------------------------------------------------------------------

def _render_article_card(item, bookmarks, user, dimmed=False):
    with st.container():
        opacity = "0.85" if dimmed else "1.0"
        border_color = "#333333" if dimmed else "#444444"
        st.markdown(f"<div style='opacity:{opacity};border-left:3px solid {border_color};padding-left:12px;margin-bottom:8px;'>", unsafe_allow_html=True)
        col_title, col_trust = st.columns([4, 1])
        with col_title:
            if dimmed:
                st.markdown("<span style='font-size:11px;color:#888;background:#222;padding:2px 6px;border-radius:4px;'>EXPLORE</span>", unsafe_allow_html=True)
            st.subheader(f"[{item['category']}] {item['title']}")
            st.caption(f"Source: **{item['source']}** | Date: {item['date']} | {item['reading_time']} min read | {item['views']:,} views")
        with col_trust:
            trust_color = "#00C853" if item['trust_score'] >= 90 else "#FFD600" if item['trust_score'] >= 80 else "#FF5252"
            st.markdown(f"<div style='background:{trust_color};padding:8px;border-radius:8px;text-align:center;color:white;font-weight:bold;'>Trust: {item['trust_score']}%</div>", unsafe_allow_html=True)
        st.markdown(f"**Summary:** {item['summary']}")
        sentiment_colors = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}
        st.markdown(f"Sentiment: {sentiment_colors.get(item['sentiment'], '⚪')} **{item['sentiment'].capitalize()}**")
        col_act1, col_act2, col_act3 = st.columns([1, 1, 4])
        with col_act1:
            bookmark_key = f"bookmark_{item['id']}_{'exp' if dimmed else 'foru'}"
            is_bookmarked = item['id'] in bookmarks
            if st.button("🔖 Bookmark" if not is_bookmarked else "✅ Bookmarked", key=bookmark_key):
                db = SessionLocal()
                try:
                    db_user = db.query(User).filter(User.email == user['email']).first()
                    if db_user:
                        bms = db_user.bookmarks or []
                        if is_bookmarked:
                            bms = [x for x in bms if x != item['id']]
                            st.toast("Removed from bookmarks")
                        else:
                            bms.append(item['id'])
                            st.toast("Added to bookmarks!")
                        db_user.bookmarks = bms
                        db.commit()
                        st.session_state.current_user['bookmarks'] = bms
                except Exception as e:
                    db.rollback()
                    st.error(f"Bookmark update failed: {e}")
                finally:
                    db.close()
                st.rerun()
        with col_act2:
            if st.button("📖 Read Details", key=f"detail_{item['id']}_{'exp' if dimmed else 'foru'}"):
                st.session_state.selected_article = item
                st.rerun()
        with st.expander("⚠️ Perspective & Contradiction Analysis", expanded=False):
            st.markdown("*Summary of counter-claims and contradictory viewpoints:*")
            for idx, contradiction in enumerate(item["contradictions"], 1):
                st.markdown(f"• **Counterpoint {idx}:** {contradiction}")
            st.markdown("---")
            st.markdown("**Contradiction Detection Metadata:**")
            st.markdown("- NLI Model: `cross-encoder/nli-deberta-v3-small`")
            st.markdown("- Threshold: `0.70`")
            st.markdown("- Semantic Search: ChromaDB + MiniLM")
            st.markdown(f"- Cross-referenced against {random.randint(3, 8)} similar articles")
        st.markdown("</div>", unsafe_allow_html=True)
        st.divider()

# -----------------------------------------------------------------------------
# 6. AUTHENTICATION MODULE
# -----------------------------------------------------------------------------

def render_auth_page():
    st.title("🔐 Welcome to InsightNews AI")
    st.caption("High-Trust News Aggregation & Contradiction Intelligence Platform")
    tab_login, tab_signup, tab_admin = st.tabs(["User Login", "Sign Up / Interest Selection", "Admin Access"])

    with tab_login:
        st.subheader("Login to your Account")
        login_email = st.text_input("Email Address", key="login_email")
        col_login, col_google = st.columns(2)
        with col_login:
            if st.button("Sign In with Email", type="primary"):
                db = SessionLocal()
                user = db.query(User).filter(User.email == login_email).first()
                if user:
                    user_dict = user_to_dict(user)
                    db.close()
                    st.session_state.logged_in = True
                    st.session_state.current_user = user_dict
                    st.rerun()
                else:
                    db.close()
                    st.error("Account not found. Please Sign Up.")
        with col_google:
            if st.button("🌐 Sign In with Google"):
                db = SessionLocal()
                user = db.query(User).filter(User.email == "user@example.com").first()
                if not user:
                    user = User(
                        email="user@example.com",
                        name="Google User",
                        role="user",
                        auth_provider="Google",
                        interests=["Technology", "AI & ML"],
                        bookmarks=[]
                    )
                    db.add(user)
                    db.commit()
                user_dict = user_to_dict(user)
                db.close()
                st.session_state.logged_in = True
                st.session_state.current_user = user_dict
                st.success("Authenticated via Google!")
                st.rerun()

    with tab_signup:
        st.subheader("Create a New Account")
        new_name = st.text_input("Full Name", key="signup_name")
        new_email = st.text_input("Email Address", key="signup_email")
        new_password = st.text_input("Password", type="password", key="signup_password")
        st.markdown("### 🎯 Select Your Preferred Topics")
        selected_topics = st.multiselect(
            "Choose topics to personalize your news feed:",
            options=ALL_INTEREST_TOPICS,
            default=["Technology", "AI & ML"],
            key="signup_topics"
        )
        st.markdown("---")
        col_sup_email, col_sup_google = st.columns(2)
        with col_sup_email:
            if st.button("Complete Sign Up", key="btn_signup_email"):
                if not new_email or not selected_topics or not new_password:
                    st.warning("Please fill in all fields, select topics, and set a password.")
                else:
                    db = SessionLocal()
                    existing = db.query(User).filter(User.email == new_email).first()
                    if existing:
                        db.close()
                        st.error("An account with this email already exists.")
                    else:
                        new_user = User(
                            name=new_name,
                            email=new_email,
                            role="user",
                            auth_provider="Password",
                            interests=selected_topics,
                            bookmarks=[],
                            password_hash=hash_password(new_password)
                        )
                        db.add(new_user)
                        db.commit()
                        user_dict = user_to_dict(new_user)
                        db.close()
                        st.session_state.logged_in = True
                        st.session_state.current_user = user_dict
                        st.success("Account created successfully!")
                        st.rerun()
        with col_sup_google:
            if st.button("🌐 Sign Up with Google", key="btn_signup_google"):
                if not selected_topics:
                    st.warning("Please pick your interested topics before Google Sign-Up.")
                else:
                    g_email = new_email if new_email else f"google_{datetime.now().strftime('%M%S')}@gmail.com"
                    db = SessionLocal()
                    existing = db.query(User).filter(User.email == g_email).first()
                    if existing:
                        db.close()
                        st.error("Account already exists.")
                    else:
                        g_user = User(
                            name=new_name or "Google User",
                            email=g_email,
                            role="user",
                            auth_provider="Google OAuth",
                            interests=selected_topics,
                            bookmarks=[]
                        )
                        db.add(g_user)
                        db.commit()
                        user_dict = user_to_dict(g_user)
                        db.close()
                        st.session_state.logged_in = True
                        st.session_state.current_user = user_dict
                        st.rerun()

    with tab_admin:
        st.subheader("Admin Portal Access")
        admin_email = st.text_input("Admin Email", value="admin@news.com", key="admin_email")
        admin_pass = st.text_input("Password", type="password", key="admin_password")
        if st.button("Login as Admin", key="btn_admin_login"):
            db = SessionLocal()
            user = db.query(User).filter(User.email == admin_email, User.role == "admin").first()
            if user and user.password_hash and user.password_hash == hash_password(admin_pass):
                user_dict = user_to_dict(user)
                db.close()
                st.session_state.logged_in = True
                st.session_state.current_user = user_dict
                st.rerun()
            else:
                db.close()
                st.error("Invalid Admin Credentials")
# -----------------------------------------------------------------------------
# 7. USER DASHBOARD (News Feed)
# -----------------------------------------------------------------------------

def render_user_dashboard():
    user = st.session_state.current_user
    st.title(f"👋 Welcome back, {user['name']}")
    user_interests = user.get("interests", [])
    st.sidebar.markdown("### 👤 User Profile")
    st.sidebar.write(f"**Email:** {user['email']}")
    st.sidebar.write(f"**Role:** {user['role'].capitalize()}")
    st.sidebar.write(f"**Interested Topics:** {', '.join(user_interests)}")
    bookmarks = user.get("bookmarks", [])
    st.sidebar.metric("🔖 Saved Articles", len(bookmarks))
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔥 Trending Topics")
    trending = ["AI Safety", "CBDC Framework", "Quantum Computing", "Fusion Energy", "Arctic Warming"]
    for t in trending:
        st.sidebar.markdown(f"• {t}")

    st.markdown("### 🔍 Search & Filter")
    if "do_reset" not in st.session_state:
        st.session_state.do_reset = False
    col_search, col_cat, col_sort, col_reset = st.columns([3, 2, 2, 1])
    with col_reset:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Reset", use_container_width=True, key="reset_btn"):
            st.session_state.do_reset = True
            st.rerun()
    if st.session_state.do_reset:
        default_search, default_cat, default_sort = "", "All", "Trust Score (High-Low)"
        st.session_state.do_reset = False
    else:
        default_search = st.session_state.get("search_input", "")
        default_cat = st.session_state.get("cat_filter", "All")
        default_sort = st.session_state.get("sort_filter", "Trust Score (High-Low)")
    with col_search:
        search_query = st.text_input("Search articles...", value=default_search, placeholder="Try 'quantum', 'Fed', 'vaccine'...", key="search_input")
    with col_cat:
        all_cats = ["All"] + sorted(list(set(n["category"] for n in MOCK_NEWS)))
        try:
            cat_index = all_cats.index(default_cat)
        except ValueError:
            cat_index = 0
        filter_cat = st.selectbox("Category", all_cats, index=cat_index, key="cat_filter")
    with col_sort:
        sort_options = ["Trust Score (High-Low)", "Date (Newest)", "Views (High-Low)"]
        try:
            sort_index = sort_options.index(default_sort)
        except ValueError:
            sort_index = 0
        sort_by = st.selectbox("Sort by", sort_options, index=sort_index, key="sort_filter")

    all_news = MOCK_NEWS.copy()
    if search_query:
        q = search_query.lower()
        all_news = [n for n in all_news if q in n["title"].lower() or q in n["summary"].lower() or q in n["category"].lower()]
    if filter_cat != "All":
        all_news = [n for n in all_news if n["category"] == filter_cat]
    if sort_by == "Trust Score (High-Low)":
        all_news.sort(key=lambda x: x["trust_score"], reverse=True)
    elif sort_by == "Date (Newest)":
        all_news.sort(key=lambda x: x["date"], reverse=True)
    elif sort_by == "Views (High-Low)":
        all_news.sort(key=lambda x: x["views"], reverse=True)

    personalized = [n for n in all_news if n["category"] in user_interests or "All" in user_interests]
    other_news = [n for n in all_news if n["category"] not in user_interests and "All" not in user_interests]

    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    with col_stat1:
        st.metric("Articles Found", len(all_news))
    with col_stat2:
        avg_trust = round(sum(n["trust_score"] for n in all_news) / len(all_news), 1) if all_news else 0
        st.metric("Avg Trust Score", f"{avg_trust}%")
    with col_stat3:
        contra_count = sum(len(n["contradictions"]) for n in all_news)
        st.metric("Contradictions Detected", contra_count)
    with col_stat4:
        total_views = sum(n["views"] for n in all_news)
        st.metric("Total Readership", f"{total_views:,}")

    if personalized:
        st.markdown("### 📌 For You — Based on Your Interests")
        st.caption(f"Showing articles matching: {', '.join(user_interests)}")
        for item in personalized:
            _render_article_card(item, bookmarks, user)

    if other_news:
        st.markdown("---")
        st.markdown("### 🌍 Explore More")
        st.caption("Other trending stories outside your interests")
        for item in other_news:
            _render_article_card(item, bookmarks, user, dimmed=True)

    if not all_news:
        if search_query:
            st.info(f"No articles match your search for '{search_query}'. Try different keywords or clear the search.")
        else:
            st.info("No news available right now. Check back later!")

    if st.session_state.selected_article:
        item = st.session_state.selected_article
        with st.container():
            st.markdown("---")
            st.markdown("### 📖 Article Details")
            st.header(item['title'])
            st.caption(f"{item['source']} | {item['date']} | {item['category']} | {item['reading_time']} min read")
            col_d1, col_d2, col_d3 = st.columns(3)
            with col_d1:
                st.metric("Trust Score", f"{item['trust_score']}%")
            with col_d2:
                st.metric("Views", f"{item['views']:,}")
            with col_d3:
                st.metric("Sentiment", item['sentiment'].capitalize())
            st.markdown(f"**Summary:** {item['summary']}")
            st.markdown("**Full Contradiction Analysis:**")
            for idx, c in enumerate(item['contradictions'], 1):
                st.info(f"{idx}. {c}")
            if st.button("❌ Close Details", key="close_detail_panel"):
                st.session_state.selected_article = None
                st.rerun()
            st.markdown("---")

# -----------------------------------------------------------------------------
# 8. BOOKMARKS MODULE
# -----------------------------------------------------------------------------

def render_bookmarks():
    st.subheader("🔖 Your Bookmarked Articles")
    user = st.session_state.current_user
    bookmarks = user.get("bookmarks", [])
    if not bookmarks:
        st.info("No bookmarks yet. Save articles from your news feed to see them here!")
        return
    bookmarked_articles = [n for n in MOCK_NEWS if n['id'] in bookmarks]
    for item in bookmarked_articles:
        with st.container():
            st.markdown(f"**[{item['category']}] {item['title']}**")
            st.caption(f"Source: {item['source']} | Trust: {item['trust_score']}%")
            st.markdown(item['summary'])
            if st.button("🗑️ Remove", key=f"remove_{item['id']}"):
                db = SessionLocal()
                try:
                    db_user = db.query(User).filter(User.email == user['email']).first()
                    if db_user:
                        bms = db_user.bookmarks or []
                        if item['id'] in bms:
                            bms.remove(item['id'])
                            db_user.bookmarks = bms
                            db.commit()
                            st.session_state.current_user['bookmarks'] = bms
                except Exception as e:
                    db.rollback()
                    st.error(f"Remove failed: {e}")
                finally:
                    db.close()
                st.rerun()
            st.divider()


# -----------------------------------------------------------------------------
# 9. ANALYTICS & VISUALIZATION MODULE
# -----------------------------------------------------------------------------

def render_analytics():
    st.subheader("📊 Content & Trust Analytics")
    df_news = pd.DataFrame(MOCK_NEWS)
    df_news['date'] = pd.to_datetime(df_news['date'])
    colors = ['#00D4FF', '#0099FF', '#FF4B4B', '#FF8F00', '#7C4DFF', '#69F0AE', '#FFD600']

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.markdown("#### Trust Score Distribution by Article")
        fig_bar = px.bar(df_news, x="title", y="trust_score", color="category", text="trust_score",
                         labels={"trust_score": "Trust Score (%)", "title": "Article Title"},
                         title="Article Veracity Index", color_discrete_sequence=colors)
        fig_bar.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font=dict(color="#E0E0E0"), xaxis=dict(showticklabels=False, title=None),
                              yaxis=dict(gridcolor="#333333"),
                              legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5, bgcolor="rgba(0,0,0,0)"),
                              margin=dict(l=20, r=20, t=40, b=80))
        fig_bar.update_traces(textposition="outside", textfont=dict(color="#FFFFFF", size=13))
        st.plotly_chart(fig_bar, use_container_width=True)
    with col_chart2:
        st.markdown("#### Topic Breakdown Across Network")
        category_counts = df_news["category"].value_counts().reset_index()
        category_counts.columns = ["Category", "Count"]
        fig_pie = px.pie(category_counts, names="Category", values="Count", hole=0.4,
                         title="Category Coverage Distribution", color_discrete_sequence=colors)
        fig_pie.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font=dict(color="#E0E0E0"),
                              legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5, bgcolor="rgba(0,0,0,0)"),
                              margin=dict(l=20, r=20, t=40, b=80))
        fig_pie.update_traces(textinfo="percent+label", textposition="inside", insidetextfont=dict(color="#FFFFFF", size=12))
        st.plotly_chart(fig_pie, use_container_width=True)

    col_chart3, col_chart4 = st.columns(2)
    with col_chart3:
        st.markdown("#### Trust Score Trends Over Time")
        df_time = df_news.groupby('date').agg({'trust_score': 'mean', 'id': 'count'}).reset_index()
        df_time.columns = ['Date', 'Avg Trust Score', 'Article Count']
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(x=df_time['Date'], y=df_time['Avg Trust Score'], mode='lines+markers', name='Avg Trust', line=dict(color='#00D4FF')))
        fig_line.add_trace(go.Bar(x=df_time['Date'], y=df_time['Article Count'], name='Volume', marker_color='rgba(255,75,75,0.5)', yaxis='y2'))
        fig_line.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#E0E0E0"), yaxis=dict(title="Avg Trust Score", gridcolor="#333333"),
                               yaxis2=dict(title="Article Volume", overlaying='y', side='right', showgrid=False),
                               legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                               margin=dict(l=20, r=20, t=40, b=60))
        st.plotly_chart(fig_line, use_container_width=True)
    with col_chart4:
        st.markdown("#### Source Credibility Distribution")
        source_trust = df_news.groupby('source')['trust_score'].mean().reset_index().sort_values('trust_score', ascending=True)
        fig_src = px.bar(source_trust, x='trust_score', y='source', orientation='h', color='trust_score',
                         color_continuous_scale=['#FF5252', '#FFD600', '#00C853'],
                         labels={'trust_score': 'Avg Trust Score', 'source': 'News Source'})
        fig_src.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font=dict(color="#E0E0E0"), yaxis=dict(gridcolor="#333333"),
                              coloraxis_showscale=False, margin=dict(l=20, r=20, t=40, b=40))
        st.plotly_chart(fig_src, use_container_width=True)

    col_chart5, col_chart6 = st.columns(2)
    with col_chart5:
        st.markdown("#### Sentiment Distribution by Category")
        sentiment_data = []
        for _, row in df_news.iterrows():
            sentiment_data.append({'Category': row['category'], 'Sentiment': row['sentiment']})
        df_sent = pd.DataFrame(sentiment_data)
        sent_counts = df_sent.groupby(['Category', 'Sentiment']).size().reset_index(name='Count')
        fig_sent = px.bar(sent_counts, x='Category', y='Count', color='Sentiment', barmode='group',
                          color_discrete_map={'positive': '#00C853', 'negative': '#FF5252', 'neutral': '#FFD600'})
        fig_sent.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#E0E0E0"), yaxis=dict(gridcolor="#333333"),
                               legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
                               margin=dict(l=20, r=20, t=40, b=80))
        st.plotly_chart(fig_sent, use_container_width=True)
    with col_chart6:
        st.markdown("#### Contradiction Density by Category")
        contra_data = []
        for item in MOCK_NEWS:
            for contra in item['contradictions']:
                contra_data.append({'Category': item['category'], 'Count': 1})
        if contra_data:
            df_contra = pd.DataFrame(contra_data)
            contra_pivot = df_contra.groupby(['Category']).size().reset_index(name='Contradictions')
            fig_contra = px.bar(contra_pivot, x='Category', y='Contradictions', color='Contradictions',
                                color_continuous_scale=['#69F0AE', '#FF8F00', '#FF5252'])
            fig_contra.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                     font=dict(color="#E0E0E0"), yaxis=dict(gridcolor="#333333"),
                                     coloraxis_showscale=False, margin=dict(l=20, r=20, t=40, b=40))
            st.plotly_chart(fig_contra, use_container_width=True)

    col_chart7, col_chart8 = st.columns(2)
    with col_chart7:
        st.markdown("#### Reading Time vs Trust Score")
        fig_rt = px.scatter(df_news, x='reading_time', y='trust_score', color='category', size='views',
                            hover_data=['title', 'source'], color_discrete_sequence=colors)
        fig_rt.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                             font=dict(color="#E0E0E0"), xaxis=dict(gridcolor="#333333", title="Reading Time (min)"),
                             yaxis=dict(gridcolor="#333333", title="Trust Score (%)"),
                             legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
                             margin=dict(l=20, r=20, t=40, b=80))
        st.plotly_chart(fig_rt, use_container_width=True)
    with col_chart8:
        st.markdown("#### Article Engagement (Views by Category)")
        views_cat = df_news.groupby('category')['views'].sum().reset_index().sort_values('views', ascending=True)
        fig_views = px.bar(views_cat, x='views', y='category', orientation='h', color='views',
                           color_continuous_scale=['#00D4FF', '#0099FF', '#7C4DFF'])
        fig_views.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                font=dict(color="#E0E0E0"), yaxis=dict(gridcolor="#333333"),
                                coloraxis_showscale=False, margin=dict(l=20, r=20, t=40, b=40))
        st.plotly_chart(fig_views, use_container_width=True)

    st.markdown("---")
    st.markdown("### 📥 Export Analytics Data")
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        csv = df_news.to_csv(index=False).encode('utf-8')
        st.download_button("Download News Data (CSV)", csv, "insightnews_data.csv", "text/csv")
    with col_exp2:
        json_str = df_news.to_json(orient='records')
        st.download_button("Download News Data (JSON)", json_str, "insightnews_data.json", "application/json")

# -----------------------------------------------------------------------------
# 10. DAILY BRIEFING — PLATFORM AGENT (Autonomous / Scheduled)
# -----------------------------------------------------------------------------
# Flow: Prefect Scheduler → Platform Agent → Retrieve User Preferences
# → PostgreSQL Personalized Retrieval → NewsGenerationEngine → Critic/Reflection
# → Save Daily Briefing → Email/App Notification/API

def render_daily_briefing():
    st.markdown("### 📋 Daily Briefing — Platform Agent")
    st.caption("Autonomous agent pipeline: Scheduled retrieval → Synthesis → Critic → Delivery")
    user = st.session_state.current_user
    user_prefs = user.get("interests", [])

    # Scheduler status card
    col_sched, col_trigger = st.columns([3, 1])
    with col_sched:
        st.info("**🕐 Prefect Scheduler Active** — Next run: Tomorrow 8:00 AM | Last run: Today 8:00 AM")
    with col_trigger:
        if st.button("⚡ Generate Briefing Now", type="primary", use_container_width=True):
            st.session_state.platform_agent_running = True
            st.rerun()

    st.markdown("---")

    # Show pipeline execution if triggered
    if st.session_state.platform_agent_running:
        with st.spinner("Running Platform Agent pipeline..."):
            time.sleep(1.2)
            pipeline = simulate_platform_agent_pipeline(user_prefs)
            st.session_state.last_briefing = pipeline
            st.session_state.platform_agent_running = False
            st.session_state.daily_briefings.append(pipeline)
            st.rerun()

    # Display pipeline visualization
    if st.session_state.last_briefing:
        pipeline = st.session_state.last_briefing
        st.markdown("#### 🤖 Agent Execution Flow")
        st.markdown("<div style='background:#1a1a1a;padding:16px;border-radius:12px;margin-bottom:16px;'>", unsafe_allow_html=True)

        for idx, step in enumerate(pipeline["steps"], 1):
            render_flow_step(idx, step["name"], step["status"], step.get("detail", ""))
            if idx < len(pipeline["steps"]):
                render_pipeline_connector()

        st.markdown("</div>", unsafe_allow_html=True)

        # Display the generated briefing
        st.markdown("---")
        st.markdown("#### 📰 Generated Briefing")
        st.markdown(f"<div style='background:#0d1b2a;padding:20px;border-radius:12px;border:1px solid #1b3a4b;'>", unsafe_allow_html=True)
        st.markdown(pipeline["briefing"])
        st.markdown("</div>", unsafe_allow_html=True)

        # Show source articles used
        with st.expander("📚 Source Articles Used in Briefing"):
            for article in pipeline["articles"]:
                st.markdown(f"**[{article['category']}] {article['title']}** — {article['source']} (Trust: {article['trust_score']}%)")
                st.caption(article['summary'])

        # Delivery status
        st.markdown("---")
        col_del1, col_del2, col_del3 = st.columns(3)
        with col_del1:
            st.success("✉️ Email: Queued")
        with col_del2:
            st.success("📱 App Push: Sent")
        with col_del3:
            st.success("🔌 API Webhook: 200 OK")

    else:
        # Show a sample/previous briefing or placeholder
        st.info("No briefing generated yet. Click **'Generate Briefing Now'** to run the Platform Agent pipeline.")

        # Show the architecture diagram ONLY for admin
        if user.get("role") == "admin":
            st.markdown("---")
            st.markdown("#### 🏗️ Platform Agent Architecture")
            st.markdown("""
            <div style="background:#1a1a1a;padding:20px;border-radius:12px;">
                <div style="text-align:center;font-family:monospace;font-size:14px;line-height:2.2;color:#ccc;">
                    <div style="color:#0099FF;font-weight:bold;">Prefect Scheduler</div>
                    <div style="color:#666;">▼ Every day at 8:00 AM</div>
                    <div style="color:#00C853;font-weight:bold;">Platform Agent</div>
                    <div style="color:#666;">▼</div>
                    <div>Retrieve User Preferences</div>
                    <div style="color:#666;">▼</div>
                    <div>PostgreSQL Personalized Retrieval</div>
                    <div style="color:#666;">▼</div>
                    <div style="color:#FFD600;font-weight:bold;">NewsGenerationEngine (Groq Llama-3.3-70b)</div>
                    <div style="color:#666;">▼</div>
                    <div style="color:#FF8F00;font-weight:bold;">Critic / Reflection</div>
                    <div style="color:#666;">▼</div>
                    <div>Save Daily Briefing → PostgreSQL</div>
                    <div style="color:#666;">▼</div>
                    <div style="color:#7C4DFF;font-weight:bold;">Email / App Notification / API</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # History of briefings
    if st.session_state.daily_briefings:
        st.markdown("---")
        st.markdown("#### 📜 Briefing History")
        for idx, briefing in enumerate(reversed(st.session_state.daily_briefings[-5:]), 1):
            with st.expander(f"Briefing #{len(st.session_state.daily_briefings) - idx + 1} — {briefing['timestamp']}"):
                st.markdown(briefing["briefing"])


# -----------------------------------------------------------------------------
# 11. Q&A AGENT — INTERACTIVE (User-triggered)
# -----------------------------------------------------------------------------
# Flow: User → Ask Question → Q&A Agent → Retrieve from Chroma
# → Generate Answer → Critic → Return Answer

def render_qa_agent():
    st.markdown("### 💬 Q&A Agent — Interactive")
    st.caption("User-triggered pipeline: Question → Chroma Retrieval → LLM Generation → Critic → Answer")
    user = st.session_state.current_user

    # Architecture diagram at top (admin only)
    if user.get("role") == "admin":
        with st.expander("🏗️ Q&A Agent Architecture", expanded=False):
            st.markdown("""
            <div style="background:#1a1a1a;padding:20px;border-radius:12px;">
                <div style="text-align:center;font-family:monospace;font-size:14px;line-height:2.2;color:#ccc;">
                    <div style="color:#0099FF;font-weight:bold;">User</div>
                    <div style="color:#666;">▼ Ask Question (Web UI)</div>
                    <div style="color:#00C853;font-weight:bold;">Q&A Agent</div>
                    <div style="color:#666;margin-left:12px;">Triggered by user input</div>
                    <div>  → Retrieve from ChromaDB</div>
                    <div style="color:#666;margin-left:24px;">MiniLM embeddings, top_k=5</div>
                    <div style="color:#FFD600;font-weight:bold;">  → Generate Answer</div>
                    <div style="color:#666;margin-left:24px;">Groq: llama-3.3-70b-versatile</div>
                    <div style="color:#FF8F00;font-weight:bold;">  → Critic / Reflection</div>
                    <div style="color:#666;margin-left:24px;">Trust check, source diversity</div>
                    <div style="color:#7C4DFF;font-weight:bold;">  → Return Answer</div>
                    <div style="color:#666;margin-left:24px;">Rendered in chat UI</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Suggested questions
    with st.expander("💡 Suggested Questions"):
        suggestions = [
            "What are the latest developments in AI safety?",
            "Explain the contradictions around the CBDC framework.",
            "Summarize the health news from this week.",
            "What are the opposing views on quantum battery technology?",
            "Tell me about climate change news and conflicting reports."
        ]
        cols = st.columns(len(suggestions))
        for i, q in enumerate(suggestions):
            with cols[i]:
                if st.button(q, key=f"suggest_{i}"):
                    st.session_state.chat_history.append({"role": "user", "content": q, "timestamp": datetime.now().strftime("%H:%M:%S")})
                    retrieved = retrieve_relevant_articles(q, top_k=3)
                    pipeline = simulate_qa_agent_pipeline(q, retrieved)
                    st.session_state.qa_agent_state = pipeline
                    st.session_state.chat_history.append({"role": "assistant", "content": pipeline["final_answer"], "timestamp": datetime.now().strftime("%H:%M:%S"), "pipeline": pipeline})
                    st.rerun()

    # Display conversation
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            # Show pipeline expander for assistant messages
            if message["role"] == "assistant" and "pipeline" in message:
                with st.expander("🔍 View Q&A Agent Pipeline Execution", expanded=False):
                    pipeline = message["pipeline"]
                    st.markdown("**Agent Pipeline Steps:**")
                    for idx, step in enumerate(pipeline["steps"], 1):
                        render_flow_step(idx, step["name"], step["status"], step.get("detail", ""))
                        if idx < len(pipeline["steps"]):
                            render_pipeline_connector()
                    if pipeline.get("critic_feedback"):
                        st.markdown("**🧐 Critic Feedback:**")
                        st.info(pipeline["critic_feedback"])

    # User Input
    if prompt := st.chat_input("Ask me anything about news, trust scores, or contradictions..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt, "timestamp": datetime.now().strftime("%H:%M:%S")})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            # Step 1: Show retrieval spinner
            with st.spinner("🔍 Retrieving from ChromaDB..."):
                time.sleep(0.5)
                retrieved = retrieve_relevant_articles(prompt, top_k=3)

            if retrieved:
                with st.expander("📚 Retrieved Context (ChromaDB)", expanded=False):
                    for idx, art in enumerate(retrieved, 1):
                        st.markdown(f"**{idx}. {art['title']}** ({art['source']}, Trust: {art['trust_score']}%)")
                        st.caption(art['summary'])

            # Step 2: Generate + Critic
            with st.spinner("🧠 Generating answer via Groq LLM..."):
                time.sleep(0.6)
                pipeline = simulate_qa_agent_pipeline(prompt, retrieved)
                st.session_state.qa_agent_state = pipeline

            # Step 3: Show pipeline visualization
            with st.expander("🔍 View Q&A Agent Pipeline Execution", expanded=False):
                st.markdown("**Agent Pipeline Steps:**")
                for idx, step in enumerate(pipeline["steps"], 1):
                    render_flow_step(idx, step["name"], step["status"], step.get("detail", ""))
                    if idx < len(pipeline["steps"]):
                        render_pipeline_connector()
                if pipeline.get("critic_feedback"):
                    st.markdown("**🧐 Critic Feedback:**")
                    st.info(pipeline["critic_feedback"])

            # Step 4: Display final answer
            st.markdown(pipeline["final_answer"])

        st.session_state.chat_history.append({"role": "assistant", "content": pipeline["final_answer"], "timestamp": datetime.now().strftime("%H:%M:%S"), "pipeline": pipeline})

    # Clear chat button
    if st.session_state.chat_history:
        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = []
            st.session_state.qa_agent_state = {}
            st.rerun()

# -----------------------------------------------------------------------------
# 12. AGENT MONITOR — Live Status Dashboard
# -----------------------------------------------------------------------------

def render_agent_monitor():
    st.markdown("### 🤖 Agent Monitor")
    st.caption("Real-time visibility into both agent pipelines")

    # Platform Agent Status Card
    st.markdown("---")
    col_pa1, col_pa2, col_pa3, col_pa4 = st.columns(4)
    with col_pa1:
        st.metric("Platform Agent", "🟢 Active", "Scheduled")
    with col_pa2:
        st.metric("Next Run", "8:00 AM", "~5h 30m")
    with col_pa3:
        briefings_count = len(st.session_state.daily_briefings)
        st.metric("Briefings Generated", briefings_count)
    with col_pa4:
        st.metric("Last Status", "Success", "✓ Delivered")

    # Q&A Agent Status Card
    col_qa1, col_qa2, col_qa3, col_qa4 = st.columns(4)
    with col_qa1:
        st.metric("Q&A Agent", "🟢 Active", "On Demand")
    with col_qa2:
        qa_count = len([m for m in st.session_state.chat_history if m["role"] == "assistant"])
        st.metric("Queries Answered", qa_count)
    with col_qa3:
        st.metric("Avg Response Time", "~1.2s", "Chroma + Groq")
    with col_qa4:
        st.metric("Last Status", "Ready", "✓ Standing by")

    st.markdown("---")

    # Side-by-side architecture comparison
    col_arch1, col_arch2 = st.columns(2)

    with col_arch1:
        st.markdown("#### 🏭 Platform Agent (Autonomous)")
        st.markdown("""
        <div style="background:#1a1a1a;padding:16px;border-radius:12px;font-family:monospace;font-size:12px;line-height:2;color:#ccc;">
            <div style="color:#0099FF;font-weight:bold;">▶ Prefect Scheduler</div>
            <div style="color:#666;margin-left:12px;">Every day at 8:00 AM</div>
            <div style="color:#00C853;font-weight:bold;">▶ Platform Agent</div>
            <div style="color:#666;margin-left:12px;">LangGraph StateGraph</div>
            <div>  → Retrieve User Preferences</div>
            <div>  → PostgreSQL Personalized Retrieval</div>
            <div style="color:#FFD600;font-weight:bold;">  → NewsGenerationEngine</div>
            <div style="color:#666;margin-left:24px;">Groq: llama-3.3-70b-versatile</div>
            <div style="color:#FF8F00;font-weight:bold;">  → Critic / Reflection</div>
            <div>  → Save DailyBriefing (PostgreSQL)</div>
            <div style="color:#7C4DFF;font-weight:bold;">  → Email / Push / API</div>
        </div>
        """, unsafe_allow_html=True)

        # Platform agent recent logs
        st.markdown("**Recent Platform Agent Runs:**")
        if st.session_state.daily_briefings:
            for b in reversed(st.session_state.daily_briefings[-3:]):
                st.success(f"✓ {b['timestamp']} — {len(b['articles'])} articles → Briefing saved")
        else:
            st.info("No runs yet. Generate a briefing in the Daily Briefing tab.")

    with col_arch2:
        st.markdown("#### 💬 Q&A Agent (Interactive)")
        st.markdown("""
        <div style="background:#1a1a1a;padding:16px;border-radius:12px;font-family:monospace;font-size:12px;line-height:2;color:#ccc;">
            <div style="color:#0099FF;font-weight:bold;">▶ User</div>
            <div style="color:#666;margin-left:12px;">Ask Question (Web UI)</div>
            <div style="color:#00C853;font-weight:bold;">▶ Q&A Agent</div>
            <div style="color:#666;margin-left:12px;">Triggered by user input</div>
            <div>  → Retrieve from ChromaDB</div>
            <div style="color:#666;margin-left:24px;">MiniLM embeddings, top_k=5</div>
            <div style="color:#FFD600;font-weight:bold;">  → Generate Answer</div>
            <div style="color:#666;margin-left:24px;">Groq: llama-3.3-70b-versatile</div>
            <div style="color:#FF8F00;font-weight:bold;">  → Critic / Reflection</div>
            <div style="color:#666;margin-left:24px;">Trust check, source diversity</div>
            <div style="color:#7C4DFF;font-weight:bold;">  → Return Answer</div>
            <div style="color:#666;margin-left:24px;">Rendered in chat UI</div>
        </div>
        """, unsafe_allow_html=True)

        # Q&A agent recent logs
        st.markdown("**Recent Q&A Agent Queries:**")
        if st.session_state.chat_history:
            user_msgs = [m for m in st.session_state.chat_history if m["role"] == "user"]
            for m in reversed(user_msgs[-3:]):
                st.info(f"❓ {m.get('timestamp', 'Now')} — {m['content'][:50]}...")
        else:
            st.info("No queries yet. Ask something in the Q&A Agent tab.")

    # System components status
    st.markdown("---")
    st.markdown("#### 🖥️ System Components Status")
    components = [
        ("PostgreSQL", "🟢 Connected", "raw_articles, daily_briefings, article_contradictions"),
        ("ChromaDB", "🟢 Connected", "news_articles collection, 384-dim MiniLM embeddings"),
        ("Groq API", "🟢 Connected", "llama-3.3-70b-versatile, temp=0"),
        ("NLI Model", "🟢 Loaded", "cross-encoder/nli-deberta-v3-small"),
        ("BERTopic", "🟢 Ready", "Topic modeling on demand"),
        ("News APIs", "🟡 Degraded", "RSS active, 1/4 APIs throttled"),
    ]
    for name, status, detail in components:
        col_c1, col_c2, col_c3 = st.columns([2, 2, 6])
        with col_c1:
            st.markdown(f"**{name}**")
        with col_c2:
            st.markdown(status)
        with col_c3:
            st.caption(detail)

    # Pipeline execution logs
    st.markdown("---")
    st.markdown("#### 📜 Execution Logs")
    if st.session_state.agent_logs:
        for log in reversed(st.session_state.agent_logs[-10:]):
            st.text(log)
    else:
        st.info("Agent logs will appear here as pipelines execute.")


# -----------------------------------------------------------------------------
# 13. ADMIN DASHBOARD
# -----------------------------------------------------------------------------

def render_admin_dashboard():
    st.title("🛠️ Creator & Admin Dashboard")
    st.caption("Customer Management & Platform Metrics")
    db = SessionLocal()
    total_users = db.query(User).count()
    db_users = db.query(User).all()
    db.close()

    users_data = []
    for u in db_users:
        users_data.append({
            "Name": u.name,
            "Email": u.email,
            "Role": u.role,
            "Auth Provider": u.auth_provider or "Standard",
            "Interested Topics": ", ".join(u.interests or []),
            "Bookmarks": len(u.bookmarks or [])
        })
    df_users = pd.DataFrame(users_data)
    st.dataframe(df_users, use_container_width=True)
    st.subheader("📡 Content Pipeline Status")
    pipeline_data = {
        "Stage": ["Ingestion", "Cleaning", "NER", "Enrichment", "Embedding", "Topic Modeling", "Contradiction Detection", "Recommendation"],
        "Status": ["✅ Active", "✅ Active", "✅ Active", "✅ Active", "✅ Active", "✅ Active", "✅ Active", "✅ Active"],
        "Processed Today": [1240, 1240, 1185, 1185, 1150, 1150, 1150, 1120],
        "Avg Latency": ["1.2s", "0.4s", "0.8s", "1.1s", "2.3s", "45s", "8.5s", "3.2s"]
    }
    df_pipeline = pd.DataFrame(pipeline_data)
    st.dataframe(df_pipeline, use_container_width=True)
    st.subheader("📊 Source Distribution")
    source_counts = {}
    for n in MOCK_NEWS:
        source_counts[n['source']] = source_counts.get(n['source'], 0) + 1
    df_sources = pd.DataFrame(list(source_counts.items()), columns=["Source", "Count"])
    fig_src = px.bar(df_sources, x="Source", y="Count", color="Source", title="Articles by Source")
    fig_src.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_src, use_container_width=True)

# -----------------------------------------------------------------------------
# 14. MAIN ENTRY POINT & ROUTING
# -----------------------------------------------------------------------------

def main():
    if not st.session_state.logged_in:
        render_auth_page()
    else:
        col_head, col_logout = st.columns([5, 1])
        with col_head:
            st.markdown(f"### 📰 InsightNews Portal | Role: `{st.session_state.current_user['role'].upper()}`")
        with col_logout:
            if st.button("🚪 Logout"):
                st.session_state.logged_in = False
                st.session_state.current_user = None
                st.rerun()
        st.divider()

        if st.session_state.current_user["role"] == "admin":
            tab_main, tab_bookmarks, tab_analytics, tab_briefing, tab_qa, tab_monitor, tab_admin = st.tabs([
                "📰 News Feed", "🔖 Bookmarks", "📊 Analytics", "📋 Daily Briefing", "💬 Q&A Agent", "🤖 Agent Monitor", "🛠️ Admin Panel"
            ])
            with tab_main:
                render_user_dashboard()
            with tab_bookmarks:
                render_bookmarks()
            with tab_analytics:
                render_analytics()
            with tab_briefing:
                render_daily_briefing()
            with tab_qa:
                render_qa_agent()
            with tab_monitor:
                render_agent_monitor()
            with tab_admin:
                render_admin_dashboard()
        else:
            tab_main, tab_bookmarks, tab_briefing, tab_qa = st.tabs([
                "📰 Personal News Feed", "🔖 Bookmarks", "📋 Daily Briefing", "💬 Q&A Agent"
            ])
            with tab_main:
                render_user_dashboard()
            with tab_bookmarks:
                render_bookmarks()
            with tab_briefing:
                render_daily_briefing()
            with tab_qa:
                render_qa_agent()
if __name__ == "__main__":
    main()