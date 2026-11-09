# API 调用

## 生成

任务 JSON 至少包含：

    {
      "profile": "本会话选定来源的稳定ID",
      "model": "本会话选定模型完整ID",
      "prompt": "用户的生图要求"
    }

可选字段包括 `size`、`quality`、`output_dir`、`no_fallback`。不要在任务中写 API Key。

运行：

    python scripts/client.py generate --job <绝对路径>

客户端先以 `GET /v1/models` 获取实时模型和路由，再提交 `POST /v1/images/generations`。

## 编辑

编辑任务增加输入图片：

    {
      "profile": "本会话选定来源的稳定ID",
      "model": "本会话选定模型完整ID",
      "prompt": "编辑要求",
      "image": "输入图片绝对路径"
    }

运行：

    python scripts/client.py edit --job <绝对路径>

调用 multipart `POST /v1/images/edits`。原始图片保持不变，结果写入新的任务目录。真实兼容性以接口测试为准，不能由文生图成功推导 edit 成功。

## 路由

直连模式按 `api.gaoxin.net.cn`、`api-sh.gaoxin.net.cn` 顺序探测，最近成功端点缓存 10 分钟。缓存只影响顺序，模型列表仍实时获取。

仅在连接建立超时且同一模型存在于另一个已探测端点时切换。结果未知的 POST 不重发。429 不通过切换端点绕过。

## 成功展示

读取客户端返回的 `record.json`，确认状态为 `success` 且包含完整解码结果。使用宿主可用的图片查看器检查，再用绝对本地路径展示。

报告请求模型、响应模型（缺失写未知）、额度来源、端点、耗时和文件路径。不得根据图片外观推断底层模型。

`client.py models` 的 `image_models` 是实时列表与 `capabilities.json` 的交集。`unknown` 表示尚未验证，不表示支持。
