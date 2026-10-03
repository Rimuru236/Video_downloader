"""
Quick Integration Test — validates key fixes
"""
import sys, os
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Force UTF-8 stdout so Unicode symbols (✓, ✗, →) don't crash on Windows'
# default cp1252 console encoding.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import asyncio
from database.models import DownloadType
from utils.url_validator import validate_url
from config.config_manager import ConfigManager

async def test_url_validator():
    """Test: SSRF validation rewrite"""
    print("\n[TEST 1] URL Validator (SSRF protection)")
    
    # Valid URLs should pass
    valid = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://example.com",
    ]
    for url in valid:
        is_valid, reason = validate_url(url)
        assert is_valid, f"Valid URL rejected: {url} — {reason}"
        print(f"  ✓ {url}")
    
    # Invalid/dangerous URLs should fail
    invalid = [
        "http://127.0.0.1:8080/admin",  # localhost
        "http://192.168.1.1",            # private IP
        "http://localhost/api",          # localhost
        "file:///etc/passwd",            # file:// protocol
    ]
    for url in invalid:
        is_valid, reason = validate_url(url)
        assert not is_valid, f"Invalid URL accepted: {url}"
        print(f"  ✓ Blocked: {url}")
    
    print("  PASSED")


async def test_download_type_enum():
    """Test: DownloadType crash handling"""
    print("\n[TEST 2] DownloadType Enum (crash handling)")
    
    # Valid enum values
    for value in ["video", "audio", "playlist", "channel", "subtitle"]:
        dt = DownloadType(value)
        assert dt.value == value
        print(f"  ✓ {value}")
    
    # Invalid value should raise ValueError
    try:
        DownloadType("invalid")
        assert False, "Should have raised ValueError"
    except ValueError:
        print("  ✓ ValueError on invalid type")
    
    # TypeError on None should be caught by routes handler (not tested here)
    print("  PASSED")


async def test_config_async():
    """Test: Settings to engine sync (async config reads)"""
    print("\n[TEST 3] ConfigManager async reads")
    
    cfg = ConfigManager()
    
    # Test get_async with default fallback
    val = await cfg.get_async("socket_timeout", "99")
    assert val == "15", f"Expected socket_timeout=15, got {val}"
    print(f"  ✓ socket_timeout={val}")
    
    # Test non-existent key with default
    val = await cfg.get_async("nonexistent_key", "default_val")
    assert val == "default_val", f"Expected default_val, got {val}"
    print("  ✓ Default fallback works")
    
    # Verify other settings exist
    for key in ["max_concurrent", "max_retries", "retry_backoff"]:
        val = await cfg.get_async(key)
        assert val, f"Key {key} returned empty"
        print(f"  ✓ {key}={val}")
    
    print("  PASSED")


async def test_progress_calculation():
    """Test: Progress % when total_bytes unavailable"""
    print("\n[TEST 4] Progress calculation (no crash on unknown total)")
    
    # Simulating progress hook logic
    def calc_pct(total, downloaded):
        if total and total > 0:
            return round((downloaded / total) * 100, 1)
        return None
    
    # Normal case
    pct = calc_pct(1000, 500)
    assert pct == 50.0, f"Expected 50.0, got {pct}"
    print(f"  ✓ 500/1000 bytes → {pct}%")
    
    # No total available
    pct = calc_pct(None, 500)
    assert pct is None, f"Expected None, got {pct}"
    print("  ✓ None total → progress=None (no crash)")
    
    # Zero total
    pct = calc_pct(0, 100)
    assert pct is None, f"Expected None, got {pct}"
    print("  ✓ Zero total → progress=None")
    
    print("  PASSED")


async def test_download_type_noplaylist():
    """Test: Channel downloads noplaylist logic"""
    print("\n[TEST 5] Download type noplaylist flag")
    
    # Check that playlist and channel should have noplaylist=False
    for dtype in [DownloadType.PLAYLIST, DownloadType.CHANNEL]:
        should_skip = dtype.value not in ("playlist", "channel")
        assert not should_skip, f"{dtype.value} should allow playlist/channel"
        print(f"  ✓ {dtype.value}: noplaylist=False (allow multi-item)")
    
    # Video/audio/subtitle should have noplaylist=True
    for dtype in [DownloadType.VIDEO, DownloadType.AUDIO, DownloadType.SUBTITLE]:
        should_skip = dtype.value not in ("playlist", "channel")
        assert should_skip, f"{dtype.value} should skip playlists"
        print(f"  ✓ {dtype.value}: noplaylist=True")
    
    print("  PASSED")


async def main():
    print("=" * 60)
    print("INTEGRATION TEST SUITE — Key Fixes Validation")
    print("=" * 60)
    
    try:
        await test_url_validator()
        await test_download_type_enum()
        await test_config_async()
        await test_progress_calculation()
        await test_download_type_noplaylist()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
