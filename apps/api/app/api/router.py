from fastapi import APIRouter

from app.api.routes import (
    career,
    chat,
    computer,
    context,
    cost,
    english,
    evaluation,
    growth,
    health,
    intelligence,
    investment,
    knowledge,
    learning,
    memory,
    memory_network,
    memory_shadow,
    models,
    monitoring,
    notifications,
    observatory,
    onboarding,
    orchestrator,
    personality,
    proactive,
    profile,
    research,
    semantic,
    system,
    tools,
    ui,
    voice,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
api_router.include_router(orchestrator.router, tags=["orchestrator"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(career.router, tags=["career"])
api_router.include_router(
    evaluation.router,
    prefix="/evaluation",
    tags=["evaluation"],
)
api_router.include_router(english.router, tags=["english"])
api_router.include_router(intelligence.router, tags=["intelligence"])
api_router.include_router(research.router, tags=["research"])
api_router.include_router(investment.router, tags=["investment"])
api_router.include_router(monitoring.router, tags=["monitoring"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(learning.router, tags=["learning"])
api_router.include_router(memory.router, prefix="/memories", tags=["memories"])
api_router.include_router(
    memory_network.router,
    prefix="/memory-network",
    tags=["memory-network"],
)
api_router.include_router(
    memory_shadow.router,
    prefix="/memory-shadow",
    tags=["memory-shadow"],
)
api_router.include_router(semantic.router, prefix="/semantic", tags=["semantic"])
api_router.include_router(growth.router, tags=["growth"])
api_router.include_router(notifications.router, tags=["notifications"])
api_router.include_router(system.router, tags=["system"])
api_router.include_router(tools.router, tags=["tools", "approvals"])
api_router.include_router(observatory.router, tags=["observatory"])
api_router.include_router(cost.router, tags=["cost"])
api_router.include_router(context.router, tags=["context"])
api_router.include_router(personality.router, tags=["personality"])
api_router.include_router(proactive.router, tags=["proactive"])
api_router.include_router(computer.router, tags=["computer-use"])
api_router.include_router(ui.router, tags=["ui"])
api_router.include_router(voice.router, tags=["voice"])
