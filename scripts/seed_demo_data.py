from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.config.settings import Settings
from app.db.models import PlanSnapshot, SessionState, Task, User
from app.db.repository import TaskRepository
from app.services.security import hash_password


DEMO_USER_ID = "u-demo-seed"
DEMO_USERNAME = "demo"
DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo12345"


PLANS = [
    {
        "session_id": "s-demo-hangzhou",
        "task_id": "t-demo-01",
        "plan_id": "ps-demo-01",
        "title": "杭州西湖两日游",
        "message": "帮我规划杭州两日游，预算 2000 元，想住西湖附近。",
        "plan": {
            "overview": "杭州西湖两日轻松游，重点覆盖西湖、灵隐寺、河坊街与湖滨夜景。",
            "transport": [
                {"name": "高铁到杭州东站", "price": 180, "description": "到站后乘地铁前往湖滨商圈。"},
                {"name": "市内地铁+打车", "price": 120, "description": "西湖周边步行与短途打车结合。"},
            ],
            "hotels": [
                {"name": "西湖湖滨舒适酒店", "price": 520, "description": "靠近湖滨银泰，夜游和餐饮方便。"}
            ],
            "itinerary": [
                {"day": 1, "title": "西湖经典线", "description": "断桥、白堤、苏堤、雷峰塔，晚上湖滨步行街。"},
                {"day": 2, "title": "灵隐寺与河坊街", "description": "上午灵隐寺，下午河坊街和南宋御街。"},
            ],
            "budget": {"total": 1880, "transport": 300, "hotel": 1040, "food": 360, "tickets": 180},
            "notes": ["周末西湖人流较多，建议早出发。", "灵隐寺门票和飞来峰景区票分开购买。"],
        },
        "trip": {"destination": "杭州", "duration_days": 2, "budget": {"max": 2000}},
    },
    {
        "session_id": "s-demo-chengdu",
        "task_id": "t-demo-02",
        "plan_id": "ps-demo-02",
        "title": "成都美食四日游",
        "message": "成都四天美食游，想吃火锅、串串和小吃。",
        "plan": {
            "overview": "成都四日美食探索，兼顾宽窄巷子、锦里、熊猫基地和夜间火锅体验。",
            "transport": [{"name": "市区地铁为主", "price": 90, "description": "景点间优先地铁，夜间返程可打车。"}],
            "hotels": [{"name": "春熙路附近酒店", "price": 430, "description": "方便去太古里、IFS 和夜宵街。"}],
            "itinerary": [
                {"day": 1, "title": "春熙路与火锅", "description": "抵达后逛太古里，晚上吃火锅。"},
                {"day": 2, "title": "熊猫基地与建设路", "description": "上午熊猫基地，晚上建设路小吃。"},
                {"day": 3, "title": "宽窄巷子与人民公园", "description": "茶馆、盖碗茶、串串。"},
                {"day": 4, "title": "锦里与返程", "description": "锦里小吃和伴手礼。"},
            ],
            "budget": {"total": 2600, "hotel": 1290, "food": 800, "transport": 210, "tickets": 300},
            "notes": ["热门火锅店建议提前取号。", "熊猫基地建议上午早点去。"],
        },
        "trip": {"destination": "成都", "duration_days": 4, "budget": {"max": 3000}},
    },
    {
        "session_id": "s-demo-beijing",
        "task_id": "t-demo-03",
        "plan_id": "ps-demo-03",
        "title": "北京亲子三日游",
        "message": "带孩子去北京三天，想轻松一点。",
        "plan": {
            "overview": "北京亲子三日轻松行程，覆盖故宫、天安门、科技馆和环球度假区。",
            "transport": [{"name": "地铁+预约车", "price": 260, "description": "核心城区地铁，疲惫时使用网约车。"}],
            "hotels": [{"name": "王府井亲子酒店", "price": 680, "description": "靠近地铁和餐饮，适合家庭入住。"}],
            "itinerary": [
                {"day": 1, "title": "天安门与故宫", "description": "上午天安门，故宫控制在半日内。"},
                {"day": 2, "title": "科技馆与奥森", "description": "上午中国科技馆，下午奥林匹克森林公园。"},
                {"day": 3, "title": "环球度假区", "description": "全天环球，选择适合孩子的项目。"},
            ],
            "budget": {"total": 5200, "hotel": 2040, "tickets": 1800, "food": 760, "transport": 600},
            "notes": ["故宫和环球都需要提前预约。", "亲子游建议每天保留午休时间。"],
        },
        "trip": {"destination": "北京", "duration_days": 3, "travelers_count": 3, "traveler_type": "family"},
    },
]


def upsert_demo_data() -> None:
    repo = TaskRepository(Settings().resolved_database_url)
    now = datetime.utcnow()

    with repo._session_factory() as db:
        user = db.scalar(select(User).where(User.username == DEMO_USERNAME))
        password_hash = hash_password(DEMO_PASSWORD, salt="demo-seed-salt")
        if user is None:
            user = User(
                user_id=DEMO_USER_ID,
                username=DEMO_USERNAME,
                email=DEMO_EMAIL,
                password_hash=password_hash,
                created_at=now,
                updated_at=now,
            )
            db.add(user)
        else:
            user.email = DEMO_EMAIL
            user.password_hash = password_hash
            user.updated_at = now
        db.commit()

        for index, item in enumerate(PLANS):
            created_at = now - timedelta(days=index)
            task = db.get(Task, item["task_id"])
            if task is None:
                db.add(
                    Task(
                        task_id=item["task_id"],
                        session_id=item["session_id"],
                        user_id=user.user_id,
                        task_type="chat",
                        status="SUCCEEDED",
                        payload_json={"message": item["message"], "request_id": "seed"},
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
            else:
                task.user_id = user.user_id
                task.status = "SUCCEEDED"
                task.payload_json = {"message": item["message"], "request_id": "seed"}
                task.updated_at = created_at

            snapshot = db.get(PlanSnapshot, item["plan_id"])
            if snapshot is None:
                db.add(
                    PlanSnapshot(
                        plan_id=item["plan_id"],
                        session_id=item["session_id"],
                        user_id=user.user_id,
                        task_id=item["task_id"],
                        version=1,
                        plan_json=item["plan"],
                        created_at=created_at,
                    )
                )
            else:
                snapshot.user_id = user.user_id
                snapshot.task_id = item["task_id"]
                snapshot.plan_json = item["plan"]

            conversation_state = {
                "session_id": item["session_id"],
                "message_history": [
                    {"role": "user", "content": item["message"], "ts": created_at.isoformat()},
                    {"role": "assistant", "content": item["plan"]["overview"], "ts": created_at.isoformat()},
                ],
                "summary": item["title"],
                "current_intent": "itinerary",
                "active_agent": "planner",
                "pending_questions": [],
                "tool_results": {},
                "last_plan": item["plan"],
                "plan_history": [item["plan"]],
                "final_response": item["plan"]["overview"],
                "created_at": created_at.isoformat(),
                "updated_at": created_at.isoformat(),
            }
            trip_state = {
                "origin": None,
                "destination": None,
                "start_date": None,
                "end_date": None,
                "duration_days": None,
                "travelers_count": 1,
                "traveler_type": "adult",
                "budget": None,
                "transport_preferences": {},
                "hotel_preferences": {},
                "attraction_preferences": {},
                "pace_preference": "moderate",
                "must_visit_places": [],
                "excluded_places": [],
                "notes": [],
                **item["trip"],
            }
            state = db.get(SessionState, item["session_id"])
            if state is None:
                db.add(
                    SessionState(
                        session_id=item["session_id"],
                        user_id=user.user_id,
                        conversation_state_json=conversation_state,
                        trip_state_json=trip_state,
                        updated_at=created_at,
                    )
                )
            else:
                state.user_id = user.user_id
                state.conversation_state_json = conversation_state
                state.trip_state_json = trip_state
                state.updated_at = created_at

        db.commit()


if __name__ == "__main__":
    upsert_demo_data()
    print(f"Seeded demo data. Login: {DEMO_USERNAME} / {DEMO_PASSWORD}")
    for plan in PLANS:
        print(f"- {plan['title']} ({plan['session_id']})")
