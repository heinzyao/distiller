"""
配置管理工具
"""

import yaml
from pathlib import Path
from typing import Dict, Any


class Config:
    """配置管理類"""

    def __init__(self, config_path: str):
        """
        初始化配置

        Args:
            config_path: 配置文件路徑
        """
        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加載配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def get(self, key: str, default=None):
        """
        獲取配置值

        Args:
            key: 配置鍵，支持點號分隔的嵌套鍵（如 'training.batch_size'）
            default: 默認值

        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def __getitem__(self, key: str):
        """支持字典式訪問"""
        return self.get(key)

    def __repr__(self):
        return f"Config(path='{self.config_path}')"


def load_config(config_name: str, config_dir: str = 'configs') -> Config:
    """
    加載指定的配置文件

    Args:
        config_name: 配置文件名（不含 .yaml 後綴）
        config_dir: 配置文件目錄

    Returns:
        Config 對象
    """
    config_path = Path(config_dir) / f"{config_name}.yaml"
    return Config(config_path)


# 使用示例
if __name__ == '__main__':
    # 加載爬蟲配置
    crawler_config = load_config('crawler_config')
    print(f"請求延遲: {crawler_config.get('request.delay')} 秒")
    print(f"線程數: {crawler_config.get('threading.num_threads')}")

    # 加載數據配置
    data_config = load_config('data_config')
    print(f"風味標籤數量: {len(data_config.get('flavor_labels', []))}")

    # 加載模型配置
    model_config = load_config('model_config')
    print(f"模型類型: {model_config.get('model.type')}")
    print(f"訓練輪數: {model_config.get('training.num_train_epochs')}")
