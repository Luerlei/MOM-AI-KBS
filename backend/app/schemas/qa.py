"""问答 Pydantic模型"""
from typing import Optional, List
from pydantic import BaseModel


class QAHistoryItem(BaseModel):
    role: str  # "user" / "assistant"
    content: str


class QARequest(BaseModel):
    question: str
    use_cache: bool = True
    history: List[QAHistoryItem] = []  # 多轮对话历史


class QASource(BaseModel):
    knowledge_id: int
    title: str
    snippet: str = ""
    score: float = 0.0


class QAResponse(BaseModel):
    answer: str
    sources: List[QASource] = []
    skill_id: Optional[int] = None
    skill_name: str = ""
    token_input: int = 0
    token_output: int = 0
    duration_ms: int = 0
    cached: bool = False
    history_id: Optional[int] = None


class QAFeedback(BaseModel):
    history_id: int
    feedback: str  # "useful" / "useless"，内部转为 1 / -1


class QAHistoryOut(BaseModel):
    id: int
    question: str
    answer: str
    sources: List[dict] = []
    skill_id: Optional[int] = None
    skill_name: Optional[str] = None
    feedback: Optional[int] = None
    token_input: int = 0
    token_output: int = 0
    duration_ms: int = 0
    created_at: str

    class Config:
        from_attributes = True


class QAHistoryListOut(BaseModel):
    id: int
    question: str
    answer_summary: str = ""
    skill_name: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str
    search_type: str = "semantic"  # semantic / keyword
    category_id: Optional[int] = None
    tag_ids: List[int] = []
    page: int = 1
    page_size: int = 10


class SearchResult(BaseModel):
    id: Optional[int] = None
    knowledge_id: int
    title: str
    snippet: str = ""
    score: float = 0.0
    content_type: str = ""
    category_name: Optional[str] = None
    tag_names: List[str] = []
    tags: List[dict] = []
