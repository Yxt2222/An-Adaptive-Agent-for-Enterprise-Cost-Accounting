from pydantic import BaseModel

class ToolRiskProfile(BaseModel):
    '''
    衡量一个工具风险的结构化数据模型
    
    参数	说明
    modifies_persistent_data	是否修改持久化数据（如数据库）
    irreversible	是否不可逆/不可覆盖
    deletes_data	是否删除数据
    affects_multiple_records	是否影响多条记录
    require_human_auth	是否需要人工授权
    '''
    modifies_persistent_data:bool = False
    irreversible:bool = False
    deletes_data:bool = False
    affects_multiple_records:bool = False
    require_human_auth:bool = False