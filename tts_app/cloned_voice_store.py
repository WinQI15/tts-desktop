"""
克隆音色持久化存储

已克隆的音色保存在 models/cloned_voices.json 中，
每个引擎的 get_available_voices() 会自动附加该引擎的克隆音色。
"""
import json
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = Path(__file__).parent.parent / "models" / "cloned_voices.json"


class ClonedVoiceStore:
    """克隆音色管理器

    数据格式 (cloned_voices.json):
    {
      "voices": [
        {
          "id": "voice_uuid",
          "name": "用户命名",
          "engine_key": "fish_s2_pro",
          "reference_audio": "path/to/ref.wav",
          "created_at": "2026-05-23T08:00:00",
          "extra": {}
        }
      ]
    }
    """

    def __init__(self, store_path: Optional[str] = None):
        self._path = Path(store_path) if store_path else DEFAULT_STORE_PATH
        self._data: dict = {"voices": []}
        self._load()

    @property
    def path(self) -> str:
        return str(self._path)

    def _load(self):
        """从文件加载"""
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
                if "voices" not in self._data:
                    self._data["voices"] = []
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"加载克隆音色数据失败: {e}")
                self._data = {"voices": []}

    def _save(self):
        """保存到文件"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_voice(
        self,
        voice_id: str,
        name: str,
        engine_key: str,
        reference_audio: str = "",
        extra: Optional[dict] = None,
    ) -> dict:
        """添加克隆音色

        Returns:
            新音色条目
        """
        entry = {
            "id": voice_id,
            "name": name,
            "engine_key": engine_key,
            "reference_audio": reference_audio,
            "created_at": datetime.now().isoformat(),
            "extra": extra or {},
        }
        self._data["voices"].append(entry)
        self._save()
        logger.info(f"克隆音色已保存: {name} ({engine_key})")
        return entry

    def remove_voice(self, voice_id: str) -> bool:
        """删除音色"""
        before = len(self._data["voices"])
        self._data["voices"] = [
            v for v in self._data["voices"] if v["id"] != voice_id
        ]
        if len(self._data["voices"]) < before:
            self._save()
            return True
        return False

    def rename_voice(self, voice_id: str, new_name: str) -> bool:
        """重命名音色"""
        for v in self._data["voices"]:
            if v["id"] == voice_id:
                v["name"] = new_name
                self._save()
                return True
        return False

    def get_voices_for_engine(self, engine_key: str) -> list[dict]:
        """获取指定引擎的所有克隆音色"""
        return [
            v for v in self._data["voices"]
            if v["engine_key"] == engine_key
        ]

    def get_all_voices(self) -> list[dict]:
        """获取所有克隆音色"""
        return list(self._data["voices"])

    def get_voice(self, voice_id: str) -> Optional[dict]:
        """获取音色详情"""
        for v in self._data["voices"]:
            if v["id"] == voice_id:
                return v
        return None

    def list_voice_ids_for_engine(self, engine_key: str) -> list[str]:
        """获取指定引擎的克隆音色 ID 列表"""
        return [v["id"] for v in self.get_voices_for_engine(engine_key)]

    @staticmethod
    def generate_id(engine_key: str, ref_audio_hash: int) -> str:
        """生成音色 ID"""
        return f"{engine_key}_cloned_{ref_audio_hash & 0xFFFF:04x}"


# 全局单例
_cloned_voice_store: Optional[ClonedVoiceStore] = None


def get_cloned_voice_store(store_path: Optional[str] = None) -> ClonedVoiceStore:
    """获取全局克隆音色管理器"""
    global _cloned_voice_store
    if _cloned_voice_store is None:
        _cloned_voice_store = ClonedVoiceStore(store_path)
    return _cloned_voice_store
