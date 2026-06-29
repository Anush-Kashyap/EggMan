from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_vision_pending_attachment_flow():
    from backend.vision.vision_manager import VisionManager
    mgr = VisionManager()

    # Initially empty
    assert not mgr.has_pending_attachment()
    assert mgr.pop_pending_attachment() is None

    # Set dummy base64 attachment
    mgr._pending_attachment = type('Attachment', (), {'source_type': 'screenshot', 'image_base64': 'dGVzdA=='})()
    assert mgr.has_pending_attachment()

    # Pop and ensure cleared
    img = mgr.pop_pending_attachment()
    assert img == 'dGVzdA=='
    assert not mgr.has_pending_attachment()

    # Test clear_pending_attachment
    mgr._pending_attachment = type('Attachment', (), {'source_type': 'screenshot', 'image_base64': 'dGVzdA=='})()
    assert mgr.has_pending_attachment()
    mgr.clear_pending_attachment()
    assert not mgr.has_pending_attachment()


def test_vision_manager_sources_architecture():
    from backend.vision.vision_manager import VisionManager
    mgr = VisionManager()

    # Screenshot source should be registered
    assert "screenshot" in mgr._sources
    assert mgr._sources["screenshot"] is not None

    # Future-ready sources placeholders should exist
    assert "clipboard" in mgr._sources
    assert "file" in mgr._sources
    assert "camera" in mgr._sources
    assert "region" in mgr._sources
