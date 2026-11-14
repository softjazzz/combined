"""任务冻结合同的受控拒绝，保持 ValueError 兼容但不靠异常正文分类。"""


class TaskExecutionContractError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)
