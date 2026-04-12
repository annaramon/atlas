from fastapi import APIRouter
from pydantic import BaseModel

from app.agent import agent

router = APIRouter()


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    answer = agent.ask(request.question)
    return AskResponse(answer=answer)
