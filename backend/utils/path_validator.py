"""Path validator — prevents a client-supplied output_folder from escaping
the configured download root via directory traversal, an absolute-path
override, or a symlink.

Without this, `POST /download` accepted `output_folder` as a raw string and
handed it straight to yt-dlp/ffmpeg's file writer — a client could point it
anywhere the server process can write (or, via a crafted relative path, read
back the layout of directories it shouldn't see the existence of). This is
deliberately scoped to the per-request `output_folder` override on
`DownloadCreate`: the *global* `download_folder` and `cookies_file` settings
are admin-configured (via the now-authenticated Settings API) and are meant
to be able to point anywhere the admin chooses, so they are intentionally
left unrestricted here.
"""
from pathlib import Path
from typing import Optional


def validate_output_folder(candidate: Optional[str], allowed_roots: list[str]) -> tuple[bool, str]:
    """Returns (is_valid, resolved_path_or_reason).

    `candidate` must resolve — after following any ".." segments and any
    symlinks — to a path equal to, or nested under, one of `allowed_roots`.
    Both sides are resolved with the same normalization (`Path.resolve()`)
    so the comparison is meaningful regardless of how either was spelled
    (relative, trailing slash, symlinked directory, etc.). Resolution does
    not require the path to already exist — output directories are created
    on demand by the download engine.
    """
    if not candidate or not candidate.strip():
        return True, ""  # caller falls back to the configured default

    if not allowed_roots:
        return False, "No allowed download root is configured"

    try:
        resolved = Path(candidate).expanduser().resolve()
    except (OSError, ValueError) as exc:
        return False, f"Invalid path: {exc}"

    for root in allowed_roots:
        if not root or not root.strip():
            continue
        try:
            root_resolved = Path(root).expanduser().resolve()
        except (OSError, ValueError):
            continue
        if resolved == root_resolved or root_resolved in resolved.parents:
            return True, str(resolved)

    return False, "output_folder must be inside an allowed download directory"
