"""数据源适配器接口（预留，MVP不实现具体适配器）"""
from abc import ABC, abstractmethod
from typing import List


class DataAdapter(ABC):
    """数据源适配器接口（预留，MVP不实现具体适配器）"""

    @abstractmethod
    def fetch(self) -> List[dict]:
        """从数据源获取数据并转为标准格式"""
        pass


# 预留的适配器类型：
# - DBAdapter: 从数据库获取数据
# - APIAdapter: 从API获取数据
# MVP仅定义接口，具体实现后续扩展
