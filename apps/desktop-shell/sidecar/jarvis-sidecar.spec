from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


project_root = Path(SPECPATH).parents[2]
api_root = project_root / "apps" / "api"
desktop_source = project_root / "apps" / "desktop" / "src"
entry = Path(SPECPATH) / "jarvis_sidecar.py"

datas = [
    (str(api_root / "alembic.ini"), "."),
    (str(api_root / "migrations"), "migrations"),
    (str(desktop_source / "jarvis_desktop" / "tts.vbs"), "jarvis_desktop"),
]
binaries = []
hiddenimports = [
    "app.main",
    "app.db.models",
    "jarvis_desktop.__main__",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    *collect_submodules("app"),
]

for package in (
    "aiosqlite",
    "asyncpg",
    "sherpa_onnx",
    "psycopg",
    "psycopg_pool",
    "mem0",
    "langgraph",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

analysis = Analysis(
    [str(entry)],
    pathex=[str(api_root), str(desktop_source)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="jarvis-sidecar",
    console=True,
    debug=False,
    strip=False,
    upx=False,
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="jarvis-sidecar",
)
