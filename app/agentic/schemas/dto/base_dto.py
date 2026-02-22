from pydantic import BaseModel

class BaseDTO(BaseModel):
    class Config:
        orm_mode = True

    @classmethod#强制所有 DTO 显式定义映射
    def from_orm_model(cls, orm_obj):
        """
        子类应 override
        """
        raise NotImplementedError(
            f"{cls.__name__}.from_orm_model() must be implemented"
        )