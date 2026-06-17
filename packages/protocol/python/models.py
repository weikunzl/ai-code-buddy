from typing import Any, Literal, TypedDict


class PendingOption(TypedDict, total=False):
    id: str
    label: str
    desc: str


class PendingItem(TypedDict, total=False):
    id: str
    sid: str
    kind: str
    title: str
    body: str
    options: list[PendingOption]


class BuddySnapshot(TypedDict, total=False):
    type: Literal["snapshot"]
    total: int
    running: int
    waiting: int
    msg: str
    entries: list[str]
    tokens: int
    tokens_today: int
    focused: str
    project: str
    branch: str
    dirty: int
    model: str
    assistant_msg: str
    sessions: list[dict[str, Any]]
    pending: list[PendingItem]
    prompt: dict[str, Any]
    event: dict[str, Any]


class PermissionIntent(TypedDict):
    cmd: Literal["permission"]
    id: str
    decision: Literal["once", "deny"]


class AnswerIntent(TypedDict, total=False):
    cmd: Literal["answer"]
    id: str
    choice: str
    choices: list[str]


DeviceIntent = PermissionIntent | AnswerIntent | dict[str, Any]
