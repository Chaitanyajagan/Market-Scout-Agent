import json
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
from google import genai

load_dotenv()
gemini_client = None
if "GEMINI_API_KEY" in os.environ and os.environ["GEMINI_API_KEY"]:
    gemini_client = genai.Client()
from duckduckgo_search import DDGS
from fpdf import FPDF

app = FastAPI(title="InnoTech AI Strategic Intelligence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
GROQ_API_KEY = "ENTER-YOUR-API-KEY" 
client = Groq(api_key=GROQ_API_KEY)

class CompanyProfile(BaseModel):
    my_name: str
    my_description: str
    my_core_features: list
    maintenance_tips: list = []

class AnalysisRequest(BaseModel):
    company_name: str
    days: int = 30
    profile: CompanyProfile = None

class CategoryRequest(BaseModel):
    category_name: str

class ReportRequest(BaseModel):
    title: str
    content: list[str]

class ChatRequest(BaseModel):
    message: str

# --- PDF Generator ---
def search_web(query: str):
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=10)
            result_list = list(results) if results else []
            if not result_list:
                return "No recent web data found."
            return "\n".join([f"Source: {r['title']} - {r['body']}" for r in result_list])
    except Exception:
        return "No recent web data found."

def ai_json_call(prompt: str):
    completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a Senior Business Intelligence Analyst. Output strictly in JSON format."},
            {"role": "user", "content": prompt}
        ],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"}
    )
    return json.loads(completion.choices[0].message.content)

# --- Endpoints ---
last_news_fetch = None
cached_news = []

@app.get("/market-news")
async def get_market_news():
    global last_news_fetch, cached_news
    now = datetime.now()
    
    # Fetch news if cache is empty or older than 60 seconds 
    # This prevents rate limits while allowing the frontend to poll frequently
    if not last_news_fetch or (now - last_news_fetch).total_seconds() > 60 or not cached_news:
        try:
            with DDGS() as ddgs:
                results = ddgs.news("technology", max_results=15)
                news_list = [r['title'] for r in results] if results else []
                if news_list:
                    cached_news = news_list
                    last_news_fetch = now
        except Exception:
            pass
            
    if not cached_news:
        return {"news": ["Gathering live technology market data..."]}
        
    return {"news": cached_news}

@app.post("/chat")
async def chat_with_gemini(req: ChatRequest):
    try:
        if not gemini_client:
            return {"error": "Gemini API credentials not configured."}
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=req.message,
        )
        return {"response": response.text}
    except Exception as e:
        return {"error": str(e)}

@app.post("/analyze-company")
async def analyze_company(req: AnalysisRequest):
    search_query = f"{req.company_name} new features product updates {datetime.now().year}"
    raw_data = search_web(search_query)
    
    prompt = f"""
    Based on this web data: {raw_data}
    Analyze {req.company_name} for the last {req.days} days.
    
    TASKS:
    1. Identify features released STRICTLY in the last {req.days} days. If none, return an empty list.
    2. List 4 general latest features/updates regardless of date.
    3. Provide a 3-point sentiment trend (scores 0-100).
    4. Provide a SWOT analysis.

    Return JSON: 
    {{
        "name": "{req.company_name}",
        "bio": "Short summary",
        "sentiment": "Positive/Neutral/Negative",
        "sentiment_trend": [
            {{"date": "15 days ago", "score": 70}}, {{"date": "7 days ago", "score": 75}}, {{"date": "Today", "score": 85}}
        ],
        "features_in_period": ["feature 1"],
        "general_latest_updates": ["update A", "update B"],
        "swot": {{"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}},
        "next_predicted_move": "Prediction based on gaps",
        "strategic_gap": "One specific gap"
    }}
    """
    return ai_json_call(prompt)

@app.post("/bi-report")
async def bi_report(req: AnalysisRequest):
    search_query = f"{req.company_name} business model products recent news {datetime.now().year}"
    raw_data = search_web(search_query)
    
    prompt = f"""
    You are an AI business intelligence analyst.
    
    Based on this web data: {raw_data}
    
    User Input Company: "{req.company_name}"

    Generate a structured business intelligence dashboard report with the following layout:

    SECTION 1: Company Overview
    - Company Name
    - Founded Year
    - Founders
    - Headquarters
    - Industry
    - Market Position

    SECTION 2: Products & Services (Left Panel)
    List ALL major products and services in bullet format.
    Group them by category if applicable.

    SECTION 3: Recent Updates & News (Right Panel)
    - Major product launches
    - Acquisitions
    - Funding updates
    - Strategic partnerships
    - Expansion updates
    (Only from last 3-5 years)

    SECTION 4: Business Model (Tree Layout Data)
    Provide the core pillars of the business model.
    - Revenue Streams
    - Customer Segments
    - Key Partners
    - Value Proposition

    SECTION 5: SWOT Analysis (Bottom Panel)
    Strengths:
    Weaknesses:
    Opportunities:
    Threats:

    Return structured JSON with keys:
    {{
        "overview": {{
            "Company Name": "",
            "Founded Year": "",
            "Founders": "",
            "Headquarters": "",
            "Industry": "",
            "Market Position": ""
        }},
        "products": {{
            "Category 1": ["Product A", "Product B"],
            "Category 2": ["Service X"]
        }},
        "recent_updates": [
            "Update 1",
            "Update 2"
        ],
        "business_model": {{
            "Value Proposition": ["Point 1", "Point 2"],
            "Customer Segments": ["Segment A", "Segment B"],
            "Key Partners": ["Partner 1", "Partner 2"],
            "Revenue Streams": ["Stream 1", "Stream 2"]
        }},
        "swot": {{
            "Strengths": [],
            "Weaknesses": [],
            "Opportunities": [],
            "Threats": []
        }}
    }}
    Only return JSON.
    No extra explanation.
    """
    return ai_json_call(prompt)

@app.post("/compare-intelligence")
async def compare_intel(req: AnalysisRequest):
    prompt = f"""
    Compare Our Project: {req.profile.my_name} ({req.profile.my_core_features})
    Against Competitor: {req.company_name}
    Return JSON:
    {{
        "comparison_table": [
            {{"feature": "Feature Name", "us": "Our version", "them": "Their version", "winner": "us/them/tie"}}
        ]
    }}
    """
    return ai_json_call(prompt)

@app.post("/generate-battle-card")
async def battle_card(req: AnalysisRequest):
    prompt = f"""
    Create a Sales Battle Card: {req.profile.my_name} vs {req.company_name}.
    Return JSON:
    {{
        "kill_points": ["Reason 1 we win", "Reason 2"],
        "objection_handling": [{{"they_say": "...", "we_say": "..."}}],
        "top_landmines": ["Question to ask client..."],
        "summary": "30-second elevator pitch"
    }}
    """
    return ai_json_call(prompt)

@app.post("/competitive-analysis")
async def competitive_analysis(req: CategoryRequest):
    # Fetch recent data to pass context to the LLM
    search_query = f"{req.category_name} top leading companies competitors market {datetime.now().year}"
    raw_data = search_web(search_query)

    prompt = f"""
    Based on this web data context: {raw_data}
    You are a business intelligence assistant.
    When a user provides a business category, generate a structured competitive analysis report.
    
    Category: "{req.category_name}"
    
    Your task:
    1. Identify the top 5-10 leading companies in this category.
    2. For each company, provide:
       - Company Name
       - Founded Year
       - Headquarters Location
       - Founder(s)
       - Estimated Revenue (if available)
       - Key Products/Services
       - Market Position (Leader / Emerging / Niche)
       - Competitive Strength
       - Target Audience
       - Official Website
    
    3. Format the output STRICTLY in JSON format like this:
    {{
      "category": "{req.category_name}",
      "top_competitors": [
        {{
          "company_name": "",
          "founded": "",
          "headquarters": "",
          "founders": "",
          "revenue": "",
          "key_products": [],
          "market_position": "",
          "competitive_strength": "",
          "target_audience": "",
          "website": ""
        }}
      ]
    }}
    
    Only return valid JSON. No explanations outside JSON.
    """
    return ai_json_call(prompt)

@app.post("/analyze-project-maintenance")
async def analyze_project_maintenance(req: CompanyProfile):
    search_query = f"{req.my_name} technology market trends what to build next {datetime.now().year}"
    raw_data = search_web(search_query)

    prompt = f"""
    Based on general market context: {raw_data}
    
    You are an AI Product Strategy Consultant.
    The user is building a project called "{req.my_name}".
    Description: "{req.my_description}"
    Current Core Features: {req.my_core_features}
    
    Provide exactly 3 "Better to Maintain Tips" for this specific project.
    Critically analyze their provided Description and Core Features against the market data. 
    EACH tip MUST explicitly reference their given project details or features, and specify EXACTLY what needs to be updated or added to compete effectively with the current market.
    
    Return JSON:
    {{
        "maintenance_tips": [
            "Tip 1...",
            "Tip 2...",
            "Tip 3..."
        ]
    }}
    Only return valid JSON. No explanations outside JSON.
    """
    return ai_json_call(prompt)

from fpdf import FPDF

class InnoTechPDF(FPDF):
    def header(self):
        # Watermark
        self.set_font("Arial", "B", 60)
        self.set_text_color(240, 240, 245)
        # Position watermark in center
        self.text(30, 150, "InnoTech")
        
        # Header text
        self.set_font("Arial", "B", 10)
        self.set_text_color(100, 100, 120)
        current_date = datetime.now().strftime("%B %d, %Y")
        self.cell(0, 10, f"InnoTech Strategic Pulse Report  |  {current_date}", ln=True, align="R")
        self.ln(5)

@app.post("/download-report")
async def download_report(req: ReportRequest, background_tasks: BackgroundTasks):
    pdf = InnoTechPDF()
    pdf.add_page()
    
    # Title
    pdf.set_font("Arial", "B", 24)
    pdf.set_text_color(30, 30, 80)
    pdf.multi_cell(0, 15, req.title.encode('latin-1', 'replace').decode('latin-1'), align="C")
    pdf.ln(10)
    
    # Content
    pdf.set_font("Arial", "", 11)
    pdf.set_text_color(50, 50, 50)
    
    for line in req.content:
        # Sanitize text for FPDF latin-1 requirement
        safe_line = line.encode('latin-1', 'replace').decode('latin-1')
        
        if safe_line.startswith("### "):
            pdf.ln(8)
            pdf.set_font("Arial", "B", 14)
            pdf.set_text_color(79, 70, 229) # Indigo
            pdf.multi_cell(0, 8, safe_line.replace("### ", ""))
            pdf.set_font("Arial", "", 11)
            pdf.set_text_color(50, 50, 50)
            pdf.ln(2)
        elif safe_line.startswith("**") and safe_line.endswith("**"):
            pdf.ln(4)
            pdf.set_font("Arial", "B", 12)
            pdf.multi_cell(0, 8, safe_line.replace("**", ""))
            pdf.set_font("Arial", "", 11)
        else:
            pdf.multi_cell(0, 6, safe_line)
            pdf.ln(2)

    import tempfile
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    
    pdf.output(path)
    
    background_tasks.add_task(os.remove, path)
    
    return FileResponse(
        path=path,
        filename=f"{req.title.replace(' ', '_')}.pdf",
        media_type="application/pdf"
    )

@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
