# 统一异常处理

项目所有对外业务异常统一使用 `backend/src/exceptions.py` 中的 `BusinessError`。异常只能通过 `BusinessErrorCode` 枚举创建，公开 code、message 和 retryable 不允许由调用方自由传入。

```python
raise BusinessError(BusinessErrorCode.TASK_NOT_FOUND)
```

包装底层异常时使用异常链，原始信息只进入服务端日志：

```python
try:
    await provider.call()
except Exception as exc:
    raise BusinessError(BusinessErrorCode.STORAGE_FAILED) from exc
```

禁止将 `str(exc)` 写入 API、Agent 消息、文档错误或 task `result_data`。

## 错误码分区

| 范围 | 模块 |
|------|------|
| 1xxxx | Workspace、账号、邀请码 |
| 2xxxx | 文档 |
| 3xxxx | PPT、口播稿和产出任务 |
| 4xxxx | PPT 风格 |
| 5xxxx | 文件和存储 |
| 6xxxx | 消息和分享 |
| 7xxxx | Agent、模型和工具 |
| 8xxxx | PPT 风格提取 |
| 9xxxx | TTS 和 Vision |

`BusinessError.to_dict()` 是统一序列化入口：

```json
{
  "code": 80004,
  "message": "模型服务额度不足，请恢复额度后继续执行任务。",
  "type": "style_extraction_model_quota",
  "retryable": true,
  "stage": "style_merge_template"
}
```

## 传输方式

- REST：全局 handler 返回 `{data, code, message, error}`，保留原有 envelope 兼容。
- Agent：middleware 把同一结构写入 `additional_kwargs.rumi_error`，消息正文使用安全 message。
- 后台任务：将同一结构写入 `result_data.error` 或 `tts_error`。
- 文档：数据库 `error_message` 继续保存字符串，但只能保存枚举的安全 message。

任务 API sanitizer 同时兼容旧字符串错误。旧 provider 原文不会透传；可识别的额度和认证错误会映射到对应枚举，其余返回模块通用错误。

前端通过 `BusinessErrorPayload` 和 `getBusinessErrorMessage()` 展示错误，不解析 provider 原始英文异常。
