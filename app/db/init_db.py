from app.db.session import get_engine
from app.db.base import Base

#-------------------导入所有表-----------------------
from app.models.user import User
from app.models.project import Project
from app.models.file_record import FileRecord
from app.models.material_item import MaterialItem
from app.models.part_item import PartItem
from app.models.labor_item import LaborItem
from app.models.logistics_item import LogisticsItem
from app.models.cost_summary import CostSummary
from app.models.name_mapping import NameMapping
from app.models.audit_log import AuditLog
from app.models.raw_upload_record import RawUploadRecord
from app.models.Semantic_infra_related_models import SchemaInstanceModel, ChangeRecordModel, SemanticObjectModel

def init_db():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
