# create_namemapping.py
# 创建初始列名标准化映射脚本
from app.db.session import get_session
from app.services.name_normalization_service import NameNormalizationService
from app.services.audit_log_service import AuditLogService
from app.services.user_service import UserService
from app.db.enums import NameDomain
       
mapping_data = []         
def create_mapping():
    """创建初始列名标准化映射"""
    db = get_session()
    try:
        user_service = UserService(db)
        audit_log_service = AuditLogService(db)
        name_normalization_service = NameNormalizationService(db, audit_log_service)
        # 检查列名标准化映射是否已存在
        # 检查用户是否已存在
        existing_user = user_service.get_user_by_account("admin")
    
        for original_name, standard_name in mapping_data:
            name_normalization_service.create_mapping(domain=NameDomain.COLUMN,
                                                      raw_name=original_name, 
                                                      normalized_name=standard_name,
                                                      operator_id=existing_user.id if existing_user else None) 
            
        
        db.commit()
        print(f"✅ 名字映射创建成功!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 创建失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_mapping()

