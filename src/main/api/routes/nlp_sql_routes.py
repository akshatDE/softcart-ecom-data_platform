"""REST endpoint for natural-language analytics questions."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.main.services.nlp_sql_service import NLPSQLService
from src.main.utility.exceptions import NLPServiceError, SQLValidationError
from src.main.utility.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/nlp", tags=["nlp-to-sql"])


class QuestionRequest(BaseModel):
    """A natural-language analytics question."""

    question: str = Field(..., min_length=3, max_length=1000,
                          examples=["What were the top 10 products by revenue last month?"])


class QuestionResponse(BaseModel):
    """Generated SQL plus the query result."""

    question: str
    sql: str
    row_count: int
    rows: list[dict[str, Any]]


@router.post("/query", response_model=QuestionResponse)
def nlp_query(request: QuestionRequest) -> QuestionResponse:
    """Translate a question to safe SQL, execute it read-only, return rows.

    The generated SQL is validated (SELECT-only, approved tables, enforced
    LIMIT) and executed on a read-only connection with a timeout, so this
    endpoint can never modify the warehouse.
    """
    service = NLPSQLService()
    try:
        result = service.answer(request.question)
    except SQLValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Unsafe SQL rejected: {exc}") from exc
    except NLPServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return QuestionResponse(
        question=result["question"],
        sql=result["sql"],
        row_count=result["row_count"],
        rows=result["rows"],
    )
