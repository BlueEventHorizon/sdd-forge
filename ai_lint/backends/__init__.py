"""判定 backend の実装と、名前からの生成。"""

from __future__ import annotations

from ai_lint.backend import Backend, BackendError

BACKEND_NAMES = ("jev",)


def create_backend(name: str) -> Backend:
    if name == "jev":
        from ai_lint.backends.jev import JevBackend

        return JevBackend.from_environment()
    raise BackendError(
        f"未知の backend: {name}（使えるのは {', '.join(BACKEND_NAMES)}）"
    )
