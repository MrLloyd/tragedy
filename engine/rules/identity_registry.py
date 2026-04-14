"""惨剧轮回 — 身份注册表

纯数据层，只读查询接口。
从一个或多个 LoadedModule 注册身份定义，按 identity_id 查询。
"""

from __future__ import annotations

from typing import Optional

from engine.models.identity import IdentityDef


class IdentityRegistry:
    def __init__(self) -> None:
        self._defs: dict[str, IdentityDef] = {}

    def register(self, defs: dict[str, IdentityDef]) -> None:
        """批量注册身份定义（后注册的同 id 会覆盖先注册的）"""
        self._defs.update(defs)

    def get(self, identity_id: str) -> Optional[IdentityDef]:
        return self._defs.get(identity_id)

    def all(self) -> dict[str, IdentityDef]:
        return dict(self._defs)

    def __len__(self) -> int:
        return len(self._defs)
