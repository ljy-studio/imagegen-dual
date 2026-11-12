# Agent 客户端模型兼容性参考

核查日期：2026-11-09。产品版本和模型目录变化快；本表说明配置和工具边界，不替代安装后的逐项实测。

## 结论

“模型能完成文本对话”“终端接受自定义模型配置”“模型能正确调用宿主工具”是三种不同能力。模型可在某个客户端聊天，不代表它能调用该客户端的原生提问、文件或终端工具；也不代表它支持图片生成。

| 客户端 | 模型接入方式 | 原生提问能力 | 对 imagegen-dual 的影响 |
|---|---|---|---|
| Codex | 原生 OpenAI 模型支持最完整；配置层允许自定义 provider、base URL 和 API key，Codex 自身也实现同步和异步提问工具 | `request_user_input` 受协作模式限制；`request_user_input_async` 是否真正调用成功取决于模型、网关和当前会话工具适配 | 按当前组合探测；Sol 实测可用，Opus 5.5 与 DeepSeek 在 Codex 实测返回 `unsupported call` 时改用编号文本 |
| Claude Code | 原生支持 Claude 别名和完整模型 ID；可通过 `ANTHROPIC_BASE_URL` 或网关接入自定义模型名 | 原生 `AskUserQuestion` 工具；Claude Code + DeepSeek 已实测可用 | 优先原生选择；第三方网关仍需验证工具调用，不能按模型名推断 |
| DeepSeek Harness | 默认 DeepSeek provider；插件化架构可通过自定义组合挂载其他 provider/model 目录 | 官方提供 provider-neutral 的 `ask_user_question` 和用户问题接口 | 与“Codex 中选择 DeepSeek”是两个不同宿主；不能把 Codex 的限制归到 DSH |
| WorkBuddy | 支持内置模型和 OpenAI Chat Completions 兼容自定义模型；本地配置声明工具调用、图片输入等能力 | 提问和任务交互由具体客户端/技能决定，不统一等同于 Codex 或 Claude 的工具名 | 模型必须启用工具调用；图片输入不等于图片生成，仍由 imagegen-dual 调图片 API |
| Trae | IDE 自定义模型支持 OpenAI Chat Completions 和 Anthropic Messages；可设模型 ID、端点、工具轮数、图片输入和推理参数 | 具体提问呈现和工具名按 Trae 当前版本验证 | 连接测试通过只说明 API 可访问，须再测 ask、脚本执行和图片显示 |

## 关键边界

- Codex 的异步提问工具在核心代码中定义为“立即返回、答复异步进入会话”。工具被定义不保证某一 provider 接受并返回该工具调用。社区也有 Default 模式同步工具不可用及自定义 provider 工具失败的记录。
- Codex 模型目录端点并不等同于普通 OpenAI `/v1/models`；Codex 的模型发现和工具回路有自身协议要求。应验证完整推理回合，而不只看能否列模。
- Claude Code 的 `ANTHROPIC_BASE_URL` 只改变请求去向，不保证第三方网关完整实现 Anthropic Messages 的工具调用语义。
- DeepSeek Harness 已有 `ASK_ABORTED`、问题卡片未渲染和远端连接丢失等社区报告。遇到时必须检查 DSH 版本、插件组合和 UI 连接方式，不能据此认定 DeepSeek 模型本身不支持 ask。
- WorkBuddy 自定义模型常用 `/v1/chat/completions`；模型要支持函数调用，且配置中的工具能力声明必须准确。官方也明确图片输入理解不同于图片生成。
- Trae 接入自定义模型时会做连接验证；连接成功只证明鉴权、地址和模型 ID 可用。工具轮数和模型系列参数仍需通过实际 agent 任务验收。

## 已实测与待测

本机已实测：

- Codex + GPT-6.1 Sol：`request_user_input_async` 可显示并收到点击回答。
- Codex + Opus 5.5：同步提问工具受 Default 模式限制，异步工具返回 `unsupported call`。
- Codex + DeepSeek：异步提问返回 `unsupported call`；改用编号文本。
- Claude Code + DeepSeek：原生 ask 可用。

仍需逐项实测：Claude Code + Opus 的当前版本、DeepSeek Harness 的真实问卡、WorkBuddy 和 Trae 的 skill 发现/脚本/ask/图片展示。更换网关、客户端版本或模型接入方式后重新记录。

## 日常交互规则（0.3 更新）

历史结果仅供排错。依当前回合工具处理必要问题，失败用文字。首次安装不发测试问卡；不用空参数或非法参数探测。用户专门要求诊断时才记录 ask_capability。日常选择与授权见 [提问与选择](提问与选择.md)。

## 来源

- [Codex 异步提问工具定义](https://github.com/openai/codex/blob/main/codex-rs/prompts/src/model_messages.rs)
- [Codex Default 模式提问工具问题 #24750](https://github.com/openai/codex/issues/24750)
- [Codex 自定义 provider 与 Responses 配置](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server)
- [Claude Code 模型配置](https://code.claude.com/docs/en/model-config)
- [Claude Code `AskUserQuestion` 工具行为](https://code.claude.com/docs/en/tools-reference)
- [DeepSeek Harness 用户问题子系统](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/user-questions.md)
- [DeepSeek Harness 自定义 provider/model 说明](https://github.com/deepseek-ai/deepseek-harness/blob/master/python/sdk/README.md)
- [DeepSeek Harness 问卡未显示的社区报告](https://github.com/deepseek-ai/deepseek-harness/discussions/11721)
- [WorkBuddy 模型配置](https://www.workbuddy.ai/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Model-Configuration)
- [WorkBuddy 接入 DeepSeek](https://api-docs.deepseek.com/quick_start/agent_integrations/workbuddy/)
- [TRAE 自定义模型](https://docs.trae.cn/ide_custom-models)
- [Trae Agent CLI 模型参数](https://github.com/bytedance/trae-agent/blob/main/trae_agent/cli.py)
