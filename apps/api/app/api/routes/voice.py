from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db_session
from app.schemas.voice import (
    VoiceLoopStatus,
    VoiceSynthesisRequest,
    VoiceTranscription,
)
from app.services.notifications import get_or_create_preferences, quiet_hours_active
from app.services.voice_loop import (
    InvalidVoiceAudioError,
    VoiceLoopUnavailableError,
    get_voice_loop,
)

router = APIRouter(prefix="/voice")
RuntimeSettings = Annotated[Settings, Depends(get_settings)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def _voice_error(error: Exception) -> HTTPException:
    if isinstance(error, InvalidVoiceAudioError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))


async def _current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before using local voice",
        )
    return user


@router.get("/status", response_model=VoiceLoopStatus)
async def voice_status(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> VoiceLoopStatus:
    user = await _current_user(db)
    preference = await get_or_create_preferences(db, user.id)
    loop = get_voice_loop(settings)
    stt_ready, tts_ready = loop.readiness()
    reason = None
    if not settings.v3_voice_loop_enabled:
        reason = "feature_disabled"
    elif not stt_ready or not tts_ready:
        reason = "local_models_missing"
    return VoiceLoopStatus(
        enabled=settings.v3_voice_loop_enabled,
        state=loop.state,
        stt_ready=stt_ready,
        tts_ready=tts_ready,
        models_loaded=loop.adapter.loaded,
        quiet_active=quiet_hours_active(preference),
        idle_unload_seconds=settings.voice_model_idle_seconds,
        reason=reason,
    )


@router.post("/transcriptions", response_model=VoiceTranscription)
async def transcribe_voice(
    settings: RuntimeSettings,
    payload: bytes = Body(media_type="audio/wav", max_length=1_920_044),
) -> VoiceTranscription:
    try:
        result = await asyncio.to_thread(get_voice_loop(settings).transcribe, payload)
    except (InvalidVoiceAudioError, VoiceLoopUnavailableError) as error:
        raise _voice_error(error) from error
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        unavailable = VoiceLoopUnavailableError(str(error))
        raise _voice_error(unavailable) from error
    return VoiceTranscription(
        text=result.text,
        processing_ms=round(result.processing_ms, 2),
        audio_duration_ms=round(result.audio_duration_ms, 2),
    )


@router.post("/synthesis")
async def synthesize_voice(
    payload: VoiceSynthesisRequest,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> Response:
    user = await _current_user(db)
    preference = await get_or_create_preferences(db, user.id)
    if quiet_hours_active(preference):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Voice playback is paused during quiet hours",
        )
    try:
        result = await asyncio.to_thread(get_voice_loop(settings).synthesize, payload.text)
    except VoiceLoopUnavailableError as error:
        raise _voice_error(error) from error
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        unavailable = VoiceLoopUnavailableError(str(error))
        raise _voice_error(unavailable) from error
    return Response(
        content=result.wave_bytes,
        media_type="audio/wav",
        headers={"X-Jarvis-TTS-Ms": f"{result.processing_ms:.2f}"},
    )


@router.post("/unload", status_code=status.HTTP_204_NO_CONTENT)
async def unload_voice_models(settings: RuntimeSettings) -> Response:
    get_voice_loop(settings).unload()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
