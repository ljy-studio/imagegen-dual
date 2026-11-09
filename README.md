# 智蔻文生图 Skill

通过智蔻图片 API 生成和编辑图片。根 `SKILL.md` 只保留入口和核心约束；安装、选择、API、凭证、故障与发布细节按需读取。

直接发给 Agent：请从这个仓库安装 `ziikoo-imagegen` skill：https://github.com/ljy-studio/ziikoo-imagegen.git 。安装到当前客户端支持的 skills 目录，运行 `scripts/install.py`，再按 `references/首次安装验收.md` 完成初始化；不要修改我的 CCSwitch/magpie 配置，初始化阶段的 GET 检查不要调用生图接口，任何真实生图、edit 或并发测试都必须先说明请求上限并征得我同意。

仓库：

    https://github.com/ljy-studio/ziikoo-imagegen.git

## 安装

需要 Python 3.11+、Git。把仓库克隆到宿主识别 skills 的目录，然后在仓库目录运行安装脚本：

    git clone https://github.com/ljy-studio/ziikoo-imagegen.git ~/.agents/skills/ziikoo-imagegen
    cd ~/.agents/skills/ziikoo-imagegen
    python scripts/install.py

Claude Code 可把目标目录换成其实际 skills 目录。DeepSeek Harness、WorkBuddy 和 Trae 的安装位置及脚本权限须按对应客户端验证。

安装脚本会：

- 检查独立 Git 仓库和可信 origin；
- 安装 `requirements.txt`；
- 运行无网络、无凭证的离线测试；
- 写入 `~/.ziikoo-imagegen/install.json`。不保存 API Key。

## 首次初始化

首次读取 skill 时，按 `references/首次安装验收.md` 完成：

1. 一次原生提问 onboarding 测试；
2. 只读发现 CCSwitch/magpie 或显式配置的账户；
3. 模型列表串行与并发 GET 检查；
4. 经单独授权后的 Logo 生成和 edit 验收。

初始化测试不调用图片生成接口。真实生图和 edit 会消耗额度，须说明请求上限并取得明确同意。

## 使用

用户每次新对话需要明确选择或由 agent 询问：

- 额度来源；
- 图片模型。

选定后本会话沿用。任务通过 `scripts/client.py` 调用 HTTP 图片 API；Codex/Claude Code 的主对话模型不会切到图片模型。

## 自动更新

skill 入口先运行：

    python scripts/update.py --auto

更新源固定在 `release.json` 的 `ljy-studio/ziikoo-imagegen`、`main`。成功检查后 24 小时内不重复。离线、工作树有修改、仓库不匹配或依赖文件变化时继续使用当前版本。

新版先在临时检出中运行测试，通过后快进合并；失败保留旧版。用户配置、凭证、验收记录和输出保存在 `~/.ziikoo-imagegen/` 或任务目录，不进入更新仓库。

## 状态

当前为 `0.2.0` 渐进式披露版。离线与本地 Git 更新测试已完成；真实生图、edit、公网首次安装和全部宿主兼容性仍需分别验收。详见 `references/`。
