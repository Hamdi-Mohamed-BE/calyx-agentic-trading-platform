from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


ROOT = Path(__file__).resolve().parent

app = FastAPI(
    title="Calyx Agentic Trading Research",
    description="A portfolio-safe view of an evidence-first research and validation system.",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")


STAGES = [
    {
        "number": "01",
        "title": "Ingest research",
        "detail": "Browser, PDF and video-transcript tools turn papers and demonstrations into traceable strategy requirements.",
    },
    {
        "number": "02",
        "title": "Specify & challenge",
        "detail": "An expert-algo-trader workflow converts the idea into explicit rules, assumptions, parameters and failure cases.",
    },
    {
        "number": "03",
        "title": "Build & backtest",
        "detail": "Private adapters generate the implementation and run native MetaTrader 5 tests against up to five years of tick data.",
    },
    {
        "number": "04",
        "title": "Stress the evidence",
        "detail": "Cost shocks, chronological splits, block bootstrap, Monte Carlo paths and drawdown constraints test robustness.",
    },
    {
        "number": "05",
        "title": "Gate promotion",
        "detail": "A policy engine rejects fragile candidates and promotes survivors only to isolated demo forward testing.",
    },
    {
        "number": "06",
        "title": "Monitor forward tests",
        "detail": "Read-only telemetry surfaces drift, risk and operational health while the human remains the final authority.",
    },
]

CAPABILITIES = [
    "Research-paper and PDF extraction",
    "YouTube transcript analysis",
    "Browser-assisted evidence collection",
    "Point-in-time macro event joins",
    "Native MT5 report parsing",
    "10,000-path block bootstrap",
    "Monte Carlo drawdown analysis",
    "Deflated Sharpe probability",
    "Broker cost stress testing",
    "Prop-style loss-limit proxies",
    "Automated accept/reject gates",
    "Read-only forward-test monitoring",
]


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="portfolio_overview.html",
        context={"stages": STAGES, "capabilities": CAPABILITIES},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "calyx-portfolio"}
