# 🚀 Competitive Intelligence Briefing Crew

> AI-powered multi-agent system for generating trustworthy competitive intelligence reports with citations, governance, and bounded execution.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![CrewAI](https://img.shields.io/badge/CrewAI-Latest-green)
![LangGraph](https://img.shields.io/badge/LangGraph-Supported-orange)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-teal)
![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-red)

---

# 📖 Overview

The **Competitive Intelligence Briefing Crew** automates the process of creating weekly competitive intelligence reports.

Instead of analysts manually searching dozens of websites and preparing reports, the system uses a coordinated team of AI agents to:

- Research competitors
- Collect reliable sources
- Analyze market trends
- Compare competitor strategies
- Generate a structured executive briefing
- Attach citations to every claim
- Handle failures gracefully
- Produce exportable reports

---

# 🎯 Business Problem

Strategy teams spend hours every week collecting:

- Competitor pricing
- Product launches
- Funding news
- Market trends
- Customer sentiment
- Industry reports

This process is:

- Time consuming
- Inconsistent
- Difficult to verify
- Often outdated

This project automates the entire workflow.

---

# ✨ Features

## Multi-Agent Workflow

The project consists of four agents:

### Supervisor Agent

- Controls execution
- Delegates tasks
- Prevents infinite loops
- Monitors step limits

---

### Research Agent

Responsibilities:

- Search trusted sources
- Collect articles
- Retrieve company updates
- Gather pricing information
- Store citations

---

### Analyst Agent

Responsibilities:

- Compare competitors
- Detect pricing changes
- Identify market signals
- Remove duplicate information
- Validate evidence

---

### Writer Agent

Responsibilities:

- Generate executive briefing
- Produce structured report
- Preserve citations
- Format output

---

# 📊 Generated Report

The final report contains:

1. Executive Summary
2. Key Recommendations
3. Competitor Pricing
4. Product Launches
5. Market Signals
6. SWOT Analysis
7. Risks
8. Opportunities
9. Industry Trends
10. Citations
11. Run Metadata
12. Sources Used

---

# 🏗 Architecture

```
                    User
                      │
                      ▼
               Streamlit UI
                      │
                      ▼
               Supervisor Agent
                      │
      ┌───────────────┼───────────────┐
      ▼               ▼               ▼
 Research Agent   Analyst Agent   Writer Agent
      │               │               │
      └───────────────┼───────────────┘
                      │
                      ▼
             Final Intelligence Report
```

---

# 📂 Project Structure

```
competitive-intelligence-crew/

│
├── app.py
├── crew.py
├── config.py
├── requirements.txt
├── .env
│
├── agents/
│     researcher.py
│     analyst.py
│     writer.py
│
├── tools/
│     web_search.py
│     rag_search.py
│     citations.py
│
├── reports/
│     report.md
│     report.html
│     report.pdf
│
├── data/
│
├── frontend/
│     streamlit_app.py
│
└── backend/
      main.py
```

---

# ⚙ Installation

Clone repository

```bash
git clone https://github.com/yourusername/competitive-intelligence-crew.git

cd competitive-intelligence-crew
```

Create virtual environment

```bash
python -m venv venv
```

Activate

Windows

```bash
venv\Scripts\activate
```

Linux/Mac

```bash
source venv/bin/activate
```

Install packages

```bash
pip install -r requirements.txt
```

---

# 🔑 Environment Variables

Create a `.env`

```env
OPENROUTER_API_KEY=YOUR_API_KEY

OPENROUTER_MODEL=openai/gpt-4.1-mini

MAX_STEPS=20

MAX_SOURCES=15

CACHE_ENABLED=true

LOG_LEVEL=INFO
```

---

# ▶ Running the Application

Backend

```bash
uvicorn backend.main:app --reload
```

Frontend

```bash
streamlit run frontend/streamlit_app.py
```

---

# Workflow

```
Research

↓

Collect Sources

↓

Analyze

↓

Validate Citations

↓

Generate Report

↓

Export
```

---

# Failure Handling

The system gracefully handles:

✅ Source timeout

✅ Website unavailable

✅ Missing information

✅ Duplicate articles

✅ Invalid URLs

Instead of stopping execution, the report continues and logs unavailable sources.

---

# Governance

Every published claim must include a citation.

Unverified information is:

- Removed
- Or clearly marked as unverified

No unsupported claims appear in the final report.

---

# Evaluation

The project evaluates:

- Citation Coverage
- Faithfulness
- Hallucination Detection
- Trace Correctness
- Tool Usage
- Response Quality

---

# Output Formats

Reports can be exported as

- Markdown
- HTML
- PDF
- JSON

---

# Example Report

```
Executive Summary

Competitor A reduced enterprise pricing by 12%.

Source:
https://...

---

Market Signals

Demand for AI automation increased significantly.

Source:
https://...
```

---

# Technologies Used

- Python
- CrewAI
- LangGraph
- FastAPI
- Streamlit
- OpenRouter
- ChromaDB
- FAISS
- DuckDuckGo Search
- BeautifulSoup
- Pydantic

---

# Future Improvements

- Scheduled weekly reports
- Email delivery
- Slack integration
- Interactive dashboards
- Fact-check agent
- Human approval workflow

---

# License

MIT License

---

# Author

Developed as part of the **Competitive Intelligence Briefing Crew** capstone project.
