import hashlib
import os
import pandas as pd

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.raw_upload_record import RawUploadRecord
from app.services.audit_log_service import AuditLogService
from app.db.enums import RawUploadStatus, FileType


class RawUploadRecordService:

    def __init__(self, db: Session, audit_log_service: AuditLogService):
        self.db = db
        self.audit_log_service = audit_log_service

    def _calculate_hash(self, storage_path: str) -> str:
        hasher = hashlib.sha256()
        with open(storage_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _match_file_type(self,columns):
            REQUIRED_COLUMNS = {
            "material_cost": ["名称", "规格型号", "数量", "单位", "材质", "参考重量\n（kg）", "单价", "小计"],
            "part_cost": ["名称", "规格型号", "数量", "单位", "单价", "小计"],
            "labor_cost": ["班组（外协单位）", "数量", "单位", "单价", "加工费", "吨位奖金", "箱梁攻丝费、行走、液压站组装费、溜槽补助", "小计"],
            "logistics_cost": ["类型", "备注", "小计"],
            }
            for file_type, required in REQUIRED_COLUMNS.items():
                if all(col in columns for col in required):
                    return file_type
            return None

    def _detect_file_type(self, columns: list[str]) -> FileType | None:
        mapping = {
        "material_cost": FileType.material_cost,
        "part_cost": FileType.part_cost,
        "labor_cost": FileType.labor_cost,
        "logistics_cost": FileType.logistics_cost,
        }

        matched = self._match_file_type(columns)
        if not matched:
            return None
        return mapping.get(matched)

    def _next_version(self, agent_run_id: str, file_type: FileType) -> int:
        '''
        校验后的raw_file_record根据在同一agent_run_id下，同类型文件的最大version基础上递增来确定版本号。
        如果校验不通过，version保持为0，type保持为None，表示未查验或者查验类型失败。
        '''
        allow_types = [FileType.material_cost, FileType.part_cost, FileType.labor_cost, FileType.logistics_cost]
        if file_type not in allow_types:
            return 0
        
        max_version = (
            self.db.query(RawUploadRecord.version)
            .filter(
                RawUploadRecord.agent_run_id == agent_run_id,
                RawUploadRecord.file_type == file_type,
            )
            .order_by(RawUploadRecord.version.desc())
            .first()
        )

        if not max_version:
            return 1

        return max_version[0] + 1

    def create_from_uploaded_file(
        self,
        *,
        agent_run_id: str,
        original_filename: str,
        storage_path: str,
        operator_id: str,
    ) -> RawUploadRecord:

        try:
            size = os.path.getsize(storage_path)
            file_hash = self._calculate_hash(storage_path)

            # 尝试读取 Excel
            detected_type = None
            detected_columns = None
            probe_error = None
            status = RawUploadStatus.staged
            version = 0

            try:
                df = pd.read_excel(storage_path)
                detected_columns = list(df.columns)
                detected_type = self._detect_file_type(detected_columns)

                if detected_type:
                    version = self._next_version(agent_run_id, detected_type)
                    status = RawUploadStatus.probed
                else:
                    # 可读但不匹配
                    probe_error = "File read successfully but required columns not detected. File type undetermined."
                    status = RawUploadStatus.staged

            except Exception as e:
                # 读取失败仍然创建记录
                probe_error = str(e)
                status = RawUploadStatus.staged

            record = RawUploadRecord(
                agent_run_id=agent_run_id,
                original_filename=original_filename,
                storage_path=storage_path,
                file_hash=file_hash,
                size=size,
                file_type=detected_type,
                version=version,
                status=status,
                detected_columns=detected_columns,
                probe_error=probe_error,
            )
            self.db.add(record)
            self.db.flush()
            
             #审计
            self.audit_log_service.record_create(
                project_id=None,
                entity_type="RawFileRecord",
                entity_id=record.id,
                operator_id=operator_id,
            )
            return record

        except SQLAlchemyError as e:
            self.db.rollback()
            raise e
    def list_by_run(self, agent_run_id:str, file_type: str | None = None, status: str | None = None) -> list[RawUploadRecord]:
        '''
        输入agent_run_id和可选的file_type,status，返回该agent_run_id下符合状态的所有raw_upload_record，按上传时间倒序排列。
        agent_run_id: 关联的agent_run_id
        file_type: 可选的FileType枚举值，如果提供则过滤出符合文件类型的记录
        status: 可选的RawUploadStatus枚举值，如果提供则过滤出符合状态
        '''
        file_type_mapping = {s.value: s for s in FileType}
        status_mapping ={s.value:s for s in RawUploadStatus}
        if file_type is not None:
            if file_type not in file_type_mapping:
                raise ValueError(f"Invalid file_type. Allowed values are: {', '.join(file_type_mapping.keys())}")
        if status is not None:
            if status not in  status_mapping:
                raise ValueError(f"Invalid status. Allowed values are: {', '.join(status_mapping.keys())}")
        
        query = self.db.query(RawUploadRecord).filter(RawUploadRecord.agent_run_id == agent_run_id).order_by(RawUploadRecord.upload_time.desc())
        if file_type is not None:
            query = query.filter(RawUploadRecord.file_type == file_type_mapping.get(file_type))
        if status is not None:
            query = query.filter(RawUploadRecord.status == status_mapping.get(status))
        return query.all()
    
    def get_by_id(self, raw_upload_id: str) -> RawUploadRecord | None:
        return self.db.query(RawUploadRecord).filter(RawUploadRecord.id == raw_upload_id).first()

    def confirm_file_type(self, agent_run_id:str,raw_upload_id: str, operator_id:str) -> None:
        '''
        用户授权后确认文件类型，只有状态为probed且成功探测出文件类型的记录才允许确认，确认后状态更新为confirmed，并记录审计日志。
        agent_run_id: 关联的agent_run_id
        raw_upload_id: 待确认的RawUploadRecord的id
        operator_id: 执行确认操作的用户id
        '''
        raw_record = self.db.query(RawUploadRecord).filter(RawUploadRecord.id == raw_upload_id).first()
        #空值校验
        if not raw_record:
            raise ValueError(f"RawUploadRecord with id {raw_upload_id} not found.")
        #agent_run_id校验
        if raw_record.agent_run_id != agent_run_id:
            raise ValueError(f"RawUploadRecord with id {raw_upload_id} does not belong to agent_run_id {agent_run_id}.Cross-run operation forbidden.")
        #状态校验，只有probed状态的记录才允许确认
        if raw_record.status != RawUploadStatus.probed:
            raise ValueError(f"RawUploadRecord with id {raw_upload_id} is not in probed status and cannot be confirmed. Only probed records can be confirmed.")
        #类型校验, 只有成功探测出文件类型的记录才允许确认
        if raw_record.file_type is None:
            raise ValueError(f"RawUploadRecord with id {raw_upload_id} has undetermined file type and cannot be confirmed.")
        #确认后状态更新为confirmed
        raw_record.status = RawUploadStatus.confirmed
        self.db.flush()
        self.db.commit()
        #审计
        self.audit_log_service.record_update(
            project_id=None,
            entity_type="RawFileRecord",
            entity_id=raw_record.id,
            changed_attribute="status",
            before_value=RawUploadStatus.probed.value,
            after_value=RawUploadStatus.confirmed.value,
            operator_id=operator_id,
        )
        
        
         