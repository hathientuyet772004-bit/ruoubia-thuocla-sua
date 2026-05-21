"""
Interface chuẩn cho các chiến lược thu thập dữ liệu.
Mọi strategy cần kế thừa từ BaseCollector.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseCollector(ABC):
    @abstractmethod
    def collect(self, url: str) -> List[Dict[str, Any]]:
        """Phương thức thu thập chính."""
        pass
