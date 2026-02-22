# app/db/enums.py
import enum

# Project related enums
class ProjectIdentifierStatus(enum.Enum):
    pending = "pending"
    ok = "ok"
    business_code_conflicted = "business_code_conflicted"
    contract_code_conflicted = "contract_code_conflicted"
    both_conflicted = "both_conflicted"
    


class ProjectNameStatus(enum.Enum):
    pending = "pending"
    matched = "matched"
    unmatched = "unmatched"
    manualy_verified = "manualy_verified"

# AuditLog related enums
class AuditEntityType(enum.Enum):
    User = "user"
    NameMapping = "name_mapping"
    Project = "project"
    FileRecord = "file_record"
    MaterialItem = "material_item"
    PartItem = "part_item"
    LaborItem = "labor_item"
    LogisticsItem = "logistics_item"
    CostSummary = "cost_summary"


class AuditAction(enum.Enum):
    create = "create"
    update = "update"
    confirm = "confirm"
    system = "system"

#FileRecord related enums
class FileType(enum.Enum):
    material_plan = "material_plan"
    part_plan = "part_plan"
    material_cost = "material_cost"
    part_cost = "part_cost"
    labor_cost = "labor_cost"
    logistics_cost = "logistics_cost"
    manual = "manual"   #虚拟File，意味着数据来源是手工录入


class ParseStatus(enum.Enum):
    pending = "pending"
    parsed = "parsed"
    failed = "failed"


class ValidationStatus(enum.Enum):
    pending = "pending"
    ok = "ok"
    warning = "warning"
    confirmed = "confirmed"
    blocked = "failed"

# CostItem related enums
class CostItemStatus(enum.Enum):
    ok = "ok"
    warning = "warning"
    confirmed = "confirmed"
    blocked = "blocked"

# Logistics related enums  
class LogisticsType(enum.Enum):
    TRANSPORT = "transport"        # 运输费用
    INSTALLATION = "installation"  # 安装费用
    OTHER = "other"                # 其他物流相关费用

# CostSummary related enums   
class CostSummaryStatus(enum.Enum):
    ACTIVE = "active"        # 当前有效、可用于报价
    REPLACED = "replaced"    # 已被新版本替代


class NameDomain(enum.Enum):
    COLUMN = "column"
    PROJECT = "project"
    MATERIAL = "material"
    PART = "part"
    LABOR_GROUP = "labor_group"
