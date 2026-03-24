"""使用 Locust 压测 LangGraph StreamingClient SDK."""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from locust import User, task, between, events

from src.clients import StreamingClient

logger = logging.getLogger(__name__)
RUN_LOG_DIR: Path | None = None
PROGRESS_EVERY_CHUNKS = int(os.getenv("LOCUST_PROGRESS_EVERY_CHUNKS", "20"))


def _serialize_chunk(chunk: Any) -> str:
    return json.dumps(
        {
            "event": getattr(chunk, "event", None),
            "data": getattr(chunk, "data", None),
        },
        ensure_ascii=False,
        default=str,
    )


def _get_run_log_dir() -> Path:
    global RUN_LOG_DIR
    if RUN_LOG_DIR is None:
        log_root = Path(os.getenv("LOCUST_STREAM_LOG_DIR", "logs/locust-streaming-sdk"))
        log_root.mkdir(parents=True, exist_ok=True)
        RUN_LOG_DIR = log_root / datetime.now().strftime("%Y%m%d-%H%M%S")
        RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    return RUN_LOG_DIR


@events.init.add_listener
def on_locust_init(environment, **kwargs) -> None:
    log_dir = _get_run_log_dir()
    logger.info("Locust Streaming SDK initialized. log_dir=%s", log_dir)
    print(f"[locust-streaming-sdk] initialized, log_dir={log_dir}", flush=True)


class StreamingSdkUser(User):
    """通过 StreamingClient.chat_stream 执行 Locust 压测."""

    wait_time = between(
        float(os.getenv("LOCUST_WAIT_MIN", "1")),
        float(os.getenv("LOCUST_WAIT_MAX", "3")),
    )

    abstract = False

    def on_start(self) -> None:
        self.host = os.getenv("TEST_HOST", "https://agent.schoopia.com")
        self.assistant_id = os.getenv("TEST_ASSISTANT_ID", "research")
        self.user_id = os.getenv("TEST_USER_ID", "user001")
        self.message = os.getenv("TEST_MESSAGE", "测试10个工具调用")
        self.system_prompt = os.getenv(
            "TEST_SYSTEM_PROMPT",
            "你是一个专业的技术顾问，擅长回答编程问题。",
        )
        self.streaming_client = StreamingClient(url=self.host, assistant_id=self.assistant_id)
        self.log_dir = _get_run_log_dir()
        logger.info(
            "User started. host=%s assistant_id=%s log_dir=%s",
            self.host,
            self.assistant_id,
            self.log_dir,
        )
        print(
            f"[locust-streaming-sdk] user_started host={self.host} "
            f"assistant_id={self.assistant_id} log_dir={self.log_dir}",
            flush=True,
        )

    @task
    def chat_stream_task(self) -> None:
        asyncio.run(self._run_stream())

    async def _run_stream(self) -> None:
        thread_id = str(uuid.uuid4())
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        response_length = 0
        chunk_count = 0
        log_file = self.log_dir / f"{request_id}.log"

        with log_file.open("w", encoding="utf-8") as fp:
            print(
                f"[locust-streaming-sdk] request_started request_id={request_id} "
                f"thread_id={thread_id} log_file={log_file}",
                flush=True,
            )
            fp.write(
                f"thread_id={thread_id} request_id={request_id} "
                f"started_at={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            fp.flush()
            try:
                async for chunk in self.streaming_client.chat_stream(
                    message=self.message,
                    system_prompt=self.system_prompt,
                    thread_id=thread_id,
                    multitask_strategy="reject",
                    stream_subgraphs=True,
                    on_disconnect="cancel",
                    on_completion="keep",
                    durability="async",
                    metadata={"user_id": self.user_id, "name": f"locust-{request_id}"},
                ):
                    line = _serialize_chunk(chunk)
                    chunk_count += 1
                    response_length += len(line.encode("utf-8"))
                    fp.write(line + "\n")
                    fp.flush()
                    if chunk_count == 1 or chunk_count % PROGRESS_EVERY_CHUNKS == 0:
                        elapsed_ms = (time.perf_counter() - started) * 1000
                        print(
                            f"[locust-streaming-sdk] request_progress request_id={request_id} "
                            f"thread_id={thread_id} chunks={chunk_count} "
                            f"elapsed_ms={elapsed_ms:.2f} log_file={log_file}",
                            flush=True,
                        )

            except Exception as exc:
                elapsed_ms = (time.perf_counter() - started) * 1000
                fp.write(
                    f"finished_at={datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
                    f"success=false chunks={chunk_count} error={type(exc).__name__}: {exc}\n"
                )
                fp.flush()
                logger.exception(
                    "Request failed. request_id=%s thread_id=%s log_file=%s",
                    request_id,
                    thread_id,
                    log_file,
                )
                print(
                    f"[locust-streaming-sdk] request_failed request_id={request_id} "
                    f"thread_id={thread_id} error={type(exc).__name__}: {exc} "
                    f"log_file={log_file}",
                    flush=True,
                )
                events.request.fire(
                    request_type="sdk",
                    name="chat_stream",
                    response_time=elapsed_ms,
                    response_length=response_length,
                    exception=exc,
                    context={"thread_id": thread_id, "log_file": str(log_file)},
                )
                return

            elapsed_ms = (time.perf_counter() - started) * 1000
            fp.write(
                f"finished_at={datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
                f"success=true chunks={chunk_count}\n"
            )
            fp.flush()
            logger.info(
                "Request finished. request_id=%s thread_id=%s response_time_ms=%.2f chunks=%s log_file=%s",
                request_id,
                thread_id,
                elapsed_ms,
                chunk_count,
                log_file,
            )
            print(
                f"[locust-streaming-sdk] request_finished request_id={request_id} "
                f"thread_id={thread_id} response_time_ms={elapsed_ms:.2f} "
                f"chunks={chunk_count} "
                f"log_file={log_file}",
                flush=True,
            )
            events.request.fire(
                request_type="sdk",
                name="chat_stream",
                response_time=elapsed_ms,
                response_length=response_length,
                exception=None,
                context={"thread_id": thread_id, "log_file": str(log_file)},
            )
