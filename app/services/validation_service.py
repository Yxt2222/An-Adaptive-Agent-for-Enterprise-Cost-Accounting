# app/services/validation_service.py
from dataclasses import dataclass, field
from typing import Dict, List, Any
from unittest import result
from decimal import Decimal
@dataclass
class ItemValidationResult:
    item_id: str
    status: str
    error_codes: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
@dataclass
class ValidationReport:
    total_items: int
    ok_count: int
    warning_count: int
    confirmed_count: int
    blocked_count: int

    blocked_items: List[ItemValidationResult]
    warning_items: List[ItemValidationResult]

    # 便于 API 层直接使用 item_id -> validation result
    item_results: Dict[str, ItemValidationResult]

from typing import List, Dict
from sqlalchemy.orm import Session

from app.models.file_record import FileRecord, ValidationStatus
from app.models.material_item import MaterialItem
from app.models.part_item import PartItem
from app.models.labor_item import LaborItem
from app.models.logistics_item import LogisticsItem
from app.db.enums import CostItemStatus
from app.services.audit_log_service import AuditLogService

class ValidationService:
    """
    ValidationService is the gatekeeper of cost calculation.

    Responsibilities:
    - Validate item-level integrity / consistency
    - Aggregate file-level validation_status
    - Produce ValidationReport for human correction
    """

    def __init__(
        self,
        db: Session,
        audit_log_service: AuditLogService,
    ):
        self.db = db
        self.audit_log_service = audit_log_service
    def _to_decimal(self,v) -> Decimal:
        return v if isinstance(v, Decimal) else Decimal(v or 0)

    def validate_file(self, file_record: FileRecord) -> ValidationReport:
        """
        Validate all items under a FileRecord and update:
        - Item.status
        - FileRecord.validation_status
        
        :param file_record: FileRecord to validate
        :type file_record: FileRecord
        :return: ValidationReport summarizing the results
        :rtype: ValidationReport
        """
        # 1. 拉取所有 items（按 file_type）
        items = self._load_items(file_record)
        # 为了处理bundle的情况，分开处理partitem 和 others
        part_items = [i for i in items if isinstance(i, PartItem)]
        other_items = [i for i in items if not isinstance(i, PartItem)]
        
        results: Dict[str, ItemValidationResult] = {}
        ok_count = warning_count = confirmed_count = blocked_count = 0

        # 2. Item 级校验
        # 2.1 先处理 other_items
        for item in other_items:
            result = self._validate_item(item)
            results[item.id] = result#self._validate_item(item)返回的是item的ItemValidationResult对象

            # 写入 Item.status（系统行为）
            old_status = item.status
            if result.status != old_status.value:
                item.status = CostItemStatus[result.status]#根据ItemValidationResult的status更新item.status，用CostItemStatus[]转换
                # 记录审计日志
                self.audit_log_service.record_system_update(
                    project_id=file_record.project_id,
                    entity_type=item.__class__.__name__,
                    entity_id=item.id,
                    changed_attribute="status",
                    before_value=old_status.value if old_status else None,#注意一下这里的赋值
                    after_value=result.status,#注意一下这里的赋值
                )
            # 统计结果
            if result.status == "ok":
                ok_count += 1
            elif result.status == "warning":
                warning_count += 1
            elif result.status == 'confirmed':
                confirmed_count += 1    
            else:
                blocked_count += 1
            
        # 2.2 再处理 part_items（bundle 特例）
        part_results = self._validate_part_items_with_bundle(part_items)
        #将结果写入results                                                 
        for item_id, result in part_results.items():
            results[item_id] = result
        #遍历part_items,更新status
        for item in part_items:
            #获取从属于该item的校验结果
            result = results[item.id]
            # 写入 Item.status（系统行为）
            old_status = item.status
            if result.status != old_status.value:
                item.status = CostItemStatus[result.status]#根据ItemValidationResult的status更新item.status，用CostItemStatus[]转换
                # 记录审计日志
                self.audit_log_service.record_system_update(
                    project_id=file_record.project_id,
                    entity_type=item.__class__.__name__,
                    entity_id=item.id,
                    changed_attribute="status",
                    before_value=old_status.value if old_status else None,#注意一下这里的赋值
                    after_value=result.status,#注意一下这里的赋值
                )
            # 统计结果
            if result.status == "ok":
                ok_count += 1
            elif result.status == "warning":
                warning_count += 1
            elif result.status == 'confirmed':
                confirmed_count += 1
            else:
                blocked_count += 1
                    #self._validate_item(item)返回的是item的ItemValidationResult对象

        # 3. 聚合 FileRecord.validation_status
        old_file_status = file_record.validation_status
        new_file_status = self._aggregate_file_status(list(results.values()))#聚合file_record下所有item的校验结果，得到新的file_record.validation_status
        #写入 FileRecord.validation_status（系统行为）
        if new_file_status != old_file_status:
            file_record.validation_status = new_file_status
            # 记录审计日志
            self.audit_log_service.record_system_update(
                project_id=file_record.project_id,
                entity_type="FileRecord",
                entity_id=file_record.id,
                changed_attribute="validation_status",
                before_value=old_file_status.value,
                after_value=new_file_status.value,
            )

        # 4. 生成报告
        blocked_items = [
            r for r in results.values() if r.status == "blocked"
        ]
        warning_items = [
            r for r in results.values() if r.status == "warning"
        ]

        #5. 保存变动
        self.db.flush()
        
        return ValidationReport(
            total_items=len(items),
            ok_count=ok_count,
            confirmed_count=confirmed_count,
            warning_count=warning_count,
            blocked_count=blocked_count,
            blocked_items=blocked_items,
            warning_items=warning_items,
            item_results=results,
        )
    def _load_items(self, file_record: FileRecord) -> List[Any]:
        """
        Load items belonging to a file_record.
        :param file_record: FileRecord whose items to load
        :type file_record: FileRecord
        :return: List of items (MaterialItem, PartItem, LaborItem, LogisticsItem
        """
        file_type = file_record.file_type.name

        # 不生成item,不参与 validate
        if file_type.endswith("_plan"):
            return []
        
        if file_type.startswith("material"):
            return (
                self.db.query(MaterialItem)
                .filter(MaterialItem.source_file_id == file_record.id)
                .all()
            )
        if file_type.startswith("part"):
            return (
                self.db.query(PartItem)
                .filter(PartItem.source_file_id == file_record.id)
                .all()
            )
        if file_type.startswith("labor"):
            return (
                self.db.query(LaborItem)
                .filter(LaborItem.source_file_id == file_record.id)
                .all()
            )
        if file_type.startswith("logistics"):
            return (
                self.db.query(LogisticsItem)
                .filter(LogisticsItem.source_file_id == file_record.id)
                .all()
            )
        if file_type.startswith("manual"):
            return (
                self.db.query(LogisticsItem)
                .filter(LogisticsItem.source_file_id == file_record.id)
                .all()
            )
        return []
    
    def _validate_item(self, item) -> ItemValidationResult:
        '''
        Validate a single item and return ItemValidationResult.
        
        :param item: Item to validate (MaterialItem, PartItem, LaborItem, LogisticsItem)
        :type item: Any
        :return:  ItemValidationResult
        :rtype: ItemValidationResult
        '''
        if isinstance(item, MaterialItem):
            return self._validate_material_item(item)
        if isinstance(item, PartItem):
            return self._validate_single_part_item(item)
        if isinstance(item, LaborItem):
            return self._validate_labor_item(item)
        if isinstance(item, LogisticsItem):
            return self._validate_logistics_item(item)

        # 未知类型，标记为 blocked
        return ItemValidationResult(
            item_id=item.id,
            status="blocked",
            error_codes=["UNKNOWN_ITEM"],
            messages=["Unknown item type"],
        )
        
    def _validate_material_item(self, item: MaterialItem) -> ItemValidationResult:
        '''
        Validate a MaterialItem and return ItemValidationResult.
        
        :param item:  MaterialItem to validate
        :type item: MaterialItem
        :return:  ItemValidationResult
        :rtype: ItemValidationResult
        '''
        attribute_map = {"weight_kg":"参考重量（kg）", "unit_price":"单价", "subtotal":"小计"}
        if item.status == CostItemStatus.confirmed:
            return ItemValidationResult(
                item_id=item.id,
                status="confirmed",
                messages=["异常已由人工确认。"],
            )
        result = ItemValidationResult(item_id=item.id, status="ok")#默认状态为 ok

        # 1. 完整性（兜底路径）
        has_system = item.weight_kg is not None and item.unit_price is not None
        has_manual = item.subtotal is not None

        if not has_system and not has_manual:
            result.status = "blocked"
            result.error_codes.append("MISSING_ALL")
            result.messages.append("【参考重量（kg），单价，小计】部分缺失，请补全。")
            return result

        if not has_system and has_manual:
            result.status = "warning"
            result.error_codes.append("MISSING_SYSTEM")
            result.messages.append("【参考重量（kg），单价】部分缺失，请补全。")

        # 2. 非负性
        for name in ["quantity","weight_kg", "unit_price", "subtotal"]:
            val = getattr(item, name, None)
            #先判存在性
            if val is None:
                continue
            val = self._to_decimal(val)
            if val < Decimal('0'):
                result.status = "blocked"#存在负数-> blocked
                result.error_codes.append("NEGATIVE_VALUE")
                result.messages.append(f"{attribute_map[name]} 为负数，请修改。")
                return result

        # 3. 数量关系（只对 ok）
        if result.status == "ok" and has_system and has_manual:
            weight_kg = self._to_decimal(item.weight_kg)
            unit_price = self._to_decimal(item.unit_price)
            subtotal = self._to_decimal(item.subtotal)
            expected = weight_kg * unit_price * Decimal("0.001")
            if abs(expected - subtotal) > 1:
                result.status = "blocked"
                result.error_codes.append("RULE_INCONSISTENT")
                result.messages.append(
                    "数量关系异常，单价默认每吨，请确保【小计=参考重量（kg）*单价*0.001】。"
                )

        return result
    
    def _validate_single_part_item(self, item: PartItem) -> ItemValidationResult:
        '''
        Validate a PartItem and return ItemValidationResult.
    
        :param item: PartItem to validate
        :type item: PartItem
        :return: ItemValidationResult
        :rtype: ItemValidationResult
        '''
        attribute_map = {"quantity":"数量", "unit_price":"单价", "subtotal":"小计"}
        if item.status == CostItemStatus.confirmed:
            return ItemValidationResult(
                item_id=item.id,
                status="confirmed",
                messages=["异常已由人工确认。"],
            )
        result = ItemValidationResult(item_id=item.id, status="ok")#先默认为ok

        has_system = item.quantity is not None and item.unit_price is not None
        has_manual = item.subtotal is not None
        #完整性校验
        if not has_system and not has_manual:
            result.status = "blocked"
            result.error_codes.append("MISSING_ALL")
            result.messages.append("【数量，单价，小计】存在部分缺失，请补全。")
            return result

        if not has_system and has_manual:
            result.status = "warning"
            result.error_codes.append("MISSING_SYSTEM")
            result.messages.append("【数量，单价】存在部分缺失，请补全。")
        #非负性校验
        for name in ["quantity", "unit_price", "subtotal"]:
            val = getattr(item, name, None)
            #先判存在性
            if val is None:
                continue
            #再判非负性
            val = self._to_decimal(val)
            if  val < Decimal('0'):
                result.status = "blocked"#存在负数-> blocked
                result.error_codes.append("NEGATIVE_VALUE")
                result.messages.append(f"【{attribute_map[name]}】 为负数，请修改。")
                return result
        #数量关系校验（只对 ok）
        if result.status == "ok" and has_system and has_manual:
            quantity = self._to_decimal(item.quantity)
            unit_price = self._to_decimal(item.unit_price)
            subtotal = self._to_decimal(item.subtotal)
            expected = quantity * unit_price
            if abs(expected - subtotal) > 1:
                result.status = "blocked"
                result.error_codes.append("RULE_INCONSISTENT")
                result.messages.append("数量关系异常，请确保【小计 = 数量*单价】。")

        return result
    def _validate_part_bundle(
        self,
        bundle_items: list[PartItem],
    ) -> dict[str, ItemValidationResult]:
        """
        Bundle validation rules (final version):
        - Exactly one anchor item with non-zero subtotal
        - Anchor selection priority:
            1) system + manual
            2) system only
            3) manual only
        - Non-anchor items if have subtotal == 0, status = warning
        :param bundle_items: List of PartItems in the same bundle
        :type bundle_items: list[PartItem]
        return dict[str, ItemValidationResult] which maps item_id to validation result of each item in the bundle
        """
        attribute_map = {"quantity":"数量", "unit_price":"单位", "subtotal":"小计"}
        def is_effective_value(x, eps=1e-8):
            if x is None:
                return False
            return abs(float(x)) > eps
        results: dict[str, ItemValidationResult] = {}

        # 1️完整性分类
        system_candidates = []#system-only candidates
        manual_candidates = []#manual-only candidates
        full_candidates = []#system + manual candidates

        for item in bundle_items:
            has_system = item.quantity is not None and item.unit_price is not None
            has_manual = item.subtotal is not None

            if has_system and has_manual:
                full_candidates.append(item)
            elif has_system:
                system_candidates.append(item)
            elif has_manual:
                manual_candidates.append(item)

        # 2️选择 anchor，默认选择第一个符合条件的
        anchor: PartItem | None = None
        if full_candidates:
            anchor = full_candidates[0]
        elif system_candidates:
            anchor = system_candidates[0]
        elif manual_candidates:
            anchor = manual_candidates[0]
        # 3️全部缺失 → 全 blocked
        if anchor is None:
            for item in bundle_items:
                results[item.id] = ItemValidationResult(
                    item_id=item.id,
                    status="blocked",
                    error_codes=["MISSING_ALL"],
                    messages=["不存在合格的锚点行, 【数量，单价，小计】部分缺失，请补全。"],
                )
            return results

        # 4️⃣ 非锚点行：subtotal若不为0，则 warning，需要confirm分摊
        for item in bundle_items:  
            if item.id == anchor.id:
                continue
            
            # 1️⃣ 非负性校验（最高优先级）
            for name in ["quantity", "unit_price", "subtotal"]:
                val = getattr(item, name, None)
                #先判存在
                if val is not None:
                    continue
                val = self._to_decimal(val)
                if val < Decimal("0"):
                    results[item.id] = ItemValidationResult(
                        item_id=item.id,
                        status="blocked",
                        error_codes=["NEGATIVE_VALUE"],
                        messages=[f"【{attribute_map[name]}】为负数，请修改。"],
                    )
                    break
            else:
                # 2️⃣ bundle 规则,subtal校验
                if is_effective_value(item.subtotal):
                    # V0.1：不允许多锚点
                    results[item.id] = ItemValidationResult(
                        item_id=item.id,
                        status="blocked",
                        error_codes=["BUNDLE_MULTI_ANCHOR"],
                        messages=[
                            "并购项中多行存在非0小计，V0.1暂不允许分摊，请修改【小计】至0。"
                        ],
                    )
                else:
                    #等于0或None，is_calculable= False，status = ok. 不纳入cost计算，但保留在系统中
                    item.is_calculable = False
                    results[item.id] = ItemValidationResult(
                        item_id=item.id,
                        status="ok",
                        messages=["非锚点行，不纳入成本计算。"],
                    )
            


        # 5️⃣ 校验 anchor 本身（复用单行逻辑）
        anchor_result = self._validate_single_part_item(anchor)

        results[anchor.id] = anchor_result
        return results

    
    def _validate_part_items_with_bundle(
        self,
        items: list[PartItem],
    ) -> dict[str, ItemValidationResult]:
        """
        Validate PartItems with bundle awareness.
        :param items: List of PartItems to validate
        :type items: list[PartItem]
        """
        results: dict[str, ItemValidationResult] = {}

        # 按 bundle_key 分组（None 也作为一个独立组）
        bundle_map: dict[int | None, list[PartItem]] = {}
        for item in items:
            bundle_map.setdefault(item.bundle_key, []).append(item)

        for bundle_key, bundle_items in bundle_map.items():
            # bundle_key== None, 单行 bundle，直接走普通校验
            if bundle_key is None or len(bundle_items) == 1:
                for item in bundle_items:
                    results[item.id] = self._validate_single_part_item(item)
                continue
            else:
                # 多行 bundle,走bundle校验,直接把同一个bundle的items传进去
                bundle_results = self._validate_part_bundle(bundle_items)
                results.update(bundle_results)

        return results
    
    def _validate_labor_item(self, item: LaborItem) -> ItemValidationResult:
        '''
        validate a LaborItem and return ItemValidationResult.

        :param item: LaborItem to validate
        :type item: LaborItem
        :return:  ItemValidationResult
        :rtype: ItemValidationResult
        '''
        attribute_map = {
            "work_quantity":"数量",
            "unit_price":"单价",
            "extra_subsidies":"补助",
            "ton_bonus":"吨位奖金",
            "subtotal":"小计"
            }
        if item.status == CostItemStatus.confirmed:
            return ItemValidationResult(
                item_id=item.id,
                status="confirmed",
                messages=["异常已由人工确认。"],
            )
        result = ItemValidationResult(item_id=item.id, status="ok")

        has_system = (
            item.work_quantity is not None
            and item.unit is not None
            and item.unit_price is not None
            and item.extra_subsidies is not None
            and item.ton_bonus is not None
        )
        has_manual = item.subtotal is not None

        # 完整性
        if not has_system and not has_manual:
            result.status = "blocked"
            result.error_codes.append("MISSING_ALL")
            result.messages.append("【数量，单位，单价，补助，吨位奖金，小计】中部分属性存在缺失，请补全。")
            return result

        if not has_system and has_manual:
            result.status = "warning"
            result.error_codes.append("MISSING_SYSTEM")
            result.messages.append("【数量，单位，单价，补助，吨位奖金】中部分属性存在缺失，请补全。")

        # 非负性
        for name in [
            "work_quantity",
            "unit_price",
            "extra_subsidies",
            "ton_bonus",
            "subtotal",
        ]:
            val = getattr(item, name, None)
            if val is None:
                continue
            val = self._to_decimal(val)
            if val < Decimal("0"):
                result.status = "blocked"
                result.error_codes.append("NEGATIVE_VALUE")
                result.messages.append(f"【{attribute_map[name]}】为负数，请修改。")
                return result

        # 数量关系（仅 ok）
        if result.status == "ok" and has_system and has_manual:
            work_quantity = self._to_decimal(item.work_quantity)
            unit_price = self._to_decimal(item.unit_price)
            subtotal = self._to_decimal(item.subtotal)
            extra_subsidies = self._to_decimal(item.extra_subsidies)
            ton_bonus = self._to_decimal(item.ton_bonus)
            expected_processing = work_quantity * unit_price
            #ton_bonus = (
            #    Decimal(item.work_quantity) * Decimal("5")
            #    if item.unit == "吨"
            #    else Decimal(item.work_quantity) * Decimal("0.005"))
            expected_total = (
                expected_processing
                + extra_subsidies
                + ton_bonus
            )

            if abs(expected_total - subtotal) > 1:
                result.status = "blocked"
                result.error_codes.append("RULE_INCONSISTENT")
                result.messages.append(
                    "数量关系异常，请确保：【小计 = 数量 * 单价 + 补助 + 吨位奖金】。"
                )

        return result

    def _validate_logistics_item(self, item: LogisticsItem) -> ItemValidationResult:
        '''
        Validate a LogisticsItem and return ItemValidationResult.
        
        :param item: LogisticsItem to validate
        :type item: LogisticsItem
        :return:  ItemValidationResult
        :rtype: ItemValidationResult
        '''
        if item.status == CostItemStatus.confirmed:
            return ItemValidationResult(
                item_id=item.id,
                status="confirmed",
                messages=["异常已由人工确认"],
            )
        result = ItemValidationResult(item_id=item.id, status="ok")

        # 完整性
        if item.subtotal is None:
            result.status = 'blocked'
            result.error_codes.append("MISSING_SUBTOTAL")
            result.messages.append("【小计】缺失，请填补。")
            return result

        # 非负性
        if self._to_decimal(item.subtotal) < Decimal("0"):
            result.status = 'blocked'
            result.error_codes.append("NEGATIVE_VALUE")
            result.messages.append("【小计】为负数，请修改。")
            return result
        return result

    def _aggregate_file_status(
        self, results: List[ItemValidationResult]
    ) -> ValidationStatus:
        '''
        Aggregate FileRecord.validation_status from item-level results.
    
        :param results:  List of ItemValidationResult
        :type results: List[ItemValidationResult]
        :return: Aggregated ValidationStatus
        :rtype: ValidationStatus
        ''' 
        statuses = {r.status for r in results}

        if "blocked" in statuses:
            return ValidationStatus.blocked
        if "warning" in statuses:
            return ValidationStatus.warning
        if "confirmed" in statuses:
            return ValidationStatus.confirmed
        return ValidationStatus.ok


