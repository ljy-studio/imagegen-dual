# API 调用

<client> 为便携 exe 或专属虚拟环境 Python + scripts/cli.py。

## 生成

任务至少包含 profile（已确认来源 ID）、model（完整模型 ID）、prompt。可选 size、quality、output_dir、no_fallback，不得写密钥。运行 <client> generate --job <绝对路径>；GET /v1/models 后以 JSON POST /v1/images/generations。

## 编辑：默认 JSON

任务在生成字段基础上增加 image（输入图片绝对路径）和可选 edit_transport=json。运行 <client> edit --job <绝对路径>。

客户端验证 PNG/JPEG/WEBP 后，以 application/json POST /v1/images/edits。请求包含 model、prompt、n=1、size、quality，以及 images 数组，其元素为 image_url 字段，值为 data:image/png;base64,... 形式的完整 data URL。

不向 API 发送本地文件路径或裸 base64。data URL 最长 20,971,520 字符，超限在 POST 前报错，不自动压缩图片或切换协议。

## multipart 兼容模式

服务明确支持时设置 edit_transport=multipart，客户端以 data 传文本、files.image 传文件，Content-Type 和 boundary 由 HTTP 库共同生成，不能配 application/json 头。任务字段优先，其次 profile 配置，默认 json。

2026-11-12 对照 [OpenAI 官方 edit API](https://developers.openai.com/api/reference/resources/images/methods/edit)：当前参考页定义 JSON images[].image_url，支持 data URL，并列出两个 2.5 模型。第三方网关和 az/ 路由是否完整兼容仍需实际验收；multipart 仅保留为显式兼容选项。

invalid character '-' in numeric literal 与 multipart 边界被 JSON 解析的情况一致；也可能来自网关内部转换，单凭错误无法确认。record.json 保存请求路径和 Content-Type，不保存请求图片内容。被拒绝不自动换协议再发一次。

## 路由与结果

直连探测 api.gaoxin.net.cn 与 api-sh.gaoxin.net.cn；显式网关只访问网关。仅连接建立超时可按范围切换已探测端点；未知 POST 不重发，429 不绕过。原图保持不变，结果写新目录。success 且完整解码后展示；响应无模型就记录未知。capabilities 的 unknown 不代表支持。
