from __future__ import annotations

import asyncio
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from orchestrator.events import AgentState  # noqa: E402
from orchestrator.main import Orchestrator  # noqa: E402


class RtspAndWebUiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.orch = object.__new__(Orchestrator)
        self.orch.agent_root = AGENT_ROOT
        self.orch.camera_enabled = True
        self.orch.camera_url = "rtsp://192.168.1.100:554/stream"
        self.orch.camera_rtsp_transport = "tcp"
        self.orch.camera_timeout = 2.0
        self.orch.camera_size = 448
        self.orch.camera_prompt = "描述画面"
        self.orch.camera_vlm_cmd = ""
        self.orch.camera_api_url = ""
        self.orch.camera_api_key = ""
        self.orch.camera_model = "test"
        self.orch._tts_abort = False
        self.orch._turn_busy = False
        self.orch._next_turn_id = 0
        self.orch._active_turn_id = 0
        self.orch._latest_camera_bytes = None
        self.orch._latest_camera_time = 0.0
        self.orch._scene_memory = {
            "caption": "桌上有一台笔记本电脑和一个水杯。",
            "updated_at": time.monotonic(),
        }
        self.orch.state = AgentState.IDLE
        self.orch.set_state = lambda s: setattr(self.orch, "state", s)
        self.orch.tts_queue = MagicMock()
        self.orch.tts_queue.abort = MagicMock()
        self.orch.tts_queue.mark_utterance_start = MagicMock()

        self.events: list[dict] = []

        async def fake_emit(ev: dict) -> None:
            self.events.append(ev)

        self.orch.emit = fake_emit  # type: ignore[method-assign]

    def test_sync_ui_preview_frame(self) -> None:
        test_bytes = b"\xff\xd8\xff\xe0test_preview_data"
        self.orch._sync_ui_preview_frame(test_bytes)
        preview_file = AGENT_ROOT / "ui" / "latest_frame.jpg"
        self.assertTrue(preview_file.is_file())
        self.assertEqual(preview_file.read_bytes(), test_bytes)

    def test_rtsp_grab_routing(self) -> None:
        with patch.object(self.orch, "_grab_rtsp_frame", return_value=True) as mock_rtsp:
            test_path = AGENT_ROOT / "run" / "test_frame.jpg"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_bytes(b"dummy")

            ok = self.orch._grab_camera_frame(
                "rtsp://10.0.0.120:554/live",
                test_path,
                timeout=1.5,
                max_cache_age_sec=0.0,
            )
            self.assertTrue(ok)
            mock_rtsp.assert_called_once()
            self.assertIn("rtsp://10.0.0.120:554/live", mock_rtsp.call_args[0])

    async def test_ws_set_camera_url(self) -> None:
        msg = json.dumps({
            "type": "set_camera_url",
            "url": "rtsp://192.168.1.200:554/h264",
            "transport": "udp",
        })
        with patch.object(self.orch, "_grab_camera_frame", return_value=True):
            await self.orch._handle_ws_message(msg)
            # Allow background test task to finish
            await asyncio.sleep(0.05)

        self.assertEqual(self.orch.camera_url, "rtsp://192.168.1.200:554/h264")
        self.assertEqual(self.orch.camera_rtsp_transport, "udp")
        status_events = [e for e in self.events if e.get("type") == "camera_status"]
        self.assertTrue(len(status_events) > 0)
        self.assertTrue(status_events[0]["connected"])

    async def test_ws_get_status(self) -> None:
        msg = json.dumps({"type": "get_status"})
        await self.orch._handle_ws_message(msg)

        status_events = [e for e in self.events if e.get("type") == "status_response"]
        self.assertEqual(len(status_events), 1)
        resp = status_events[0]
        self.assertEqual(resp["state"], "IDLE")
        self.assertEqual(resp["camera_url"], self.orch.camera_url)
        self.assertIn("caption", resp["scene_memory"])

    async def test_ws_chat_dispatches_llm(self) -> None:
        msg = json.dumps({"type": "chat", "text": "桌面上有什么？"})
        with patch.object(self.orch, "_run_llm", return_value=None) as mock_llm:
            await self.orch._handle_ws_message(msg)
            await asyncio.sleep(0.05)

            mock_llm.assert_called_once()
            self.assertIn("桌面上有什么", mock_llm.call_args[0][0])
            asr_events = [e for e in self.events if e.get("type") == "asr_final"]
            self.assertEqual(len(asr_events), 1)
            self.assertEqual(asr_events[0]["source"], "web")

    async def test_ws_stop_aborts_tts(self) -> None:
        msg = json.dumps({"type": "stop"})
        await self.orch._handle_ws_message(msg)
        self.assertTrue(self.orch._tts_abort)
        self.orch.tts_queue.abort.assert_called_once()
        self.assertEqual(self.orch.state, AgentState.LISTEN)


if __name__ == "__main__":
    unittest.main()
