"""运行时动态 schema 工具中间件。

通过 `config.configurable.dynamic_tools` 传入工具 schema，
在每次 run 的模型调用前动态追加到 request.tools。

这些工具为占位 stub tool：
- 不执行真实业务逻辑
- 默认回显调用参数（echo）
- 用于让客户端获取模型生成的结构化 tool call 参数
"""

from __future__ import annotations

import json
import keyword
import logging
import re
from typing import Any, Callable

from langchain.agents.middleware.types import AgentMiddleware, ContextT, ModelRequest, ModelResponse, ResponseT
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict, Field, create_model

logger = logging.getLogger(__name__)

DYNAMIC_TOOLS_CONFIG_KEY = "dynamic_tools"
SUPPORTED_RESPONSE_MODES = {"echo", "ack", "template"}


class _DynamicToolBaseModel(BaseModel):
    """动态工具参数模型基类。"""

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class DynamicSchemaToolsMiddleware(AgentMiddleware):
    """从 config.configurable 读取动态工具 schema 并注入到当前 run 的 tools。"""

    def __init__(
        self,
        config_key: str = DYNAMIC_TOOLS_CONFIG_KEY,
        default_response_mode: str = "echo",
    ):
        self.config_key = config_key
        self.default_response_mode = default_response_mode
        self.tools: list[Any] = []

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        return handler(self._inject_dynamic_tools(request))

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Any],
    ) -> ModelResponse[ResponseT]:
        return await handler(self._inject_dynamic_tools(request))

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage],
    ) -> ToolMessage:
        stub_result = self._build_dynamic_tool_message(request)
        if stub_result is not None:
            return stub_result
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ) -> ToolMessage:
        stub_result = self._build_dynamic_tool_message(request)
        if stub_result is not None:
            return stub_result
        return await handler(request)

    def _inject_dynamic_tools(self, request: ModelRequest[ContextT]) -> ModelRequest[ContextT]:
        configurable = self._get_configurable()
        raw_specs = configurable.get(self.config_key)
        if not raw_specs:
            return request

        if not isinstance(raw_specs, list):
            logger.warning("DynamicSchemaToolsMiddleware: '%s' 必须是 list，实际为 %s", self.config_key, type(raw_specs).__name__)
            return request

        existing_names = {self._get_tool_name(tool) for tool in request.tools}
        dynamic_tools: list[StructuredTool] = []

        for index, spec in enumerate(raw_specs):
            tool = self._build_tool(spec, index=index, existing_names=existing_names)
            if tool is None:
                continue
            dynamic_tools.append(tool)
            existing_names.add(tool.name)

        if not dynamic_tools:
            return request

        logger.info("DynamicSchemaToolsMiddleware: 为本次 run 注入 %s 个动态工具", len(dynamic_tools))
        return request.override(tools=[*request.tools, *dynamic_tools])

    def _get_configurable(self) -> dict[str, Any]:
        cfg: RunnableConfig | dict[str, Any] | None = get_config()
        if not cfg:
            return {}
        if isinstance(cfg, dict):
            configurable = cfg.get("configurable", {})
            return configurable if isinstance(configurable, dict) else {}
        configurable = cfg.get("configurable", {})
        return configurable if isinstance(configurable, dict) else {}

    def _build_tool(
        self,
        spec: Any,
        *,
        index: int,
        existing_names: set[str],
    ) -> StructuredTool | None:
        if not isinstance(spec, dict):
            logger.warning("DynamicSchemaToolsMiddleware: dynamic_tools[%s] 必须是 dict", index)
            return None

        name = spec.get("name")
        description = spec.get("description")
        input_schema = spec.get("input_schema")
        response_mode = spec.get("stub_response_mode", self.default_response_mode)
        response_template = spec.get("stub_response_template")

        if not isinstance(name, str) or not name.strip():
            logger.warning("DynamicSchemaToolsMiddleware: dynamic_tools[%s].name 缺失或非法", index)
            return None
        name = name.strip()

        if name in existing_names:
            logger.warning("DynamicSchemaToolsMiddleware: 跳过重名动态工具 '%s'", name)
            return None

        if not isinstance(description, str) or not description.strip():
            description = f"动态注入工具 {name}。调用后不会真实执行，仅返回占位结果。"

        if response_mode not in SUPPORTED_RESPONSE_MODES:
            logger.warning(
                "DynamicSchemaToolsMiddleware: dynamic_tools[%s].stub_response_mode=%s 不支持，回退为 %s",
                index,
                response_mode,
                self.default_response_mode,
            )
            response_mode = self.default_response_mode

        args_schema = self._create_args_schema(name, input_schema)

        async def _dynamic_tool(**kwargs: Any) -> str:
            payload = self._build_stub_response(
                tool_name=name,
                arguments=kwargs,
                response_mode=response_mode,
                response_template=response_template,
            )
            return json.dumps(payload, ensure_ascii=False)

        return StructuredTool.from_function(
            coroutine=_dynamic_tool,
            name=name,
            description=description,
            args_schema=args_schema,
        )

    def _build_dynamic_tool_message(self, request: ToolCallRequest) -> ToolMessage | None:
        tool_call = request.tool_call
        tool_name = tool_call.get("name")
        if not isinstance(tool_name, str) or not tool_name:
            return None

        spec = self._find_dynamic_spec(tool_name)
        if spec is None:
            return None

        arguments = tool_call.get("args", {})
        if isinstance(arguments, str):
            try:
                parsed_arguments = json.loads(arguments)
            except json.JSONDecodeError:
                parsed_arguments = {"raw_args": arguments}
        elif isinstance(arguments, dict):
            parsed_arguments = arguments
        else:
            parsed_arguments = {"raw_args": arguments}

        response_mode = spec.get("stub_response_mode", self.default_response_mode)
        if response_mode not in SUPPORTED_RESPONSE_MODES:
            response_mode = self.default_response_mode

        payload = self._build_stub_response(
            tool_name=tool_name,
            arguments=parsed_arguments,
            response_mode=response_mode,
            response_template=spec.get("stub_response_template"),
        )

        return ToolMessage(
            content=json.dumps(payload, ensure_ascii=False),
            tool_call_id=tool_call["id"],
            name=tool_name,
            status="success",
        )

    def _find_dynamic_spec(self, tool_name: str) -> dict[str, Any] | None:
        raw_specs = self._get_configurable().get(self.config_key)
        if not isinstance(raw_specs, list):
            return None

        for spec in raw_specs:
            if not isinstance(spec, dict):
                continue
            name = spec.get("name")
            if isinstance(name, str) and name.strip() == tool_name:
                return spec
        return None

    def _build_stub_response(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        response_mode: str,
        response_template: Any,
    ) -> dict[str, Any]:
        if response_mode == "ack":
            return {
                "ok": True,
                "tool": tool_name,
                "message": "dynamic tool acknowledged",
            }

        if response_mode == "template":
            return {
                "ok": True,
                "tool": tool_name,
                "message": response_template if response_template is not None else f"{tool_name} accepted",
                "arguments": arguments,
            }

        return {
            "ok": True,
            "tool": tool_name,
            "arguments": arguments,
        }

    def _create_args_schema(self, tool_name: str, input_schema: Any) -> type[BaseModel]:
        if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
            logger.warning(
                "DynamicSchemaToolsMiddleware: 工具 '%s' 的 input_schema 缺失或不是 object，回退为宽松 payload 模式",
                tool_name,
            )
            return create_model(
                f"{self._safe_model_name(tool_name)}Args",
                __base__=_DynamicToolBaseModel,
                payload=(dict[str, Any], Field(default=..., description="动态工具原始参数对象")),
            )

        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        if not isinstance(properties, dict):
            properties = {}
        if not isinstance(required, list):
            required = []

        field_definitions: dict[str, tuple[Any, Any]] = {}
        used_names: set[str] = set()

        for original_name, schema in properties.items():
            if not isinstance(original_name, str):
                continue
            if not isinstance(schema, dict):
                schema = {}

            field_name = self._safe_field_name(original_name, used_names)
            field_type = self._json_schema_to_python_type(
                schema,
                model_name_prefix=f"{self._safe_model_name(tool_name)}_{field_name}",
            )
            description = schema.get("description") if isinstance(schema.get("description"), str) else None
            is_required = original_name in required

            if is_required:
                field_definitions[field_name] = (
                    field_type,
                    Field(default=..., description=description, alias=original_name),
                )
            else:
                field_definitions[field_name] = (
                    field_type | None,
                    Field(default=None, description=description, alias=original_name),
                )

        if not field_definitions:
            field_definitions["payload"] = (
                dict[str, Any],
                Field(default=..., description="动态工具原始参数对象"),
            )

        return create_model(
            f"{self._safe_model_name(tool_name)}Args",
            __base__=_DynamicToolBaseModel,
            **field_definitions,
        )

    def _json_schema_to_python_type(self, schema: dict[str, Any], *, model_name_prefix: str) -> Any:
        schema_type = schema.get("type")

        if isinstance(schema_type, list):
            non_null_types = [item for item in schema_type if item != "null"]
            schema_type = non_null_types[0] if non_null_types else None

        if schema_type == "string":
            return str
        if schema_type == "integer":
            return int
        if schema_type == "number":
            return float
        if schema_type == "boolean":
            return bool
        if schema_type == "array":
            items = schema.get("items")
            if isinstance(items, dict):
                item_type = self._json_schema_to_python_type(items, model_name_prefix=f"{model_name_prefix}Item")
            else:
                item_type = Any
            return list[item_type]
        if schema_type == "object":
            properties = schema.get("properties")
            if isinstance(properties, dict) and properties:
                required = schema.get("required", [])
                if not isinstance(required, list):
                    required = []
                nested_fields: dict[str, tuple[Any, Any]] = {}
                used_names: set[str] = set()
                for original_name, nested_schema in properties.items():
                    if not isinstance(original_name, str):
                        continue
                    if not isinstance(nested_schema, dict):
                        nested_schema = {}
                    field_name = self._safe_field_name(original_name, used_names)
                    nested_type = self._json_schema_to_python_type(
                        nested_schema,
                        model_name_prefix=f"{model_name_prefix}_{field_name}",
                    )
                    description = nested_schema.get("description") if isinstance(nested_schema.get("description"), str) else None
                    if original_name in required:
                        nested_fields[field_name] = (
                            nested_type,
                            Field(default=..., description=description, alias=original_name),
                        )
                    else:
                        nested_fields[field_name] = (
                            nested_type | None,
                            Field(default=None, description=description, alias=original_name),
                        )
                return create_model(model_name_prefix, __base__=_DynamicToolBaseModel, **nested_fields)
            return dict[str, Any]
        return Any

    @staticmethod
    def _safe_model_name(name: str) -> str:
        sanitized = re.sub(r"\W|^(?=\d)", "_", name).strip("_")
        return sanitized or "DynamicTool"

    @staticmethod
    def _safe_field_name(name: str, used_names: set[str]) -> str:
        candidate = re.sub(r"\W|^(?=\d)", "_", name).strip("_") or "field"
        if keyword.iskeyword(candidate):
            candidate = f"{candidate}_"
        base = candidate
        suffix = 2
        while candidate in used_names:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used_names.add(candidate)
        return candidate

    @staticmethod
    def _get_tool_name(tool: Any) -> str:
        if hasattr(tool, "name") and isinstance(tool.name, str):
            return tool.name
        if isinstance(tool, dict):
            name = tool.get("name")
            if isinstance(name, str):
                return name
        return ""
