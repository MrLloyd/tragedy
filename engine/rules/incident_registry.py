"""惨剧轮回 — 事件注册表

纯数据层，只读查询接口。
从一个或多个 LoadedModule 注册事件定义，按 incident_id 查询。
"""

from __future__ import annotations

from typing import Optional

from engine.models.incident import IncidentDef


class IncidentRegistry:
    def __init__(self) -> None:
        self._defs: dict[str, IncidentDef] = {}

    def register(self, defs: dict[str, IncidentDef]) -> None:
        """批量注册事件定义（后注册的同 id 会覆盖先注册的）"""
        self._defs.update(defs)

    def get(self, incident_id: str) -> Optional[IncidentDef]:
        return self._defs.get(incident_id)

    def all(self) -> dict[str, IncidentDef]:
        return dict(self._defs)

    def __len__(self) -> int:
        return len(self._defs)
