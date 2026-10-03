import sys, os
# Ensure backend/ on path
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import asyncio
from config.config_manager import ConfigManager
from core.downloader_engine import _build_ydl_opts, _make_progress_hook
from services.metadata_service import _fetch
from database.models import DownloadType

async def main():
    cfg = ConfigManager()
    val = await cfg.get_async('socket_timeout')
    print('Config socket_timeout:', val)
    print('DownloadType values:', [e.value for e in DownloadType])
    print('Modules imported OK')

if __name__ == '__main__':
    asyncio.run(main())
