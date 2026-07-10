from __future__ import annotations
import pytest
from backend.event_bus.event_bus import EventBus
from backend.registry.common.exceptions import DuplicateRegistrationError, ItemNotFoundError, ValidationError
from backend.registry.common.base_registry import BaseRegistry
from backend.registry.capability.capability import Capability, CapabilityMetadata
from backend.registry.capability.capability_registry import (
    CapabilityRegistry,
    CapabilityRegisteredEvent,
    CapabilityEnabledEvent,
    CapabilityDisabledEvent
)
from backend.registry.capability.decorators import capability, register_pending_capabilities
from backend.registry.tool.tool import Tool, ToolMetadata
from backend.registry.tool.tool_registry import ToolRegistry, ToolRegisteredEvent
from backend.registry.tool.decorators import tool, register_pending_tools
from backend.registry.tool.executor import ToolExecutor


# 1. BaseRegistry tests
class DummyItem:
    def __init__(self, id: str, name: str) -> None:
        self.id = id
        self.name = name


def test_base_registry_operations():
    registry = BaseRegistry[DummyItem]()
    
    # Empty registry checks
    assert len(registry) == 0
    assert not registry.exists("dummy_1")
    with pytest.raises(ItemNotFoundError):
        registry.get("dummy_1")
        
    # Register items
    item_1 = DummyItem("dummy_1", "First Item")
    item_2 = DummyItem("dummy_2", "Second Item")
    
    registry.register(item_1)
    assert len(registry) == 1
    assert registry.exists("dummy_1")
    assert registry.get("dummy_1") == item_1
    
    # Duplicate registration check
    with pytest.raises(DuplicateRegistrationError):
        registry.register(item_1)
        
    registry.register(item_2)
    assert len(registry) == 2
    
    # Get all items
    items = registry.get_all()
    assert item_1 in items
    assert item_2 in items
    
    # Iteration check
    iterated = list(registry)
    assert len(iterated) == 2
    assert iterated[0] in [item_1, item_2]
    
    # Unregister check
    registry.unregister("dummy_1")
    assert len(registry) == 1
    assert not registry.exists("dummy_1")
    with pytest.raises(ItemNotFoundError):
        registry.unregister("dummy_1")
        
    # Clear check
    registry.clear()
    assert len(registry) == 0


# 2. CapabilityRegistry & EventBus Integration tests
def test_capability_registry_event_bus():
    event_bus = EventBus()
    registry = CapabilityRegistry(event_bus=event_bus)
    
    received_events = []
    
    def log_event(event):
        received_events.append(event)
        
    event_bus.subscribe(CapabilityRegisteredEvent, log_event)
    event_bus.subscribe(CapabilityEnabledEvent, log_event)
    event_bus.subscribe(CapabilityDisabledEvent, log_event)
    
    # Create metadata and register
    metadata = CapabilityMetadata(
        id="voice_test",
        name="Voice Test",
        description="Testing voice capability desc"
    )
    cap = Capability(metadata)
    
    # Test registration and check event publication
    registry.register(cap)
    assert len(received_events) == 1
    assert isinstance(received_events[0], CapabilityRegisteredEvent)
    assert received_events[0].capability_id == "voice_test"
    
    # Test disablement event publication
    registry.set_enabled("voice_test", False)
    assert len(received_events) == 2
    assert isinstance(received_events[1], CapabilityDisabledEvent)
    assert received_events[1].capability_id == "voice_test"
    
    # Test enablement event publication
    registry.set_enabled("voice_test", True)
    assert len(received_events) == 3
    assert isinstance(received_events[2], CapabilityEnabledEvent)
    assert received_events[2].capability_id == "voice_test"


# 3. ToolRegistry & EventBus Integration tests
def test_tool_registry_event_bus():
    event_bus = EventBus()
    registry = ToolRegistry(event_bus=event_bus)
    
    received_events = []
    event_bus.subscribe(ToolRegisteredEvent, lambda ev: received_events.append(ev))
    
    # Create metadata and register
    metadata = ToolMetadata(
        id="calc_test",
        capability_id="automation_test",
        name="Calculator Test",
        description="Testing calculator tool desc"
    )
    
    class TestExecutable:
        def execute(self, a, b):
            return a + b
            
    tool_item = Tool(metadata, executable=TestExecutable())
    
    registry.register(tool_item)
    assert len(received_events) == 1
    assert isinstance(received_events[0], ToolRegisteredEvent)
    assert received_events[0].tool_id == "calc_test"
    assert received_events[0].capability_id == "automation_test"


# 4. ToolExecutor test
def test_tool_executor():
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    
    metadata = ToolMetadata(
        id="math_add",
        capability_id="automation_test",
        name="Math Add",
        description="Testing addition"
    )
    
    # Test callable tool
    tool_callable = Tool(metadata, executable=lambda x, y: x + y)
    registry.register(tool_callable)
    assert executor.execute("math_add", 5, 10) == 15
    
    # Test class with execute method
    class MultiplyTool:
        def execute(self, x, y):
            return x * y
            
    metadata_mult = ToolMetadata(
        id="math_mult",
        capability_id="automation_test",
        name="Math Mult",
        description="Testing multiplication"
    )
    tool_mult = Tool(metadata_mult, executable=MultiplyTool())
    registry.register(tool_mult)
    assert executor.execute("math_mult", 3, 4) == 12
    
    # Test disabled tool execution failure
    registry.set_enabled("math_add", False)
    with pytest.raises(ValueError):
        executor.execute("math_add", 1, 2)


# 5. Decorators test
def test_auto_decorators_registration():
    # Define capabilities using decorator
    @capability(
        id="dec_cap",
        name="Decorator Capability",
        description="Testing decorator description"
    )
    class DummyCapClass:
        pass
        
    # Define tools using decorator
    @tool(
        id="dec_tool",
        capability_id="dec_cap",
        name="Decorator Tool",
        description="Testing decorator tool description"
    )
    class DummyToolClass:
        def execute(self):
            return "decorator_success"
            
    cap_registry = CapabilityRegistry()
    tool_registry = ToolRegistry()
    
    # Flush pending decorators
    register_pending_capabilities(cap_registry)
    register_pending_tools(tool_registry)
    
    assert cap_registry.exists("dec_cap")
    assert cap_registry.get("dec_cap").name == "Decorator Capability"
    
    assert tool_registry.exists("dec_tool")
    assert tool_registry.get("dec_tool").name == "Decorator Tool"
    
    # Verify tool execution
    executor = ToolExecutor(tool_registry)
    assert executor.execute("dec_tool") == "decorator_success"
