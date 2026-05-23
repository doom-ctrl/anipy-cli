"""
AniPy-CLI API Server
A FastAPI wrapper for anipy-api to serve anime data and streams.
"""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

from contextlib import asynccontextmanager
from typing import Optional
from enum import Enum

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

from anipy_api.provider import (
    get_provider,
    list_providers,
    LanguageTypeEnum,
    FilterCapabilities,
    Filters,
    Season,
)
from anipy_api.anime import Anime


# Provider enum for type safety
class ProviderEnum(str, Enum):
    animekai = "animekai"
    allanime = "allanime"
    native = "native"


# Language enum
class LanguageEnum(str, Enum):
    sub = "sub"
    dub = "dub"


# Global provider cache
_providers: dict[str, object] = {}


def get_cached_provider(name: str):
    """Get or create a cached provider instance."""
    if name not in _providers:
        _providers[name] = get_provider(name)
    return _providers[name]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("🚀 AniPy-CLI API starting up...")
    print(f"Available providers: {[p.NAME for p in list_providers()]}")
    yield
    print("👋 AniPy-CLI API shutting down...")


app = FastAPI(
    title="AniPy-CLI API",
    description="API for anime streaming and downloading",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Health & Info ============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "providers": [p.NAME for p in list_providers()]}


@app.get("/providers")
async def list_all_providers():
    """List all available providers."""
    return {
        "providers": [
            {
                "name": p.NAME,
                "base_url": p().BASE_URL,
                "filter_caps": {
                    "season": bool(p.FILTER_CAPS & FilterCapabilities.SEASON),
                    "year": bool(p.FILTER_CAPS & FilterCapabilities.YEAR),
                    "no_query": bool(p.FILTER_CAPS & FilterCapabilities.NO_QUERY),
                    "genre": bool(p.FILTER_CAPS & FilterCapabilities.GENRE),
                },
            }
            for p in list_providers()
        ]
    }


# ============ Search & Anime ============

@app.get("/search")
async def search_anime(
    query: str = Query(..., min_length=1, description="Search query"),
    provider: ProviderEnum = Query("allanime", description="Provider to use"),
):
    """Search for anime."""
    try:
        prov = get_cached_provider(provider)
        results = prov.get_search(query)
        return {
            "results": [
                {
                    "name": r.name,
                    "identifier": r.identifier,
                    "languages": list(r.languages),
                }
                for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/anime/{provider}/{identifier}")
async def get_anime_info(
    provider: ProviderEnum,
    identifier: str,
):
    """Get anime information."""
    try:
        prov = get_cached_provider(provider)
        anime = Anime(prov, identifier=identifier, languages=set())
        info = anime.get_info()
        return {
            "name": info.name,
            "description": info.description,
            "genres": info.genres,
            "image_url": info.image_url,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/anime/{provider}/{identifier}/episodes")
async def get_episodes(
    provider: ProviderEnum,
    identifier: str,
    lang: LanguageEnum = Query(LanguageEnum.sub, description="Language type"),
):
    """Get anime episodes."""
    try:
        prov = get_cached_provider(provider)
        lang_enum = LanguageTypeEnum.SUB if lang == LanguageEnum.sub else LanguageTypeEnum.DUB
        anime = Anime(prov, identifier=identifier, languages=set())
        episodes = anime.get_episodes(lang=lang_enum)
        return {"episodes": episodes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/anime/{provider}/{identifier}/video")
async def get_video(
    provider: ProviderEnum,
    identifier: str,
    episode: float = Query(..., description="Episode number"),
    lang: LanguageEnum = Query(LanguageEnum.sub, description="Language type"),
    quality: int = Query(720, description="Preferred quality (480, 720, 1080)"),
):
    """Get video stream URL for an episode."""
    try:
        prov = get_cached_provider(provider)
        lang_enum = LanguageTypeEnum.SUB if lang == LanguageEnum.sub else LanguageTypeEnum.DUB
        anime = Anime(prov, identifier=identifier, languages=set())
        video = anime.get_video(
            episode=episode,
            lang=lang_enum,
            preferred_quality=quality,
        )
        return {
            "url": video.url,
            "resolution": video.resolution,
            "episode": video.episode,
            "language": video.language,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/anime/{provider}/{identifier}/videos")
async def get_all_videos(
    provider: ProviderEnum,
    identifier: str,
    episode: float = Query(..., description="Episode number"),
    lang: LanguageEnum = Query(LanguageEnum.sub, description="Language type"),
):
    """Get all video streams for an episode."""
    try:
        prov = get_cached_provider(provider)
        lang_enum = LanguageTypeEnum.SUB if lang == LanguageEnum.sub else LanguageTypeEnum.DUB
        anime = Anime(prov, identifier=identifier, languages=set())
        videos = anime.get_videos(episode=episode, lang=lang_enum)
        return {
            "videos": [
                {
                    "url": v.url,
                    "resolution": v.resolution,
                    "episode": v.episode,
                    "language": v.language,
                }
                for v in videos
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Main ============

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)