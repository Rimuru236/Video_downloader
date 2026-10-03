"""REL-5: WebSocket disconnects should be noticed promptly (via an active
receive() loop), not only once the next keepalive ping's send() fails."""
import core.downloader_engine as engine


def test_progress_hook_is_unregistered_promptly_on_disconnect(client):
    download_id = "ws-disconnect-probe"
    with client.websocket_connect(f"/api/v1/ws/download/{download_id}"):
        assert download_id in engine._progress_hooks

    # The `with` block's exit sends a close frame. If disconnects were only
    # noticed via a failed send() on the next ping (the pre-fix behavior),
    # this registration could linger for up to ws_keepalive seconds. With
    # the receive() loop running concurrently, it should already be gone.
    assert download_id not in engine._progress_hooks


def test_connection_still_receives_pushed_progress(client):
    download_id = "ws-push-probe"
    with client.websocket_connect(f"/api/v1/ws/download/{download_id}") as ws:
        hooks = engine._progress_hooks.get(download_id, [])
        assert len(hooks) == 1
        import asyncio
        asyncio.run(hooks[0]({"download_id": download_id, "progress": 42}))
        msg = ws.receive_json()
        assert msg["progress"] == 42
