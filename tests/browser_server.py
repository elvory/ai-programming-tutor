"""Local browser acceptance fixture: temporary data and fake HTTP transport.

Not a production mode. No real credentials, .env loading, or external model
requests are permitted here. Run from the repository root.
"""
import argparse
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def fake_response(request, **kwargs):
    if request.full_url != "https://api.deepseek.com/responses":
        raise AssertionError("Only the mocked Responses endpoint is permitted")
    payload = json.loads(request.data)
    context = json.loads(payload["input"])
    code = context["code"]
    if "QA_TIMEOUT" in code:
        raise TimeoutError("Synthetic timeout")
    if "QA_SLOW" in code:
        time.sleep(1.5)
    title = context["problem"].get("title_zh", "当前题目")
    diagnosis = {
        "error_type": "边界条件风险",
        "knowledge": "循环边界与返回值",
        "analysis": f"结合《{title}》检查循环的最后一次访问，并确认返回值符合题目要求。这是浏览器验收使用的模拟网络响应。",
        "hints": [
            "先检查循环最后一次访问的位置。",
            "用最短合法输入，手动列出每一步索引与返回值。",
            "把访问索引始终保持在有效范围内，再对照示例检查返回值。",
        ],
    }
    response = {"status": "completed", "output": [{"type": "message", "role": "assistant",
                "content": [{"type": "output_text", "text": json.dumps(diagnosis, ensure_ascii=False)}]}]}
    return io.BytesIO(json.dumps(response, ensure_ascii=False).encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tutor-browser-acceptance-") as directory:
        os.environ["AI_TUTOR_RECORDS_PATH"] = str(Path(directory) / "records.json")
        os.environ["AI_TUTOR_ACTIVITIES_PATH"] = str(Path(directory) / "activities.json")
        os.environ["DEEPSEEK_API_KEY"] = "synthetic-browser-key-never-real"
        os.environ["DEEPSEEK_MODEL"] = "deepseek-flash"
        import services.llm_service as llm
        llm.load_dotenv = lambda *args, **kwargs: None
        llm.urlopen = fake_response
        import uvicorn
        from backend.app import app
        @app.middleware("http")
        async def identify_isolated_fixture(request, call_next):
            response = await call_next(request)
            response.headers["X-AI-Tutor-Test-Fixture"] = "temporary-data;mock-deepseek"
            return response
        print("BROWSER_ACCEPTANCE: temporary data; real DeepSeek HTTP disabled", flush=True)
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
