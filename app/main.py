import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.agent import run_agent, stream_agent_thoughts
from app.auth import require_admin, require_api_key
from app.config import (
    ADMIN_SECRET_SOURCE,
    APP_NAME,
    APP_VERSION,
    BASE_DIR,
    COMPLIANCE_COUNTRY,
    DEFAULT_PRIVACY_LAYER,
    SCRAPER_API_KEY,
    STOCKARGOS_WEBHOOK_URL,
    admin_secret_is_insecure,
)
from app.compliance.policy import PolicyEngine, get_policy_status
from app.compliance.risk_gate import ProxyRequired, RiskCapabilityOff, get_status as get_risk_status
from app.compliance.gdpr_gate import apply_gdpr_gate, scan_for_pii
from app.compliance.layers import list_layers, resolve_layer
from app.seo_autopsy import seo_autopsy
from app.api_echo import api_echo
from app.passive.commoncrawl import common_crawl_lookup, common_crawl_search_text
from app.osint.investigate import investigate
from app.intelligence.pipeline import detective_scrape
from app.llm import build_chat_reply, get_llm_status, parse_user_command
from app.predictive import (
    get_suggestions_for_context,
    record_user_context,
    run_predictive_cycle,
    start_predictive_background,
)
from app.probe.orchestrator import get_probe_capabilities, run_active_probe
from app.probe.pheromones import (
    flush_all as flush_pheromones,
    get_backend_status,
    init_pheromone_table,
    list_pheromones,
    pheromone_map,
    telemetry as pheromone_telemetry,
)
from app.vision import get_vision_capabilities, vision_scrape
from app.inbox import (
    get_inbox_messages,
    get_inbox_status,
    get_submissions,
    init_inbox_tables,
    poll_inbox,
    start_inbox_background,
)
from app.multimodal.tiktok import analyze_tiktok
from app.integrations.stockargos import emit_signal, init_stockargos_tables, list_signals
from app.models import (
    AgentRequest,
    AgentResponse,
    ApiKeyCreate,
    ApiKeyListItem,
    ApiKeyResponse,
    ChatRequest,
    ChatResponse,
    ContextRequest,
    PredictiveSuggestionsResponse,
    ProbeRequest,
    StockArgosSignalRequest,
    TikTokAnalyzeRequest,
    DetectiveScrapeRequest,
    ApiEchoRequest,
    SeoAutopsyRequest,
    CommonCrawlRequest,
    OsintInvestigateRequest,
    GdprScanRequest,
    ApexRequest,
    CorporateIntelRequest,
    LawfulFallbackRequest,
    RiskAcknowledgeRequest,
    RiskCapabilitiesRequest,
    FlareSolverrRequest,
    LinkedInFetchRequest,
    GithubEmailsRequest,
    PheromoneFlushRequest,
    DashboardStats,
    LLMCommandJSON,
    ScrapeRequest,
    ScrapeResponse,
    SelfHealRequest,
    VisionScrapeRequest,
    UniversalScrapeBatchRequest,
    UniversalScrapeRequest,
    WaybackRequest,
)
from app.scraper import scrape_url
from app.self_heal import extract_with_healing
from app.store import (
    create_api_key,
    get_dashboard_stats,
    get_predictive_stats,
    init_db,
    list_api_keys,
    log_scrape,
    revoke_api_key,
    validate_api_key,
)
from app.universal_scraper import (
    get_scraper_capabilities,
    universal_scrape,
    universal_scrape_batch,
)
from app.wayback import temporal_analysis
from app.http_client import safe_get
from app.routers.workspace import router as workspace_router
from app.routers.research import router as research_router
from app.security.middleware import install_security_middleware
from app.security.ssrf import UnsafeURLError


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_pheromone_table()
    init_inbox_tables()
    init_stockargos_tables()
    start_predictive_background()
    start_inbox_background()
    yield


app = FastAPI(
    title=APP_NAME,
    description="ArgosScout — autonomous OSINT research OS with BYOK copilot",
    version=APP_VERSION,
    lifespan=lifespan,
)
install_security_middleware(app)
app.include_router(workspace_router)
app.include_router(research_router)

static_dir = BASE_DIR / "app" / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.exception_handler(UnsafeURLError)
async def unsafe_url_handler(_request, exc: UnsafeURLError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RiskCapabilityOff)
async def risk_cap_handler(_request, exc: RiskCapabilityOff):
    return JSONResponse(status_code=403, content={"detail": str(exc), "capability": exc.capability})


@app.exception_handler(ProxyRequired)
async def proxy_required_handler(_request, exc: ProxyRequired):
    return JSONResponse(status_code=403, content={"detail": str(exc), "capability": exc.capability, "proxy_required": True})


@app.get("/")
async def root():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def health():
    from app.config import RESEARCH_LAYERS_ENABLED, RESEARCH_LOCAL_ONLY, LLM_PROVIDER

    risk = get_risk_status()
    return {
        "status": "ok",
        "app": APP_NAME,
        "version": APP_VERSION,
        "scraper_api_configured": bool(SCRAPER_API_KEY),
        "llm": get_llm_status(),
        "scraperio": get_scraper_capabilities(),
        "vision": get_vision_capabilities(),
        "predictive": get_predictive_stats(),
        "probe": get_probe_capabilities(),
        "pheromones": get_backend_status(),
        "inbox": get_inbox_status(),
        "stockargos": {
            "webhook_configured": bool(STOCKARGOS_WEBHOOK_URL),
        },
        "privacy_layers": get_policy_status(DEFAULT_PRIVACY_LAYER, COMPLIANCE_COUNTRY),
        "security": {
            "ssrf_protection": True,
            "rate_limiting": True,
            "admin_secret_insecure": admin_secret_is_insecure(),
            "admin_secret_source": ADMIN_SECRET_SOURCE,
            "websocket_requires_api_key": True,
        },
        "risk": {
            "acknowledged": risk["acknowledged"],
            "any_enabled": risk["any_enabled"],
            "proxy_configured": bool(risk.get("proxy_configured")),
        },
        "research": {
            "layers_enabled": RESEARCH_LAYERS_ENABLED,
            "local_only": RESEARCH_LOCAL_ONLY or LLM_PROVIDER in {"rule", "ollama"},
            "workflows": ["discover_only", "discover_then_verify"],
            "executive_suite": True,
        },
    }


@app.get("/api/v1/dashboard", response_model=DashboardStats)
async def dashboard_stats():
    stats = get_dashboard_stats()
    return DashboardStats(
        total_api_keys=stats["total_api_keys"],
        active_api_keys=stats["active_api_keys"],
        total_scrapes=stats["total_scrapes"],
        scraper_api_configured=bool(SCRAPER_API_KEY),
        llm=get_llm_status(),
        scraperio=get_scraper_capabilities(),
    )


@app.get("/api/v1/llm/status")
async def llm_status():
    return get_llm_status()


# --- Admin ---


@app.post("/admin/keys", response_model=ApiKeyResponse, dependencies=[Depends(require_admin)])
async def admin_create_key(body: ApiKeyCreate):
    return ApiKeyResponse(**create_api_key(body.name, body.expires_days))


@app.get("/admin/keys", response_model=list[ApiKeyListItem], dependencies=[Depends(require_admin)])
async def admin_list_keys():
    return [ApiKeyListItem(**k) for k in list_api_keys()]


@app.delete("/admin/keys/{key_id}", dependencies=[Depends(require_admin)])
async def admin_revoke_key(key_id: str):
    if not revoke_api_key(key_id):
        raise HTTPException(status_code=404, detail="Key not found")
    return {"revoked": True, "id": key_id}


# --- Scrape ---


@app.post("/api/v1/scrape", response_model=ScrapeResponse)
async def api_scrape(body: ScrapeRequest, _key: dict = Depends(require_api_key)):
    try:
        result = scrape_url(body)
        log_scrape(str(body.url), "quick", items_count=1, success=True)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scrape failed: {e}")


@app.post("/api/v1/scrape/universal")
async def api_universal_scrape(body: UniversalScrapeRequest, _key: dict = Depends(require_api_key)):
    try:
        result = universal_scrape(
            url=str(body.url), author=body.author,
            content_type=body.content_type, max_items=body.max_items,
            production_mode=body.production_mode,
        )
        log_scrape(str(body.url), "universal", items_count=len(result.get("items", [])), success=result.get("success", True))
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Universal scrape failed: {e}")


@app.post("/api/v1/scrape/universal/batch")
async def api_universal_scrape_batch(body: UniversalScrapeBatchRequest, _key: dict = Depends(require_api_key)):
    try:
        return universal_scrape_batch(body.sources, max_items=body.max_items)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Batch scrape failed: {e}")


@app.get("/api/v1/scrape/capabilities")
async def scrape_capabilities():
    return get_scraper_capabilities()


@app.post("/api/v1/scrape/self-heal")
async def api_self_heal(body: SelfHealRequest, _key: dict = Depends(require_api_key)):
    try:
        resp = safe_get(str(body.url), timeout=15)
        result = extract_with_healing(resp.text, body.selectors, str(body.url))
        return {"url": str(body.url), "extracted": result, "status_code": resp.status_code}
    except UnsafeURLError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/v1/scrape/vision")
async def api_vision_scrape(body: VisionScrapeRequest, _key: dict = Depends(require_api_key)):
    try:
        result = vision_scrape(str(body.url), goal=body.goal, provider=body.llm_provider)
        log_scrape(str(body.url), "vision", items_count=1, success=result.get("success", False))
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Vision scrape failed: {e}")


@app.get("/api/v1/scrape/vision/capabilities")
async def vision_capabilities():
    return get_vision_capabilities()


@app.post("/api/v1/wayback")
async def api_wayback(body: WaybackRequest, _key: dict = Depends(require_api_key)):
    return temporal_analysis(str(body.url))


# --- Predictive Pre-Scraping ---


@app.post("/api/v1/predictive/context")
async def api_record_context(body: ContextRequest, _key: dict = Depends(require_api_key)):
    topics = record_user_context(body.message, body.llm_provider)
    return {"recorded_topics": topics, "count": len(topics)}


@app.get("/api/v1/predictive/suggestions", response_model=PredictiveSuggestionsResponse)
async def api_predictive_suggestions(message: str = "", _key: dict = Depends(require_api_key)):
    data = get_suggestions_for_context(message)
    return PredictiveSuggestionsResponse(**data)


@app.post("/api/v1/predictive/run")
async def api_predictive_run(_key: dict = Depends(require_api_key)):
    result = await run_predictive_cycle()
    return result


@app.get("/api/v1/predictive/stats")
async def api_predictive_stats(_key: dict = Depends(require_api_key)):
    return get_predictive_stats()


# --- Active Probe ---


@app.post("/api/v1/probe/run")
async def api_active_probe(body: ProbeRequest, _key: dict = Depends(require_api_key)):
    if not body.dry_run and not body.authorized_target:
        raise HTTPException(
            status_code=400,
            detail="Live probe requires authorized_target=true — confirm you may test this host.",
        )
    if not body.dry_run:
        from app.compliance.risk_gate import require_capability

        require_capability("authorized_surface_enum")
    try:
        result = await run_active_probe(
            str(body.url),
            modes=body.modes,
            goal=body.goal,
            urls=body.urls,
            dry_run=body.dry_run,
            temporal_offset_days=body.temporal_offset_days,
            swarm_workers=body.swarm_workers,
            provider=body.llm_provider,
            emit_stockargos=body.emit_stockargos,
            privacy_layer=body.privacy_layer,
            country=body.country,
        )
        log_scrape(str(body.url), "probe", items_count=len(body.modes))
        return result
    except UnsafeURLError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Active probe failed: {e}")


@app.get("/api/v1/probe/capabilities")
async def probe_capabilities():
    return get_probe_capabilities()


@app.get("/api/v1/probe/pheromones")
async def probe_pheromones(_key: dict = Depends(require_api_key)):
    return {
        "pheromones": list_pheromones(),
        "backend": get_backend_status(),
        "telemetry": pheromone_telemetry(),
        "map": pheromone_map(),
    }


@app.get("/api/v1/probe/pheromones/telemetry")
async def probe_pheromone_telemetry(_key: dict = Depends(require_api_key)):
    return pheromone_telemetry()


@app.post("/api/v1/probe/pheromones/flush")
async def probe_pheromone_flush(body: PheromoneFlushRequest, _key: dict = Depends(require_api_key)):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to flush pheromone routes.")
    return flush_pheromones()


# --- Multimodal TikTok ---


@app.post("/api/v1/multimodal/tiktok")
async def api_tiktok_analyze(body: TikTokAnalyzeRequest, _key: dict = Depends(require_api_key)):
    try:
        result = await asyncio.to_thread(analyze_tiktok, str(body.url), body.llm_provider)
        log_scrape(str(body.url), "tiktok", items_count=1, success=result.get("success", False))
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TikTok analysis failed: {e}")


# --- Inbox / Form Responses ---


@app.post("/api/v1/inbox/poll")
async def api_inbox_poll(_key: dict = Depends(require_api_key)):
    return await asyncio.to_thread(poll_inbox)


@app.get("/api/v1/inbox/submissions")
async def api_inbox_submissions(limit: int = 20, _key: dict = Depends(require_api_key)):
    return {"submissions": get_submissions(limit)}


@app.get("/api/v1/inbox/messages")
async def api_inbox_messages(
    submission_id: Optional[str] = None,
    limit: int = 20,
    _key: dict = Depends(require_api_key),
):
    return {"messages": get_inbox_messages(submission_id, limit)}


@app.get("/api/v1/inbox/status")
async def api_inbox_status(_key: dict = Depends(require_api_key)):
    return get_inbox_status()


# --- StockArgos Integration ---


@app.post("/api/v1/integrations/stockargos/signal")
async def api_stockargos_signal(body: StockArgosSignalRequest, _key: dict = Depends(require_api_key)):
    return emit_signal(
        signal_type=body.signal_type,
        title=body.title,
        content=body.content,
        source_url=body.source_url,
        metadata=body.metadata,
        auto_deliver=body.auto_deliver,
    )


@app.get("/api/v1/integrations/stockargos/signals")
async def api_stockargos_signals(limit: int = 20, _key: dict = Depends(require_api_key)):
    return {"signals": list_signals(limit)}


# --- Privacy Layers & Smart Detective (v6) ---


@app.get("/api/v1/compliance/layers")
async def api_compliance_layers():
    return get_policy_status()


@app.get("/api/v1/compliance/layer/{layer}")
async def api_compliance_layer_detail(layer: str):
    from app.compliance.layers import get_layer_profile, PrivacyLayer
    try:
        return get_layer_profile(PrivacyLayer(layer))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown layer: {layer}")


@app.post("/api/v1/compliance/gdpr-scan")
async def api_gdpr_scan(body: GdprScanRequest, _key: dict = Depends(require_api_key)):
    layer = resolve_layer(body.privacy_layer, body.country or COMPLIANCE_COUNTRY)
    findings = scan_for_pii(body.text)
    result = apply_gdpr_gate(body.text, layer)
    return {
        "layer": layer.value,
        "findings": findings,
        "scan_count": len(findings),
        **{k: result[k] for k in ("summary", "masked_count", "dropped_count", "kept_count", "gdpr_applied")},
        "sanitized_preview": str(result["data"])[:2000],
    }


@app.post("/api/v1/intelligence/detective")
async def api_detective_scrape(body: DetectiveScrapeRequest, _key: dict = Depends(require_api_key)):
    try:
        result = await detective_scrape(
            str(body.url), goal=body.goal,
            privacy_layer=body.privacy_layer or DEFAULT_PRIVACY_LAYER,
            country=body.country or COMPLIANCE_COUNTRY,
            passive_only=body.passive_only,
            provider=body.llm_provider,
        )
        log_scrape(str(body.url), "detective", items_count=1, success=result.get("success", False))
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Detective scrape failed: {e}")


@app.post("/api/v1/scrape/seo-autopsy")
async def api_seo_autopsy(body: SeoAutopsyRequest, _key: dict = Depends(require_api_key)):
    result = await asyncio.to_thread(seo_autopsy, str(body.url), body.fetch_sitemap)
    log_scrape(str(body.url), "seo_autopsy", items_count=len(result.get("sources", [])), success=result.get("success", False))
    return result


@app.post("/api/v1/scrape/api-echo")
async def api_api_echo(body: ApiEchoRequest, _key: dict = Depends(require_api_key)):
    result = await asyncio.to_thread(api_echo, str(body.url), body.llm_provider)
    return result


@app.post("/api/v1/passive/common-crawl")
async def api_common_crawl(body: CommonCrawlRequest, _key: dict = Depends(require_api_key)):
    if body.keyword:
        result = await asyncio.to_thread(common_crawl_search_text, str(body.url), body.keyword, body.limit)
    else:
        result = await asyncio.to_thread(common_crawl_lookup, str(body.url), body.limit)
    return result


@app.post("/api/v1/osint/investigate")
async def api_osint_investigate(body: OsintInvestigateRequest, _key: dict = Depends(require_api_key)):
    try:
        result = await asyncio.to_thread(
            investigate,
            name=body.name,
            url=body.url,
            tiktok_url=body.tiktok_url,
            country=body.country or COMPLIANCE_COUNTRY or "DE",
            company_name=body.company_name,
            privacy_layer=body.privacy_layer or DEFAULT_PRIVACY_LAYER,
            provider=body.llm_provider,
        )
        log_scrape(body.name or body.url or body.tiktok_url, "osint", items_count=len(result.get("sources_checked", [])))
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OSINT investigation failed: {e}")


@app.post("/api/v1/osint/corporate")
async def api_osint_corporate(body: CorporateIntelRequest, _key: dict = Depends(require_api_key)):
    from app.osint.corporate import corporate_intel

    result = await asyncio.to_thread(corporate_intel, body.name, body.url, body.country)
    log_scrape(body.name or body.url, "corporate", items_count=1, success=result.get("success", False))
    return result


@app.get("/api/v1/compliance/risk")
async def api_risk_notice():
    from app.compliance.risk_gate import get_notice

    return get_notice()


@app.get("/api/v1/compliance/risk/status")
async def api_risk_status(_key: dict = Depends(require_api_key)):
    return get_risk_status()


@app.post("/api/v1/compliance/risk/acknowledge")
async def api_risk_ack(body: RiskAcknowledgeRequest, _key: dict = Depends(require_api_key)):
    from app.compliance.risk_gate import acknowledge

    result = acknowledge(
        body.phrase,
        authorized_use=body.authorized_use,
        capabilities=body.capabilities,
        proxy_url=body.proxy_url or "",
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "Acknowledgment rejected")
    return result


@app.post("/api/v1/compliance/risk/capabilities")
async def api_risk_caps(body: RiskCapabilitiesRequest, _key: dict = Depends(require_api_key)):
    from app.compliance.risk_gate import update_capabilities

    result = update_capabilities(body.capabilities, proxy_url=body.proxy_url)
    if not result.get("ok"):
        err = result.get("error") or "Not acknowledged"
        status = 400 if "proxy" in err.lower() else 403
        raise HTTPException(status_code=status, detail=err)
    return result


@app.post("/api/v1/compliance/risk/revoke")
async def api_risk_revoke(_key: dict = Depends(require_api_key)):
    from app.compliance.risk_gate import revoke

    return revoke()


@app.post("/api/v1/recon/flaresolverr")
async def api_flaresolverr(body: FlareSolverrRequest, _key: dict = Depends(require_api_key)):
    from app.compliance.risk_gate import require_capability
    from app.recon.flaresolverr import fetch_via_flaresolverr

    require_capability("flaresolverr")
    result = await asyncio.to_thread(fetch_via_flaresolverr, str(body.url))
    log_scrape(str(body.url), "flaresolverr", items_count=1, success=result.get("ok", False))
    return result


@app.post("/api/v1/osint/linkedin")
async def api_linkedin(body: LinkedInFetchRequest, _key: dict = Depends(require_api_key)):
    from app.compliance.risk_gate import require_capability
    from app.osint.linkedin import fetch_linkedin_public

    require_capability("linkedin_public_fetch")
    result = await asyncio.to_thread(fetch_linkedin_public, str(body.url))
    log_scrape(str(body.url), "linkedin", items_count=1, success=result.get("ok", False))
    return result


@app.post("/api/v1/osint/github-emails")
async def api_github_emails(body: GithubEmailsRequest, _key: dict = Depends(require_api_key)):
    from app.compliance.risk_gate import require_capability
    from app.osint.github_emails import parse_repo, public_commit_emails

    require_capability("github_commit_emails")
    owner, repo = parse_repo(body.url or body.owner, body.repo)
    if not owner or not repo:
        raise HTTPException(status_code=400, detail="Provide owner and repo, or a github.com/owner/repo URL.")
    result = await asyncio.to_thread(public_commit_emails, owner, repo, limit=body.limit)
    log_scrape(f"{owner}/{repo}", "github_emails", items_count=result.get("count") or 0, success=result.get("ok", False))
    return result


@app.get("/api/v1/osint/graph")
async def api_osint_graph(_key: dict = Depends(require_api_key)):
    from app.osint.graph import snapshot

    return snapshot()


@app.post("/api/v1/recon/fallback")
async def api_recon_fallback(body: LawfulFallbackRequest, _key: dict = Depends(require_api_key)):
    from app.recon.fallback import lawful_fallback

    result = await asyncio.to_thread(lawful_fallback, str(body.url))
    log_scrape(str(body.url), "fallback", items_count=len(result.get("methods") or []), success=result.get("success", False))
    return result


@app.post("/api/v1/apex/run")
async def api_apex_run(body: ApexRequest, _key: dict = Depends(require_api_key)):
    from app.apex.orchestrator import run_apex

    result = await asyncio.to_thread(
        run_apex,
        body.target,
        privacy_layer=body.privacy_layer or DEFAULT_PRIVACY_LAYER,
        country=body.country or COMPLIANCE_COUNTRY,
        provider=body.llm_provider,
        include_people=body.include_people,
        include_corporate=body.include_corporate,
        include_archives=body.include_archives,
        include_live_probe=body.include_live_probe,
    )
    log_scrape(body.target[:100], "apex", items_count=len(result.get("citations") or []), success=result.get("success", False))
    return result


@app.get("/api/v1/apex/last")
async def api_apex_last(_key: dict = Depends(require_api_key)):
    from app.apex.orchestrator import last_apex

    data = last_apex()
    if not data:
        raise HTTPException(status_code=404, detail="No Apex dossier yet")
    return data


# --- ArgosScout Agent ---


@app.post("/api/v1/agent/research", response_model=AgentResponse)
async def api_agent_research(body: AgentRequest, _key: dict = Depends(require_api_key)):
    record_user_context(body.goal, body.llm_provider)
    result = await run_agent(
        body.goal, provider=body.llm_provider, model=body.llm_model,
        use_wayback=body.use_wayback, deep_scrape=body.deep_scrape,
        privacy_layer=body.privacy_layer, country=body.country,
        passive_only=body.passive_only,
    )
    log_scrape(body.goal[:100], "agent", items_count=result.get("sources_scraped", 0))
    if result.get("status") == "clarification_needed":
        return AgentResponse(status="clarification_needed", goal=body.goal, question=result.get("question"))
    return AgentResponse(
        status=result["status"], goal=result["goal"],
        synthesis=result.get("synthesis"),
        search_queries=result.get("search_queries", []),
        sources_found=result.get("sources_found", 0),
        sources_scraped=result.get("sources_scraped", 0),
        search_results=result.get("search_results", []),
        scraped=result.get("scraped", []),
        wayback=result.get("wayback", []),
    )


@app.websocket("/ws/agent")
async def ws_agent(websocket: WebSocket):
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        payload = json.loads(raw)
        api_key = payload.get("api_key", "")
        if not api_key or not validate_api_key(api_key):
            await websocket.send_json({"type": "error", "text": "Valid API key required"})
            await websocket.close(code=4401)
            return

        goal = payload.get("goal", payload.get("message", ""))
        if not goal:
            await websocket.send_json({"type": "error", "text": "Missing goal"})
            return

        async for event in stream_agent_thoughts(
            goal,
            provider=payload.get("llm_provider"),
            model=payload.get("llm_model"),
        ):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "text": str(e)})


# --- Chat ---


@app.post("/api/v1/chat", response_model=ChatResponse)
async def api_chat(body: ChatRequest, _key: dict = Depends(require_api_key)):
    record_user_context(body.message, body.llm_provider)
    command = parse_user_command(body.message, body.llm_provider, body.llm_model)
    scrape_result: Optional[ScrapeResponse] = None
    universal_result: Optional[dict[str, Any]] = None
    agent_result: Optional[dict[str, Any]] = None
    extra = None

    if body.execute_scrape and command.intent.value == "agent_research":
        agent_result = await run_agent(body.message, body.llm_provider, body.llm_model)
        extra = agent_result.get("synthesis", "")[:500]
    elif body.execute_scrape and command.intent.value == "vision_scrape" and command.urls:
        try:
            vision_result = vision_scrape(command.urls[0], goal=body.message, provider=body.llm_provider)
            extra = f"Vision OK — method: {vision_result.get('method')}"
            if body.json_only:
                return JSONResponse(content={"command": command.model_dump(), "vision_result": vision_result})
        except Exception as e:
            extra = f"Vision scrape failed: {e}"
    elif body.execute_scrape and command.urls:
        try:
            if command.scrape_mode in ("universal",) or command.intent.value == "universal_scrape":
                universal_result = universal_scrape(command.urls[0])
                extra = f"Scraper.io OK — {len(universal_result.get('items', []))} items"
            else:
                scrape_result = scrape_url(ScrapeRequest(url=command.urls[0], extract=command.extract))
                extra = f"Quick scrape OK — status {scrape_result.status_code}"
        except Exception as e:
            extra = f"Scrape failed: {e}"

    reply = build_chat_reply(command, extra)
    if body.json_only:
        return JSONResponse(content={
            "command": command.model_dump(),
            "scrape_result": scrape_result.model_dump() if scrape_result else None,
            "universal_result": universal_result,
            "agent_result": agent_result,
        })
    return ChatResponse(reply=reply, command=command, scrape_result=scrape_result)


@app.post("/api/v1/parse", response_model=LLMCommandJSON)
async def api_parse(body: ChatRequest, _key: dict = Depends(require_api_key)):
    return parse_user_command(body.message, body.llm_provider, body.llm_model)


@app.post("/api/v1/chat/public", response_model=ChatResponse)
async def public_chat(body: ChatRequest):
    command = parse_user_command(body.message, body.llm_provider, body.llm_model)
    reply = build_chat_reply(command)
    if body.json_only:
        return JSONResponse(content={"command": command.model_dump()})
    return ChatResponse(reply=reply, command=command)
