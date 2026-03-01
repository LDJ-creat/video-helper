
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv

# Load env before importing app to ensure settings are picked up
load_dotenv(".env")


# These tests exercise real LLM-backed endpoints. Skip when not configured.
if not (os.environ.get("LLM_API_BASE") and os.environ.get("LLM_API_KEY")):
    pytest.skip("LLM not configured (set LLM_API_BASE and LLM_API_KEY)", allow_module_level=True)

from core.main import app
from core.db.base import Base
from core.db.session import get_db_session
from core.db.models.project import Project
from core.db.models.conversation import ChatSession, ChatMessage
from core.db.models.quiz import QuizSession, QuizItem

# Setup Test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db_session():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db_session] = override_get_db_session

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="module")
def setup_project(db_session):
    project = Project(
        project_id="test-project-1",
        title="Test Video Project",
        source_type="youtube",
        source_url="https://www.youtube.com/watch?v=ScMzIvxBSi4", # Dummy
        created_at_ms=1000,
        updated_at_ms=1000
    )
    db_session.add(project)
    db_session.commit()
    return project

def test_chat_completions_streaming(setup_project, db_session):
    # System Prompt for Chat requires some context. 
    # In real app, context comes from analysis. 
    # Here we just want to verify connectivity and streaming.
    
    session_id: str | None = None
    saw_done = False

    with client.stream(
        "POST",
        "/api/v1/chat/completions",
        json={
            "project_id": "test-project-1",
            "message": "Hello, what is this video about?",
            # "session_id": "optional-new-session" 
        }
    ) as response:
    
        assert response.status_code == 200
        
        # Consuming the stream
        content = ""
        for line in response.iter_lines():
            if not line:
                continue

            decoded_line = line
            assert decoded_line.startswith("data: ")
            data_str = decoded_line.replace("data: ", "", 1).strip()
            content += decoded_line

            if data_str == "[DONE]":
                saw_done = True
                continue

            import json
            try:
                payload = json.loads(data_str)
            except Exception:
                continue

            if payload.get("start_session_id"):
                session_id = payload["start_session_id"]

        print(f"\n[Chat Response Content]: {content[:200]}...")
        assert "data: " in content
        assert saw_done is True
        assert session_id is not None

    # Verify DB persistence: both user and assistant messages exist
    msgs = db_session.query(ChatMessage).filter(ChatMessage.session_id == session_id).all()
    roles = [m.role for m in msgs]
    assert "user" in roles
    assert "assistant" in roles

def test_quiz_generation(setup_project):
    # Real LLM call to generate quiz
    response = client.post(
        "/api/v1/quiz/generate",
        json={
            "project_id": "test-project-1",
            "topic_focus": "General" 
        }
    )
    
    if response.status_code != 200:
        print(f"Quiz Error: {response.text}")
        
    assert response.status_code == 200
    data = response.json()
    
    assert "sessionId" in data
    assert "items" in data
    assert len(data["items"]) > 0
    
    first_item = data["items"][0]
    assert "question" in first_item
    assert "options" in first_item
    assert "correctAnswer" in first_item
    
    # Keep session_id for next test?
    pytest.quiz_session_id = data["sessionId"]
    pytest.quiz_items = data["items"]

def test_quiz_save(setup_project):
    # Requires session_id from generation or new one
    # If previous test failed, skipping this or using dummy
    if not hasattr(pytest, 'quiz_session_id'):
        pytest.skip("Skipping save test because generation failed")
        
    session_id = pytest.quiz_session_id
    items = pytest.quiz_items
    
    # Simulate answering
    answers = []
    correct_count = 0
    for item in items:
        # Just pick the first option as answer
        user_ans = item["options"][0]
        is_correct = (user_ans == item["correctAnswer"])
        if is_correct: correct_count += 1
        
        answers.append({
            "question_hash": item["questionHash"],
            "user_answer": user_ans,
            "is_correct": is_correct
        })
        
    score = int((correct_count / len(items)) * 100)
    
    response = client.post(
        "/api/v1/quiz/save",
        json={
            "project_id": "test-project-1",
            "session_id": session_id,
            "score": score,
            "items": answers
        }
    )
    
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_fetch_chat_history(setup_project, db_session):
    # Insert a dummy session and message
    session = ChatSession(
        id="test-session-1",
        project_id="test-project-1",
        title="Test Session",
        created_at_ms=1000,
        updated_at_ms=1000
    )
    db_session.add(session)
    
    msg = ChatMessage(
        id="msg-1",
        session_id="test-session-1",
        role="user",
        content="Hello history",
        created_at_ms=1001
    )
    db_session.add(msg)
    db_session.commit()
    
    # Test List Sessions
    resp = client.get("/api/v1/chat/sessions?projectId=test-project-1")
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) >= 1
    session_ids = [s["id"] for s in sessions]
    assert "test-session-1" in session_ids
    
    # Test List Messages
    resp = client.get("/api/v1/chat/sessions/test-session-1/messages")
    assert resp.status_code == 200
    msgs = resp.json()
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Hello history"
