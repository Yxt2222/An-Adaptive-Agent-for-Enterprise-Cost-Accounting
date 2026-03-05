import json
from pydantic import BaseModel
from typing import List, Optional

from app.agentic.schemas.error_type import ErrorType
from app.agentic.schemas.error_type import ErrorType
from app.agentic.schemas.tool_result import ToolResult

from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.tools.registry import tool_registry

from openai import AsyncOpenAI,OpenAI
import asyncio
#全局单例，减少重复创建client的开销
 
class ExtractedInfo(BaseModel):
    raw_name: Optional[str] = None
    contract_code: Optional[str] = None
    business_code: Optional[str] = None
    spec_tags: Optional[List[str]] = None
def build_prompt(user_input: str) -> str:
    return f"""
    你是一个企业级结构化信息抽取助手。
    从用户输入中提取以下字段：

    - raw_name：项目名称,通常为不带修饰的名词术语，不包含规格特征（最重要）
    - contract_code：合同编号:可由数字，字母，-_等符号组成（如有）
    - business_code：产品编号:可由数字，字母，-_等符号组成（如有）
    - spec_tags：规格特征:对项目的修饰和形容，如“36m”、“双逃生通道”等（如有）

    规则：
    1. 如果任何字段不存在，返回 null
    2. spec_tags 必须是字符串数组，如果和项目名称在一起，请把他们拆开
    3. 只输出 JSON
    4. 不要解释，不要添加额外内容

    用户输入：
    "{user_input}"
    """
    
'''
client = AsyncOpenAI(
        api_key="none",
        base_url="http://localhost:11434/v1"
    )

async def call_qwen_async(user_input: str) -> ExtractedInfo:
    #异步调用每次都会创建event loop,关闭event loop,重建loop，开销大，费时多。

    prompt = build_prompt(user_input)

    response = await client.chat.completions.create(
        model="qwen2.5:7b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    content = response.choices[0].message.content.strip() if response.choices[0].message.content else "{}"
    # 解析 JSON
    parsed = json.loads(content)
    return ExtractedInfo(**parsed)
'''
client = OpenAI(
        api_key="none",
        base_url="http://localhost:11434/v1"
    )

def call_qwen(user_input: str) -> ExtractedInfo:
    #异步调用每次都会创建event loop,关闭event loop,重建loop，开销大，费时多。

    prompt = build_prompt(user_input)

    response = client.chat.completions.create(
        model="qwen2.5:7b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    content = response.choices[0].message.content or "{}"
    parsed = json.loads(content)

    return ExtractedInfo(**parsed)
    

def extract_project_info_tool(user_message: str) -> ToolResult:

    try:
        # 调用 LLM（
        extracted_info = call_qwen(user_message)

        # 强制 schema 安全
        result = {
            "raw_name": extracted_info.raw_name,
            "contract_code": extracted_info.contract_code,
            "business_code": extracted_info.business_code,
            "spec_tags": extracted_info.spec_tags 
        }

        return ToolResult(
            tool_name="extract_project_info_tool",
            ok=True,
            data=result,
            explanation="Project information extracted successfully.",
            side_effect=False,
            irreversible=False
        )

    except Exception as e:
        return ToolResult(
            tool_name="extract_project_info_tool",
            ok=False,
            error_type=ErrorType.TOOL_CALL_ERROR,
            error_message=str(e),
            explanation="Failed to extract structured project info.Please try again.",
            side_effect=False,
            irreversible=False
        )

# ---- ToolSpec 注册 ----
tool_registry.register(ToolSpec(
        name="extract_project_info_tool",
        func=extract_project_info_tool,
        description="""
        从用户自然语言输入中提取项目基础信息字段。
        本工具仅做信息抽取，不创建项目，不修改数据库。
        提取字段包括：
        - raw_name（项目原始名称）
        - contract_code（合同编号，可选）
        - business_code（产品编号，可选）
        - spec_tags（规格特征列表，可选）
        """,
        input_schema={
            "user_input": "str"
        },
        output_schema='''{
            "raw_name":  "str",
            "contract_code": "str",
            "business_code":"str",
            "spec_tags": "list[str]" 
        }''',
        risk_profile=ToolRiskProfile(
            modifies_persistent_data=False,
            irreversible=False,
            deletes_data=False,
            affects_multiple_records=False,
            require_human_auth=False
        )
    )
)

# 运行示例
if __name__ == "__main__":
    userinput = "24米仰拱栈桥带双向逃生隧道，合同编号HZ-2024-001，产品编号SP-1001。"
    tool_result = extract_project_info_tool(userinput)
    print(tool_result.tool_name)
    print(tool_result.ok)
    print(tool_result.data)
    if tool_result.data:
        print(tool_result.data.get("raw_name"))
        print(tool_result.data.get("contract_code"))
        print(tool_result.data.get("business_code"))
        print(tool_result.data.get("spec_tags"))