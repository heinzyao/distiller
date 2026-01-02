"""
改進的數據處理工具
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
import logging
from pathlib import Path


class FlavorDataProcessor:
    """風味數據處理器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化數據處理器

        Args:
            config: 配置字典
        """
        self.config = config
        self.flavor_labels = config.get('flavor_labels', [])
        self.categories = config.get('categories', {})
        self.scale_factor = config.get('flavor_encoding', {}).get('scale_factor', 20)
        self.max_level = config.get('flavor_encoding', {}).get('max_level', 5)

        self.logger = logging.getLogger(__name__)

    def discretize_flavor_value(self, value: int) -> int:
        """
        將 0-100 的風味值離散化為 0-5 的等級

        Args:
            value: 原始風味值 (0-100)

        Returns:
            離散化後的等級 (0-5)
        """
        if value == 0:
            return 0
        return min(int(np.ceil(value / self.scale_factor)), self.max_level)

    def map_type_to_category(self, spirit_type: str) -> str:
        """
        將細分類型映射到主要類別

        Args:
            spirit_type: 酒類細分類型

        Returns:
            主要類別名稱
        """
        for category, types in self.categories.items():
            if spirit_type in types:
                return category
        return 'Other'

    def encode_flavor_profile(self, flavor_dict: Dict[str, int]) -> Dict[str, int]:
        """
        編碼風味檔案為離散等級

        Args:
            flavor_dict: 原始風味字典 {flavor: value}

        Returns:
            編碼後的風味字典 {flavor: level}
        """
        encoded = {}
        for label in self.flavor_labels:
            # 處理可能帶引號的鍵
            raw_value = flavor_dict.get(label, flavor_dict.get(f"'{label}'", 0))

            # 確保是整數
            try:
                raw_value = int(raw_value) if raw_value else 0
            except (ValueError, TypeError):
                raw_value = 0

            encoded[label] = self.discretize_flavor_value(raw_value)

        return encoded

    def multi_hot_encode(self, flavor_levels: Dict[str, int], num_levels: int = 6) -> np.ndarray:
        """
        Multi-Hot 編碼風味等級

        Args:
            flavor_levels: 風味等級字典 {flavor: level}
            num_levels: 等級數量 (默認 6 個等級: 0-5)

        Returns:
            Multi-Hot 編碼向量
        """
        encoded = []
        for label in self.flavor_labels:
            level = flavor_levels.get(label, 0)
            # One-Hot 編碼當前風味的等級
            one_hot = [1 if i == level else 0 for i in range(num_levels)]
            encoded.extend(one_hot)

        return np.array(encoded, dtype=np.uint8)

    def process_training_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        處理訓練數據

        Args:
            df: 原始數據 DataFrame

        Returns:
            處理後的 DataFrame
        """
        self.logger.info(f"開始處理訓練數據，原始樣本數: {len(df)}")

        # 1. 數據驗證
        self._validate_dataframe(df)

        # 2. 篩選有效數據
        df_filtered = df[
            (df['tasting_notes'].notna()) &
            (df['flavor_profile'].notna())
        ].copy()

        self.logger.info(f"篩選後樣本數: {len(df_filtered)}")

        # 3. 類別映射
        df_filtered['category'] = df_filtered['type'].apply(self.map_type_to_category)

        # 4. 風味編碼
        df_filtered['flavor_encoded'] = df_filtered['flavor_profile'].apply(
            self.encode_flavor_profile
        )

        # 5. Multi-Hot 編碼
        multi_hot_labels = np.vstack(
            df_filtered['flavor_encoded'].apply(self.multi_hot_encode).values
        )

        # 6. 創建標籤列名
        label_columns = self._generate_label_columns()

        # 7. 創建最終 DataFrame
        labels_df = pd.DataFrame(multi_hot_labels, columns=label_columns, dtype=np.uint8)

        result_df = pd.concat([
            df_filtered[['id', 'tasting_notes']].reset_index(drop=True),
            labels_df
        ], axis=1)

        self.logger.info(f"處理完成，最終形狀: {result_df.shape}")

        return result_df

    def _generate_label_columns(self, num_levels: int = 6) -> List[str]:
        """生成標籤列名"""
        columns = []
        for flavor in self.flavor_labels:
            for level in range(num_levels):
                columns.append(f"{flavor}_{level}")
        return columns

    def _validate_dataframe(self, df: pd.DataFrame):
        """驗證 DataFrame"""
        required_columns = ['tasting_notes', 'flavor_profile']
        missing = [col for col in required_columns if col not in df.columns]

        if missing:
            raise ValueError(f"缺少必要的列: {missing}")

        if len(df) == 0:
            raise ValueError("DataFrame 為空")

        self.logger.info("數據驗證通過")


# 使用示例
if __name__ == '__main__':
    import yaml
    from pathlib import Path

    # 加載配置
    config_path = Path('configs/data_config.yaml')
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # 創建處理器
    processor = FlavorDataProcessor(config)

    # 測試風味值離散化
    print("風味值離散化測試:")
    test_values = [0, 10, 25, 50, 75, 100]
    for val in test_values:
        print(f"  {val} -> {processor.discretize_flavor_value(val)}")

    # 測試類型映射
    print("\n類型映射測試:")
    test_types = ['Bourbon', 'Cognac', 'London Dry Gin', 'Unknown Type']
    for t in test_types:
        print(f"  {t} -> {processor.map_type_to_category(t)}")

    # 測試風味編碼
    print("\n風味編碼測試:")
    test_flavor = {'fruity': 75, 'smoky': 20, 'sweet': 90}
    encoded = processor.encode_flavor_profile(test_flavor)
    print(f"  原始: {test_flavor}")
    print(f"  編碼: {encoded}")

    # 測試 Multi-Hot 編碼
    print("\nMulti-Hot 編碼測試:")
    multi_hot = processor.multi_hot_encode(encoded)
    print(f"  向量長度: {len(multi_hot)}")
    print(f"  向量形狀: {multi_hot.shape}")
