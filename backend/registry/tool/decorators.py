from __future__ import annotations
from typing import Type, List, Dict, Any
from backend.registry.tool.tool import Tool, ToolMetadata

# List to hold pending tool blueprints
_pending_tools: List[tuple[ToolMetadata, Type[Any]]] = []

def tool(
    id: str,
    capability_id: str,
    name: str,
    description: str,
    parameter_schema: Dict[str, Any] = None,
    aliases: List[str] = None,
    tags: List[str] = None,
    permissions: List[str] = None
):
    """Decorator to mark an executable class as a Tool."""
    def decorator(cls: Type[Any]) -> Type[Any]:
        metadata = ToolMetadata(
            id=id,
            capability_id=capability_id,
            name=name,
            description=description,
            parameter_schema=parameter_schema or {},
            aliases=aliases or [],
            tags=tags or [],
            permissions=permissions or []
        )
        _pending_tools.append((metadata, cls))
        return cls
    return decorator

def register_pending_tools(registry: Any, container: Any = None) -> None:
    """Flushes all pending tool blueprints into the injected registry."""
    for metadata, cls in _pending_tools:
        if registry.exists(metadata.id):
            continue
        try:
            instance = None
            # Check custom dependency requirements
            if cls.__name__ == "AppLauncherTool" and container is not None:
                instance = cls(application_registry=getattr(container, "application_registry", None))
            elif cls.__name__ == "ClipboardTool" and container is not None:
                # Retrieve from container or instantiate
                instance = cls()
            else:
                instance = cls()
            
            registry.register(Tool(metadata, executable=instance))
        except Exception as exc:
            import logging
            logger = logging.getLogger("eggman")
            logger.error("Failed to instantiate auto-registered tool cls=%s: %s", cls.__name__, exc)
