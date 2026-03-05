from typing import List, Optional
from uuid import uuid4
from hashlib import sha256
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.file_record import FileRecord, FileType, ParseStatus, ValidationStatus
from app.services.audit_log_service import AuditLogService
class FileRecordService:
    """
    Service for managing FileRecord lifecycle.

    Responsibilities:
    - Upload / re-upload file records (versioned)
    - Maintain parse / validation / locked states
    - Provide valid file selection for cost calculation
    """

    def __init__(
        self,
        db: Session,
        audit_log_service: AuditLogService,
    ):
        self.db = db
        self.audit_log_service = audit_log_service

    def create_update_file_record(
        self,
        *,
        project_id: str,
        file_type: FileType,
        operator_id: str,
        storage_path: str  ,
        original_name: str  ,
        file_bytes: bytes = b'',
    ) -> FileRecord:
        """
        Create a new FileRecord.
        If previous versions exist for the same project + file_type,
        this will create a new version.
        manual file is supported with special handling.
        
        :param project_id: Associated project ID
        :type project_id: str
        :param file_type: Type of the file
        :type file_type: FileType ('material_cost", "part_cost", "labor_cost", "logistics_cost", "material_plan", "part_plan, "manual")
        :param original_name: Original filename as uploaded
        :type original_name: str
        :param storage_path: Storage path where the file is saved
        :type storage_path: str
        :param file_bytes: Raw bytes of the file (for hashing)
        :type file_bytes: bytes
        :param operator_id: User ID of the operator performing the upload
        :type operator_id: str
        """
        """
    Create or update a FileRecord (new version).
    """

        # =========================
        # 🟡 0️⃣ MANUAL FILE BRANCH
        # =========================
        if file_type == FileType.manual:
            # 0.1 计算 version（和普通 file 完全一致）
            latest = (
                self.db.query(FileRecord)
                .filter(
                    FileRecord.project_id == project_id,
                    FileRecord.file_type == file_type,
                )
                .order_by(desc(FileRecord.version))
                .first()
            )
            next_version = 1 if not latest else latest.version + 1

            # 0.2 创建 manual FileRecord
            record = FileRecord(
                id=str(uuid4()),
                project_id=project_id,
                file_type=file_type,
                original_name=original_name,
                uploader_id=operator_id,
                storage_path=None,
                file_hash=None,
                version=next_version,
                parse_status=ParseStatus.parsed,          # 👈 直接 parsed
                validation_status=ValidationStatus.pending,
                locked=False,
            )

            self.db.add(record)
            self.db.flush()

            # 0.3 审计
            self.audit_log_service.record_create(
                project_id=project_id,
                entity_type="FileRecord",
                entity_id=record.id,
                operator_id=operator_id,
            )

            return record
        
        # 1. 计算 file_hash（证据）
        file_bytes = open(storage_path, "rb").read() if file_bytes == b'' else file_bytes
        file_hash = sha256(file_bytes).hexdigest()

        # 2. 计算 version
        latest = (
            self.db.query(FileRecord)
            .filter(
                FileRecord.project_id == project_id,
                FileRecord.file_type == file_type,
            )
            .order_by(desc(FileRecord.version))
            .first()#最大的version
        )
        #如果没有旧版本，version=1；否则+1
        next_version = 1 if not latest else latest.version + 1

        # 3. 创建 FileRecord
        record = FileRecord(
            id=str(uuid4()),
            project_id=project_id,
            file_type=file_type,
            original_name=original_name,
            uploader_id=operator_id,
            storage_path=storage_path,
            file_hash=file_hash,
            version=next_version,
            parse_status=ParseStatus.pending,
            validation_status=ValidationStatus.pending,
            locked=False,
        )

        self.db.add(record)
        self.db.flush()

        # 4. 审计：上传 / 再上传
        self.audit_log_service.record_create(
            project_id=project_id,
            entity_type="FileRecord",
            entity_id=record.id,
            operator_id=operator_id,
        )

        return record
    def list_file_records(
        self,
        *,
        project_id: str,
        file_type: FileType,
    ) -> List[FileRecord]:
        """
        列出某项目下，某类型的所有 FileRecord 版本
        :param project_id: 项目ID
        :type project_id: str
        :param file_type: 文件类型
        :type file_type: FileType
        :return: FileRecord 列表，按 version 降序排列
        :rtype: List[FileRecord]
        """
        return (
            self.db.query(FileRecord)
            .filter(
                FileRecord.project_id == project_id,
                FileRecord.file_type == file_type,
            )
            .order_by(desc(FileRecord.version))
            .all()
        )
        
    def get_latest_valid_file(
        self,
        *,
        project_id: str,
        file_type: FileType,
    ) -> Optional[FileRecord]:
        """
        Return the latest file belonging to the project and file type that:
        - parse_status = parsed
        - validation_status in (ok, confirmed)
        - locked = False
        
        :param project_id: 项目ID
        :type project_id: str
        :param file_type: 文件类型
        :type file_type: FileType
        :return: 满足条件的最新 FileRecord，找不到则返回 None
        """
        return (
            self.db.query(FileRecord)
            .filter(
                FileRecord.project_id == project_id,
                FileRecord.file_type == file_type,
                FileRecord.parse_status == ParseStatus.parsed,
                FileRecord.validation_status.in_(
                    [ValidationStatus.ok, ValidationStatus.confirmed]
                ),
                FileRecord.locked.is_(False),
            )
            .order_by(desc(FileRecord.version))#按version降序排列
            .first()#取第一个，即最新的
        )
    def get_latest_version(
        self,
        *,
        project_id: str,
        file_type: FileType,
    ) -> int:
        """
        Return the latest file belonging to the project and file type that:
        - parse_status = parsed
        - validation_status in (ok, confirmed)
        - locked = False
        
        :param project_id: 项目ID
        :type project_id: str
        :param file_type: 文件类型
        :type file_type: FileType
        :return: 满足条件的最新 FileRecord，找不到则返回 None
        """
        latest_file = self.get_latest_valid_file(project_id=project_id, file_type=file_type)
        return latest_file.version if latest_file else 0

    def lock_file(
        self,
        *,
        file_record: FileRecord,
    ) -> None:
        '''
        将指定 FileRecord 标记为 locked 状态，防止后续被选用
        
        :param file_record: 要锁定的 FileRecord 实例
        :type file_record: FileRecord
        '''
        if file_record.locked:
            return

        old = file_record.locked
        file_record.locked = True

        self.audit_log_service.record_system_update(
            project_id=file_record.project_id,
            entity_type="FileRecord",
            entity_id=file_record.id,
            changed_attribute="locked",
            before_value=old,
            after_value=True,
        )
    def unlock_file(
        self,
        *,
        file_record: FileRecord,
    ) -> None:
        ''' 
        将指定 FileRecord 解除 locked 状态，允许后续被选用 
        (谨慎使用)
        :param file_record: 要解除锁定的 FileRecord 实例
        :type file_record: FileRecord
        '''
        if not file_record.locked:
            return

        old = file_record.locked
        file_record.locked = False

        self.audit_log_service.record_system_update(
            project_id=file_record.project_id,
            entity_type="FileRecord",
            entity_id=file_record.id,
            changed_attribute="locked",
            before_value=old,
            after_value=False,
        )
        
    def is_usable_for_cost(
        self,
        *,
        file_record: FileRecord,
    ) -> bool:
        '''
        校验FileRecord是否可用于成本计算：
   
        - file_type in ("material_cost", "part_cost", "labor_cost", "logistics_cost", "manual")
        - parse_status = parsed
        - validation_status in (ok, confirmed)
        - locked = False
        :param self: Description
        :param file_record: Description
        :type file_record: FileRecord
        :return: Description
        :rtype: bool
        '''
        return (
            file_record.file_type in (
                FileType.material_cost,
                FileType.part_cost,
                FileType.labor_cost,
                FileType.logistics_cost,
                FileType.manual,
            )
            and file_record.parse_status == ParseStatus.parsed
            and file_record.validation_status in (
                ValidationStatus.ok,
                ValidationStatus.confirmed,
            )
            and not file_record.locked
        )

