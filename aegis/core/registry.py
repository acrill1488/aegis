class ServiceRegistry:
    def __init__(self):
        self._services = {}
    
    def register(self, name: str, service: object) -> None:
        """Register a service with the given name."""
        self._services[name] = service
    
    def get(self, name: str) -> object:
        """Get a service by name."""
        return self._services.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a service is registered."""
        return name in self._services
    
    def list_services(self) -> list[str]:
        """List all registered service names."""
        return list(self._services.keys())