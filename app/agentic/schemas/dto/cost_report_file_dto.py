from datetime import datetime
from pydantic import BaseModel


class CostReportFileDTO(BaseModel):
    """
    给 Agent / 前端传递“可下载报表文件”的最小必要信息。

    设计原则：
    - 不返回报表全部内容
    - 只返回前端下载与业务关联所需字段
    - 字段保持 JSON-safe，适合进入 ToolResult.data
    """
    #保证前端和业务侧知道这份报表属于谁
    cost_summary_id: str
    project_id: str
    calculation_version: int
    #保证前端能下载展示
    file_name: str
    storage_path: str
    download_url: str
    mime_type: str
    
    #保证前端知道报表生成时间
    generated_at: datetime
