"""frontend/styles.py - Premium SaaS Dashboard Styles"""

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
*,*::before,*::after{box-sizing:border-box;}
html,body{font-family:'Inter',system-ui,sans-serif!important;background:#F8FAFC!important;font-size:16px;}
#MainMenu,footer,[data-testid="stToolbar"],header{visibility:hidden!important;display:none!important;}
[data-testid="stAppViewContainer"]{background:#F8FAFC!important;}
[data-testid="block-container"]{padding-top:16px!important;padding-bottom:40px!important;max-width:1280px!important;}

/* SIDEBAR WIDTH + BACKGROUND */
section[data-testid="stSidebar"]{min-width:340px!important;max-width:360px!important;background:#10233F!important;border-right:1px solid #1A3050!important;box-shadow:4px 0 24px rgba(0,0,0,0.35)!important;}
section[data-testid="stSidebar"]>div:first-child{padding:0!important;}

/* SIDEBAR TEXT */
section[data-testid="stSidebar"] *{color:#CBD5E1!important;font-family:'Inter',sans-serif!important;}
section[data-testid="stSidebar"] h1,section[data-testid="stSidebar"] h2,section[data-testid="stSidebar"] h3{color:#FFFFFF!important;}
section[data-testid="stSidebar"] label{color:#94B8D8!important;font-size:11px!important;font-weight:700!important;text-transform:uppercase!important;letter-spacing:0.09em!important;}

/* SIDEBAR INPUTS - full width, readable text */
section[data-testid="stSidebar"] input{background:#1E3356!important;border:1.5px solid #2E4A6E!important;border-radius:10px!important;color:#FFFFFF!important;font-size:15px!important;width:100%!important;}
section[data-testid="stSidebar"] textarea{background:#1E3356!important;border:1.5px solid #2E4A6E!important;border-radius:10px!important;color:#FFFFFF!important;font-size:15px!important;width:100%!important;min-height:180px!important;overflow-y:auto!important;resize:vertical!important;}
section[data-testid="stSidebar"] input::placeholder,section[data-testid="stSidebar"] textarea::placeholder{color:#5A7A96!important;}
section[data-testid="stSidebar"] input:focus,section[data-testid="stSidebar"] textarea:focus{outline:2px solid #2563EB!important;outline-offset:1px!important;border-color:#2563EB!important;}

/* SIDEBAR SELECT / MULTISELECT */
section[data-testid="stSidebar"] [data-baseweb="select"]>div{background:#1E3356!important;border:1.5px solid #2E4A6E!important;border-radius:10px!important;min-height:44px!important;}
section[data-testid="stSidebar"] [data-baseweb="select"] [data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] [data-baseweb="select"] span,
section[data-testid="stSidebar"] [data-baseweb="select"] div{color:#FFFFFF!important;font-size:15px!important;}
section[data-testid="stSidebar"] [data-baseweb="select"] svg{fill:#94B8D8!important;}
section[data-testid="stSidebar"] [data-baseweb="tag"]{background:#1D4ED8!important;border-radius:6px!important;}
section[data-testid="stSidebar"] [data-baseweb="tag"] span{color:#FFFFFF!important;font-size:13px!important;}

/* SIDEBAR SLIDER */
section[data-testid="stSidebar"] [data-testid="stThumbValue"]{color:#93C5FD!important;font-size:13px!important;}
section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] [role="slider"]{background:#2563EB!important;}

/* SIDEBAR TOGGLE */
section[data-testid="stSidebar"] [data-testid="stToggleLabel"]{color:#CBD5E1!important;font-size:14px!important;}

/* SIDEBAR CUSTOM CLASSES */
.sb-logo{background:rgba(255,255,255,0.04);border-radius:12px;padding:20px 16px;text-align:center;margin:16px 12px 8px 12px;border:1px solid rgba(255,255,255,0.07);}
.sb-logo-icon{font-size:2.6rem;line-height:1;}
.sb-logo-title{font-size:1rem!important;font-weight:800!important;color:#FFFFFF!important;margin-top:6px;display:block;}
.sb-logo-sub{font-size:0.7rem!important;color:#5A7A96!important;margin-top:3px;display:block;}
.sb-section{font-size:10px!important;font-weight:800!important;text-transform:uppercase!important;letter-spacing:0.12em!important;color:#3A6080!important;margin:20px 0 8px 0!important;padding-top:16px!important;border-top:1px solid rgba(255,255,255,0.06)!important;display:block;}
.sb-chip{display:inline-block;background:rgba(37,99,235,0.2);border:1px solid rgba(37,99,235,0.4);color:#93C5FD!important;border-radius:20px;padding:3px 10px;font-size:12px!important;font-weight:600!important;margin:2px;max-width:145px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;vertical-align:middle;}
.sb-warn{font-size:13px!important;color:#FCA5A5!important;}
.sb-footer{text-align:center;font-size:11px!important;color:#3A6080!important;padding:8px 0 4px 0;}

/* HERO HEADER */
.hero-card{background:linear-gradient(135deg,#0D1B2A 0%,#1E3A5F 50%,#2D5986 100%);padding:36px 40px 30px 40px;border-radius:18px;margin-bottom:20px;box-shadow:0 8px 32px rgba(13,27,42,0.4);position:relative;overflow:hidden;}
.hero-card::after{content:"";position:absolute;top:-50%;right:-5%;width:500px;height:500px;background:radial-gradient(circle,rgba(100,170,255,0.1) 0%,transparent 65%);pointer-events:none;}
.hero-card h1{color:#FFFFFF!important;font-size:34px!important;font-weight:800!important;margin:0 0 10px 0!important;letter-spacing:-0.03em!important;line-height:1.2!important;}
.hero-card p{color:#93C5FD!important;font-size:16px!important;margin:0 0 18px 0!important;line-height:1.55;max-width:640px;}
.hero-badges{display:flex;gap:8px;flex-wrap:wrap;}
.hero-badge{background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);color:#BFDBFE!important;padding:4px 12px;border-radius:20px;font-size:12px!important;font-weight:600!important;}

/* METRIC CARDS */
[data-testid="stMetric"]{background:#FFFFFF!important;border-radius:12px!important;padding:16px 20px!important;box-shadow:0 1px 3px rgba(0,0,0,0.08)!important;border:1px solid #E5E7EB!important;border-top:3px solid #2563EB!important;}
[data-testid="stMetricLabel"]{font-size:11px!important;font-weight:700!important;color:#6B7280!important;text-transform:uppercase!important;letter-spacing:0.05em!important;}
[data-testid="stMetricValue"]{font-size:26px!important;font-weight:800!important;color:#111827!important;line-height:1.15!important;}

/* FEATURE CARDS */
.feat-card{background:#FFFFFF;border-radius:14px;padding:24px 22px;box-shadow:0 1px 3px rgba(0,0,0,0.08);border:1px solid #E5E7EB;height:100%;transition:transform 0.2s,box-shadow 0.2s;}
.feat-card:hover{transform:translateY(-4px);box-shadow:0 12px 32px rgba(37,99,235,0.14);border-color:#BFDBFE;}
.feat-icon{font-size:2rem;background:#EFF6FF;width:56px;height:56px;border-radius:14px;display:flex;align-items:center;justify-content:center;margin-bottom:14px;}
.feat-title{font-size:16px;font-weight:700;color:#111827;margin-bottom:8px;}
.feat-desc{font-size:14px;color:#6B7280;line-height:1.6;}
.feat-tag{display:inline-block;margin-top:12px;background:#EFF6FF;color:#1E40AF;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;}

/* BUTTONS */
.stButton>button{border-radius:10px!important;font-size:15px!important;font-weight:600!important;transition:all 0.18s!important;}
.stButton>button[kind="primary"]{background:#2563EB!important;border:none!important;color:#FFFFFF!important;padding:10px 24px!important;box-shadow:0 4px 14px rgba(37,99,235,0.35)!important;}
.stButton>button[kind="primary"]:hover{background:#1D4ED8!important;box-shadow:0 6px 20px rgba(37,99,235,0.45)!important;transform:translateY(-1px)!important;}
.stButton>button[kind="primary"]:focus{outline:2px solid #2563EB!important;outline-offset:3px!important;}
.stButton>button:not([kind="primary"]){border:1.5px solid #D1D5DB!important;color:#374151!important;background:#FFFFFF!important;}
.stButton>button:not([kind="primary"]):hover{border-color:#2563EB!important;color:#2563EB!important;background:#EFF6FF!important;}

/* TABS */
.stTabs [data-baseweb="tab-list"]{background:#FFFFFF!important;border-radius:12px!important;padding:6px!important;box-shadow:0 1px 3px rgba(0,0,0,0.08)!important;border:1px solid #E5E7EB!important;gap:2px!important;flex-wrap:wrap!important;}
.stTabs [data-baseweb="tab"]{border-radius:8px!important;font-size:13px!important;font-weight:600!important;color:#6B7280!important;padding:7px 14px!important;transition:all 0.15s!important;}
.stTabs [data-baseweb="tab"]:hover{background:#F3F4F6!important;color:#111827!important;}
.stTabs [aria-selected="true"]{background:linear-gradient(135deg,#1E3A5F,#2563EB)!important;color:#FFFFFF!important;box-shadow:0 2px 8px rgba(37,99,235,0.3)!important;}
.stTabs [data-baseweb="tab-panel"]{padding-top:20px!important;}

/* REPORT CARD */
.report-card{background:#FFFFFF;border-radius:14px;padding:32px 36px;box-shadow:0 1px 3px rgba(0,0,0,0.08);border:1px solid #E5E7EB;line-height:1.8;font-size:15px;color:#1F2937;}
.report-card h1{font-size:26px!important;font-weight:800!important;color:#0D1B2A!important;}
.report-card h2{font-size:20px!important;font-weight:700!important;color:#1E3A5F!important;border-bottom:2px solid #E5E7EB!important;padding-bottom:8px!important;margin-top:32px!important;}
.report-card h3{font-size:17px!important;font-weight:700!important;color:#374151!important;}
.report-card table{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;}
.report-card th{background:#1E3A5F;color:#FFFFFF;padding:10px 14px;text-align:left;font-weight:600;font-size:13px;}
.report-card td{padding:9px 14px;border-bottom:1px solid #F3F4F6;color:#374151;}
.report-card tr:nth-child(even) td{background:#F9FAFB;}
.report-card blockquote{border-left:4px solid #2563EB;background:#EFF6FF;padding:12px 16px;border-radius:0 8px 8px 0;margin:16px 0;font-style:italic;color:#1E40AF;}
.report-card code{background:#F3F4F6;padding:2px 6px;border-radius:4px;font-size:13px;color:#1E3A5F;font-family:monospace;}

/* SECTION HEADERS */
.sec-hdr{display:flex;align-items:center;gap:10px;padding:10px 16px;background:linear-gradient(135deg,#0D1B2A,#1E3A5F);border-radius:10px;margin:4px 0 16px 0;}
.sec-hdr-icon{font-size:1.1rem;}
.sec-hdr-text{font-size:14px;font-weight:700;color:#FFFFFF!important;letter-spacing:0.01em;}

/* INFO BOXES */
.box-info{background:#EFF6FF;border:1px solid #BFDBFE;border-left:4px solid #2563EB;border-radius:10px;padding:14px 18px;margin:12px 0;font-size:14px;color:#1E40AF;line-height:1.55;}
.box-warn{background:#FFFBEB;border:1px solid #FDE68A;border-left:4px solid #F59E0B;border-radius:10px;padding:14px 18px;margin:12px 0;font-size:14px;color:#92400E;}
.box-success{background:#F0FDF4;border:1px solid #86EFAC;border-left:4px solid #22C55E;border-radius:10px;padding:14px 18px;margin:12px 0;font-size:14px;color:#166534;}

/* BADGES */
.badge{display:inline-flex;align-items:center;gap:5px;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;}
.badge-completed{background:#DCFCE7;color:#15803D;border:1px solid #86EFAC;}
.badge-running{background:#DBEAFE;color:#1D4ED8;border:1px solid #93C5FD;}
.badge-failed{background:#FEE2E2;color:#DC2626;border:1px solid #FCA5A5;}
.badge-pending{background:#FEF3C7;color:#D97706;border:1px solid #FDE68A;}

/* RUN STATUS BAR */
.run-bar{background:#FFFFFF;border-radius:12px;padding:12px 20px;display:flex;align-items:center;gap:16px;box-shadow:0 1px 3px rgba(0,0,0,0.08);border:1px solid #E5E7EB;margin-bottom:16px;flex-wrap:wrap;}
.run-id{background:#F3F4F6;border-radius:6px;padding:3px 10px;font-family:monospace;font-size:13px;color:#374151;font-weight:600;}
.run-chip{font-size:13px;color:#6B7280;}

/* STEP PILLS */
.steps-row{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 16px 0;}
.step-pill{padding:5px 14px;border-radius:20px;font-size:12px;font-weight:600;background:#F3F4F6;color:#6B7280;border:1px solid #E5E7EB;}
.step-pill.active{background:#DBEAFE;color:#1D4ED8;border-color:#93C5FD;}
.step-pill.done{background:#DCFCE7;color:#15803D;border-color:#86EFAC;}

/* PROGRESS */
.stProgress>div{background:#E5E7EB!important;border-radius:10px!important;height:8px!important;}
.stProgress>div>div{background:linear-gradient(90deg,#1E3A5F,#2563EB)!important;border-radius:10px!important;}

/* HOW IT WORKS */
.how-card{background:#FFFFFF;border-radius:14px;padding:20px 24px;box-shadow:0 1px 3px rgba(0,0,0,0.08);border:1px solid #E5E7EB;}
.step-row{display:flex;align-items:center;gap:6px;flex-wrap:wrap;}
.step-box{background:#F8FAFC;border:1px solid #E5E7EB;border-radius:10px;padding:10px 14px;text-align:center;flex:1;min-width:90px;}
.step-num{width:26px;height:26px;background:#2563EB;color:white;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;margin-bottom:6px;}
.step-lbl{font-size:12px;font-weight:600;color:#374151;}
.step-arr{color:#9CA3AF;font-size:18px;padding:0 2px;}

/* EXPANDERS */
.streamlit-expanderHeader{background:#F9FAFB!important;border-radius:8px!important;font-weight:600!important;font-size:14px!important;color:#374151!important;border:1px solid #E5E7EB!important;}

/* DATAFRAME */
.stDataFrame{border-radius:12px!important;overflow:hidden!important;}

/* REVIEW HEADER */
.review-hdr{background:linear-gradient(135deg,#1E3A5F,#2D5986);border-radius:14px;padding:20px 24px;margin-bottom:16px;display:flex;align-items:center;gap:16px;}
.review-hdr-icon{font-size:2.2rem;}
.review-hdr-title{font-size:18px;font-weight:700;color:#FFFFFF!important;}
.review-hdr-sub{font-size:13px;color:#93C5FD!important;margin-top:3px;}

/* DIVIDER */
hr{border:none!important;border-top:1px solid #E5E7EB!important;margin:20px 0!important;}

/* ── MISSING UTILITY CLASSES (used by dashboard + components) ── */

/* Hero header */
.main-header{background:linear-gradient(135deg,#0D1B2A 0%,#1E3A5F 50%,#2D5986 100%);padding:32px 36px 26px 36px;border-radius:18px;margin-bottom:16px;box-shadow:0 8px 32px rgba(13,27,42,0.35);color:#FFFFFF;}
.main-header h1{color:#FFFFFF!important;font-size:34px!important;font-weight:800!important;margin:0 0 8px 0!important;letter-spacing:-0.02em!important;line-height:1.2!important;}
.main-header p{color:#93C5FD!important;font-size:16px!important;margin:0 0 14px 0!important;line-height:1.6;}
.header-badges{display:flex;gap:8px;flex-wrap:wrap;}
.header-badge{background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.22);color:#BFDBFE!important;padding:4px 13px;border-radius:20px;font-size:12px!important;font-weight:600!important;}

/* Section header bar — used by dashboard, report_tabs, export_panel */
.section-header{display:flex;align-items:center;gap:10px;padding:10px 16px;background:linear-gradient(135deg,#0D1B2A,#1E3A5F);border-radius:10px;margin:4px 0 14px 0;}
.sh-icon{font-size:1.05rem;}
.sh-title{font-size:14px;font-weight:700;color:#FFFFFF!important;letter-spacing:0.01em;}

/* Info / warning / success boxes — used by human_review + evaluation tab */
.info-box{background:#EFF6FF;border:1px solid #BFDBFE;border-left:4px solid #2563EB;border-radius:10px;padding:14px 18px;margin:10px 0;font-size:14px;color:#1E40AF;line-height:1.6;display:flex;gap:12px;align-items:flex-start;}
.ib-icon{font-size:1.3rem;flex-shrink:0;margin-top:2px;}
.ib-text{flex:1;}
.warn-box{background:#FFFBEB;border:1px solid #FDE68A;border-left:4px solid #F59E0B;border-radius:10px;padding:12px 16px;margin:8px 0;font-size:13px;color:#92400E;line-height:1.55;}
.wb-text{flex:1;}
.success-box{background:#F0FDF4;border:1px solid #86EFAC;border-left:4px solid #22C55E;border-radius:10px;padding:12px 16px;margin:8px 0;font-size:13px;color:#166534;line-height:1.55;}

/* SCROLLBAR */
::-webkit-scrollbar{width:6px;height:6px;}
::-webkit-scrollbar-track{background:#F1F5F9;border-radius:3px;}
::-webkit-scrollbar-thumb{background:#CBD5E1;border-radius:3px;}
::-webkit-scrollbar-thumb:hover{background:#94A3B8;}

/* ANIMATIONS */
@keyframes fadeUp{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:translateY(0);}}
.hero-card,[data-testid="stMetric"],.feat-card{animation:fadeUp 0.35s ease both;}

/* RESPONSIVE */
@media(max-width:768px){
  .hero-card{padding:20px!important;}
  .hero-card h1{font-size:22px!important;}
  [data-testid="block-container"]{padding:8px 10px!important;}
}
</style>
"""

INDUSTRIES = [
    "SaaS / CRM", "Fintech / Payments", "AI / LLM / Generative AI",
    "E-commerce / Retail", "Healthcare SaaS", "Cybersecurity",
    "Cloud Infrastructure", "HR Tech", "MarTech / AdTech",
    "EdTech", "LegalTech", "PropTech", "Supply Chain Tech",
    "Autonomous Vehicles", "Semiconductors", "Custom...",
]
REGIONS = [
    "Global", "North America", "Europe", "Asia Pacific",
    "Latin America", "Middle East & Africa", "United States",
    "United Kingdom", "India", "Southeast Asia",
]
TIME_PERIODS = [
    "last 7 days", "last 14 days", "last 30 days",
    "last 60 days", "last 90 days", "last 6 months",
]
EXPORT_FORMATS = ["markdown", "pdf", "pptx", "html", "json"]
STATUS_COLORS = {
    "completed": "🟢", "running": "🔵", "failed": "🔴",
    "pending": "🟡", "rejected": "🟠",
}
AGENT_STEPS = [
    ("🔍", "Research"), ("📊", "Analysis"), ("✍️", "Writing"),
    ("🛡️", "Review"), ("📦", "Export"),
]
