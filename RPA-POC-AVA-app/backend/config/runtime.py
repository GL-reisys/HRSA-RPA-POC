import os


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://frontend:3000",
]


def resolve_app_path(configured_path: str | None, default_relative_path: str) -> str:
    target_path = configured_path or default_relative_path
    if os.path.isabs(target_path):
        return target_path

    return os.path.join(BASE_DIR, target_path)


def resolve_upload_path(file_path: str, upload_root: str | None = None) -> str:
    if os.path.isabs(file_path):
        return file_path

    root_path = upload_root or resolve_app_path(os.getenv("UPLOAD_DIR"), "uploads")
    normalized_path = os.path.normpath(file_path)

    if normalized_path in (".", ""):
        return root_path

    if normalized_path.startswith("uploads/") or normalized_path == "uploads":
        normalized_path = normalized_path.removeprefix("uploads/").removeprefix("uploads")

    return os.path.join(root_path, normalized_path.lstrip("/"))


def get_port(default: int = 5000) -> int:
    return int(os.getenv("PORT", str(default)))


def get_allowed_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ALLOWED_ORIGINS")
    if not configured_origins:
        return DEFAULT_ALLOWED_ORIGINS

    origins = [origin.strip() for origin in configured_origins.split(",")]
    return [origin for origin in origins if origin]


def is_debug_enabled() -> bool:
    return os.getenv("FLASK_DEBUG", "0") == "1"
