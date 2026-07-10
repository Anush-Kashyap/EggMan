from __future__ import annotations
from typing import Type, List, Dict, Any
from backend.registry.capability.capability import Capability, CapabilityMetadata

# List to hold pending capability blueprints
_pending_capabilities: List[CapabilityMetadata] = []

def capability(
    id: str,
    name: str,
    description: str,
    category: str = "general",
    version: str = "1.0.0",
    experimental: bool = False,
    dependencies: List[str] = None,
    health_status: str = "Healthy"
):
    """Decorator to mark a class as a capability configuration."""
    def decorator(cls: Type[Any]) -> Type[Any]:
        metadata = CapabilityMetadata(
            id=id,
            name=name,
            description=description,
            category=category,
            version=version,
            experimental=experimental,
            dependencies=dependencies or [],
            health_status=health_status
        )
        _pending_capabilities.append(metadata)
        return cls
    return decorator

def register_pending_capabilities(registry: Any) -> None:
    """Flushes all pending capability blueprints into the injected registry."""
    for metadata in _pending_capabilities:
        if not registry.exists(metadata.id):
            registry.register(Capability(metadata))
