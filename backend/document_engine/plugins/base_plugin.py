from abc import ABC, abstractmethod

class BasePlugin(ABC):
    """
    Abstract Base Class for Document Engine rendering plugins.
    """
    
    @abstractmethod
    def initialize(self):
        """
        Initializes plugin configuration or registers assets.
        """
        pass
        
    @abstractmethod
    def validate(self, config_data):
        """
        Validates the block configuration options.
        Returns (bool, list_of_errors)
        """
        pass
        
    @abstractmethod
    def render(self, config_data, context):
        """
        Renders the element to printable HTML.
        """
        pass
        
    @abstractmethod
    def serialize(self):
        """
        Serializes plugin schema metadata.
        """
        pass
