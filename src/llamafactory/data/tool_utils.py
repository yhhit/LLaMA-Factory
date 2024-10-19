# Copyright 2024 the LlamaFactory team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import re
from abc import ABC, abstractmethod
from collections import namedtuple
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Union

from typing_extensions import override

from .data_utils import SLOTS


DEFAULT_TOOL_PROMPT = (
    "You have access to the following tools:\n{tool_text}"
    "Use the following format if using a tool:\n"
    "```\n"
    "Action: tool name (one of [{tool_names}])\n"
    "Action Input: the input to the tool, in a JSON format representing the kwargs "
    """(e.g. ```{{"input": "hello world", "num_beams": 5}}```)\n"""
    "```\n"
)

LLAMA3_TOOL_PROMPT = (
    'Given the following functions, please respond with a JSON for a function call with its proper arguments that best answers the given prompt.\n\n'
    'Respond in the format {{"name": function name, "parameters": dictionary of argument name and its value}}.Do not use variables.\n\n'
    '{tool_text}'
)

GLM4_TOOL_PROMPT = (
    "你是一个名为 ChatGLM 的人工智能助手。你是基于智谱AI训练的语言模型 GLM-4 模型开发的，"
    "你的任务是针对用户的问题和要求提供适当的答复和支持。# 可用工具{tool_text}"
)


FunctionCall = namedtuple("FunctionCall", ["name", "arguments"])


@dataclass
class ToolUtils(ABC):
    """
    Base class for tool utilities.
    """

    @staticmethod
    @abstractmethod
    def get_function_slots() -> SLOTS:
        r"""
        Gets a list of slots corresponding to a single function call.
        """
        ...

    @staticmethod
    @abstractmethod
    def tool_formatter(tools: List[Dict[str, Any]]) -> str:
        r"""
        Generates the system message describing all the available tools.
        """
        ...

    @staticmethod
    @abstractmethod
    def tool_extractor(content: str) -> Union[str, List["FunctionCall"]]:
        r"""
        Extracts all the function calls from the response message.
        """
        ...


class DefaultToolUtils(ToolUtils):
    @override
    @staticmethod
    def get_function_slots() -> SLOTS:
        return ["Action: {{name}}\nAction Input: {{arguments}}\n"]

    @override
    @staticmethod
    def tool_formatter(tools: List[Dict[str, Any]]) -> str:
        tool_text = ""
        tool_names = []
        for tool in tools:
            param_text = ""
            for name, param in tool["parameters"]["properties"].items():
                required, enum, items = "", "", ""
                if name in tool["parameters"].get("required", []):
                    required = ", required"

                if param.get("enum", None):
                    enum = ", should be one of [{}]".format(", ".join(param["enum"]))

                if param.get("items", None):
                    items = ", where each item should be {}".format(param["items"].get("type", ""))

                param_text += "  - {name} ({type}{required}): {desc}{enum}{items}\n".format(
                    name=name,
                    type=param.get("type", ""),
                    required=required,
                    desc=param.get("description", ""),
                    enum=enum,
                    items=items,
                )

            tool_text += "> Tool Name: {name}\nTool Description: {desc}\nTool Args:\n{args}\n".format(
                name=tool["name"], desc=tool.get("description", ""), args=param_text
            )
            tool_names.append(tool["name"])

        return DEFAULT_TOOL_PROMPT.format(tool_text=tool_text, tool_names=", ".join(tool_names))

    @override
    @staticmethod
    def tool_extractor(content: str) -> Union[str, List["FunctionCall"]]:
        regex = re.compile(r"Action:\s*([a-zA-Z0-9_]+)\s*Action Input:\s*(.+?)(?=\s*Action:|\s*$)", re.DOTALL)
        action_match: List[Tuple[str, str]] = re.findall(regex, content)
        if not action_match:
            return content

        results = []
        for match in action_match:
            tool_name = match[0].strip()
            tool_input = match[1].strip().strip('"').strip("```")
            try:
                arguments = json.loads(tool_input)
                results.append((tool_name, json.dumps(arguments, ensure_ascii=False)))
            except json.JSONDecodeError:
                return content

        return results
    
class LLama3ToolUtils(ToolUtils):
    @override
    @staticmethod
    def get_function_slots() -> SLOTS:
        return ['{ "name": "{{name}}", "arguments": "{{arguments}}"}']

    @override
    @staticmethod
    def tool_formatter(tools: List[Dict[str, Any]]) -> str:
        tool_text = ""
        for tool in tools:
            param_text = ""
            for name, param in tool["parameters"]["properties"].items():
                required, enum, items = "", "", ""
                if name in tool["parameters"].get("required", []):
                    required = ", required"

                if param.get("enum", None):
                    enum = ", should be one of [{}]".format(", ".join(param["enum"]))

                if param.get("items", None):
                    items = ", where each item should be {}".format(param["items"].get("type", ""))

                param_text += "  - {name} ({type}{required}): {desc}{enum}{items}\n".format(
                    name=name,
                    type=param.get("type", ""),
                    required=required,
                    desc=param.get("description", ""),
                    enum=enum,
                    items=items,
                )
            warpped_tool = {
                "type": "function",
                "function": tool
            }

            tool_text += json.dumps(warpped_tool,ensure_ascii=False,indent=4)+"\n\n"

        return LLAMA3_TOOL_PROMPT.format(tool_text=tool_text)

    @override
    @staticmethod
    def tool_extractor(content: str) -> Union[str, List["FunctionCall"]]:
        regex = re.compile(r"Action:\s*([a-zA-Z0-9_]+)\s*Action Input:\s*(.+?)(?=\s*Action:|\s*$)", re.DOTALL)
        action_match: List[Tuple[str, str]] = re.findall(regex, content)
        if not action_match:
            return content

        results = []
        for match in action_match:
            tool_name = match[0].strip()
            tool_input = match[1].strip().strip('"').strip("```")
            try:
                arguments = json.loads(tool_input)
                results.append((tool_name, json.dumps(arguments, ensure_ascii=False)))
            except json.JSONDecodeError:
                return content

        return results


class GLM4ToolUtils(ToolUtils):
    @override
    @staticmethod
    def get_function_slots() -> SLOTS:
        return ["{{name}}\n{{arguments}}"]

    @override
    @staticmethod
    def tool_formatter(tools: List[Dict[str, Any]]) -> str:
        tool_text = ""
        for tool in tools:
            tool_text += "\n\n## {name}\n\n{body}\n在调用上述函数时，请使用 Json 格式表示调用的参数。".format(
                name=tool["name"], body=json.dumps(tool, indent=4, ensure_ascii=False)
            )

        return GLM4_TOOL_PROMPT.format(tool_text=tool_text)

    @override
    @staticmethod
    def tool_extractor(content: str) -> Union[str, List["FunctionCall"]]:
        if "\n" not in content:
            return content

        tool_name, tool_input = content.split("\n", maxsplit=1)
        try:
            arguments = json.loads(tool_input)
        except json.JSONDecodeError:
            return content

        return [(tool_name, json.dumps(arguments, ensure_ascii=False))]

def default_observation_utils(content):
    return content


def llama3_observation_utils(content):
    try:
        json.loads(content)
        return content
    except ValueError:
        content = json.dumps(
                    {
                        "output": content
                    },
                    ensure_ascii=False,
                )
    return content

def default_system_utils(content, tool_text):
    return content + "\n\n" + tool_text

def llama3_system_utils(content, tool_text):
    return content

TOOLS = {
    "default": DefaultToolUtils(),
    "glm4": GLM4ToolUtils(),
    "llama3": LLama3ToolUtils()
}

OBSERVATIONS = {
    "default": default_observation_utils,
    "llama3": llama3_observation_utils
}

SYSTEM = {
    "default": default_system_utils,
    "llama3": llama3_system_utils
}


def get_tool_utils(name: str) -> "ToolUtils":
    tool_utils = TOOLS.get(name, None)
    if tool_utils is None:
        raise ValueError("Tool utils `{}` not found.".format(name))

    return tool_utils

def get_observation_utils(name: str):
    observation_utils = OBSERVATIONS.get(name, None)
    if observation_utils is None:
        raise ValueError("Observation utils `{}` not found.".format(name))

    return observation_utils

def get_system_utils(name: str):
    system_utils = SYSTEM.get(name, None)
    if system_utils is None:
        raise ValueError("System utils `{}` not found.".format(name))

    return system_utils