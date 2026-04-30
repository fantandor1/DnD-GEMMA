from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_session, init_db
from .prompts import PROTECTED_SYSTEM_PROMPT
from .schemas import CampaignCreatePayload, CampaignImportPayload, CampaignUpdatePayload, HeroUpdatePayload, MessageRequest, NoteCreatePayload, TtsRequestPayload
from .services import CampaignService, GameService, LMStudioClient
from .services.llm_service import LMStudioError
from .services.serialization import load_campaign, serialize_campaign
from .services.google_tts_service import GoogleTtsError, GoogleTtsSegment, synthesize_google_tts
from .services.tts_service import DEFAULT_GEMMA_VOICE, TtsSegment, synthesize_edge_tts


settings = get_settings()
app = FastAPI(title=settings.app_name)
init_db()

BASE_WEB_DIR = Path(__file__).resolve().parent / "web"
templates = Jinja2Templates(directory=str(BASE_WEB_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_WEB_DIR / "static")), name="static")


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    detail = f"{exc.__class__.__name__}: {exc}"
    return JSONResponse(
        status_code=500,
        content={"detail": detail, "status_code": 500},
    )


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    campaign_id: int | None = None,
    view: str = "dashboard",
    db: Session = Depends(get_session),
) -> HTMLResponse:
    llm_client = LMStudioClient(settings)
    available_models = llm_client.list_models()
    campaign_service = CampaignService(db, settings, available_models)
    campaigns = campaign_service.list_campaigns()
    if not campaigns:
        campaign_service.get_or_seed_default_campaign()
        campaigns = campaign_service.list_campaigns()
    selected = load_campaign(db, campaign_id) if campaign_id is not None else None
    if selected is None and campaigns:
        selected = campaigns[0]

    view_mode = "play" if view == "play" else "dashboard"
    snapshot = serialize_campaign(selected) if selected is not None else None
    return templates.TemplateResponse(
        request,
        "play.html" if view_mode == "play" else "index.html",
        {
            "campaigns": campaigns,
            "selected": snapshot,
            "available_models": available_models,
            "default_model": settings.default_model,
            "protected_rules_prompt": PROTECTED_SYSTEM_PROMPT,
            "view_mode": view_mode,
        },
    )


@app.get("/api/models")
def api_models() -> dict[str, list[str]]:
    models = LMStudioClient(settings).list_models()
    return {"models": models}


@app.post("/api/campaigns")
def create_campaign(
    payload: CampaignCreatePayload,
    db: Session = Depends(get_session),
) -> dict[str, int]:
    llm_client = LMStudioClient(settings)
    service = CampaignService(db, settings, llm_client.list_models())
    campaign = service.create_campaign(payload)
    return {"ok": True, "campaign_id": campaign.id}


@app.patch("/api/campaigns/{campaign_id}")
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdatePayload,
    db: Session = Depends(get_session),
) -> JSONResponse:
    llm_client = LMStudioClient(settings)
    service = CampaignService(db, settings, llm_client.list_models())
    try:
        campaign = service.update_campaign(campaign_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(jsonable_encoder({"ok": True, "campaign_id": campaign.id, "snapshot": serialize_campaign(campaign)}))


@app.delete("/api/campaigns/{campaign_id}")
def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_session),
) -> dict[str, bool]:
    service = CampaignService(db, settings)
    try:
        service.delete_campaign(campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/campaigns/{campaign_id}/messages")
def process_message(
    campaign_id: int,
    payload: MessageRequest,
    db: Session = Depends(get_session),
) -> JSONResponse:
    llm_client = LMStudioClient(settings, gemini_api_key=payload.api_key)
    service = GameService(db, settings, llm_client)
    try:
        snapshot = service.process_turn(campaign_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LMStudioError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return JSONResponse(jsonable_encoder({"ok": True, "campaign_id": campaign_id, "snapshot": snapshot}))


@app.post("/api/campaigns/{campaign_id}/import")
def import_campaign_memory(
    campaign_id: int,
    payload: CampaignImportPayload,
    db: Session = Depends(get_session),
) -> JSONResponse:
    llm_client = LMStudioClient(settings, gemini_api_key=payload.api_key)
    service = GameService(db, settings, llm_client)
    try:
        snapshot = service.import_transcript(campaign_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LMStudioError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return JSONResponse(jsonable_encoder({"ok": True, "campaign_id": campaign_id, "snapshot": snapshot}))


@app.post("/api/campaigns/{campaign_id}/notes")
def add_note(
    campaign_id: int,
    payload: NoteCreatePayload,
    db: Session = Depends(get_session),
) -> dict[str, int]:
    service = CampaignService(db, settings)
    try:
        campaign = service.add_note(campaign_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "campaign_id": campaign.id}


@app.patch("/api/campaigns/{campaign_id}/hero")
def update_hero(
    campaign_id: int,
    payload: HeroUpdatePayload,
    db: Session = Depends(get_session),
) -> JSONResponse:
    service = CampaignService(db, settings)
    try:
        campaign = service.update_hero(campaign_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(jsonable_encoder({"ok": True, "campaign_id": campaign.id, "snapshot": serialize_campaign(campaign)}))


@app.delete("/api/campaigns/{campaign_id}/notes/{note_id}")
def delete_note(
    campaign_id: int,
    note_id: int,
    db: Session = Depends(get_session),
) -> JSONResponse:
    service = CampaignService(db, settings)
    try:
        campaign = service.delete_note(campaign_id, note_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(jsonable_encoder({"ok": True, "campaign_id": campaign.id, "snapshot": serialize_campaign(campaign)}))


@app.post("/api/tts/edge")
async def edge_tts_audio(payload: TtsRequestPayload) -> Response:
    try:
        audio = await synthesize_edge_tts(
            TtsSegment(
                text=payload.segment.text,
                speaker=payload.segment.speaker,
                emotion=payload.segment.emotion,
                rate=payload.segment.rate,
                pitch=payload.segment.pitch,
            ),
            voice=payload.voice or DEFAULT_GEMMA_VOICE,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Edge TTS вернул ошибку: {exc}") from exc
    if not audio:
        raise HTTPException(status_code=400, detail="Нет текста для озвучки.")
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/api/tts/google")
async def google_tts_audio(payload: TtsRequestPayload) -> Response:
    try:
        audio = await asyncio.to_thread(
            synthesize_google_tts,
            settings,
            GoogleTtsSegment(
                text=payload.segment.text,
                speaker=payload.segment.speaker,
                emotion=payload.segment.emotion,
            ),
            payload.voice,
            payload.model,
            payload.api_key,
        )
    except GoogleTtsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=f"Google TTS вернул ошибку: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google TTS вернул ошибку: {exc}") from exc
    if not audio:
        raise HTTPException(status_code=400, detail="Нет текста для озвучки.")
    return Response(content=audio, media_type="audio/wav")


@app.get("/api/tts/silero/voices")
def silero_tts_voices() -> dict[str, object]:
    from .services.silero_tts_service import get_silero_tts

    tts = get_silero_tts()
    return {
        "voices": tts.speakers,
        "default_voice": tts.default_voice,
    }


@app.post("/api/tts/silero")
async def silero_tts_audio(payload: TtsRequestPayload) -> Response:
    from .services.silero_tts_service import SileroSegment, get_silero_tts

    try:
        audio = await asyncio.to_thread(
            get_silero_tts().synthesize,
            SileroSegment(
                text=payload.segment.text,
                speaker=payload.segment.speaker,
                emotion=payload.segment.emotion,
                rate=payload.segment.rate,
            ),
            payload.voice,
            None,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Silero TTS вернул ошибку: {exc}") from exc
    if not audio:
        raise HTTPException(status_code=400, detail="Нет текста для озвучки.")
    return Response(content=audio, media_type="audio/wav")
