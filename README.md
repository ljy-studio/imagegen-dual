# ImageGen Dual

面向 Codex、Claude Code 及兼容 Skills 的图片生成与编辑 Skill。

它把图片模型选择、额度来源确认、网关发现、请求执行、结果下载和失败诊断收进一条可审计的工作流。图片模型通过独立 HTTP API 调用，不会切换宿主 Agent 的主对话模型，也不会偷偷改用宿主内置图片工具。

[![Tests](https://github.com/ljy-studio/imagegen-dual/actions/workflows/test.yml/badge.svg)](https://github.com/ljy-studio/imagegen-dual/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.2.0-111827)](version.json)

## 适合什么场景

- 在 Agent 中生成图片或基于本轮图片执行 edit。
- 同时管理多个图片 API 来源、网关或额度账户。
- 在真实请求前先确认模型、额度来源和请求上限。
- 需要失败可解释、结果未知时不自动重发的图片工作流。
- 希望通过 Git 更新，让已安装的 Skill 保持可回退。

## 快速安装

需要 Python 3.11+ 和 Git。

```bash
git clone https://github.com/ljy-studio/imagegen-dual.git ~/.agents/skills/imagegen-dual
cd ~/.agents/skills/imagegen-dual
python scripts/install.py
```

安装脚本会安装依赖、运行离线测试，并写入 `~/.imagegen-dual/install.json`。它不会保存 API Key。

## 快速使用

安装后，Agent 会按以下顺序工作：

1. 检查更新和本地安装状态。
2. 发现可用账户或读取显式配置。
3. 让用户选择额度来源和图片模型。
4. 通过 `scripts/client.py` 执行 generate 或 edit。
5. 只展示本轮实际返回并成功解码的图片。

也可以直接运行客户端：

```bash
python scripts/client.py generate --job path/to/job.json
python scripts/client.py edit --job path/to/edit-job.json
```

任务格式、模型路由和 edit 输入要求见 [`references/API调用.md`](references/API调用.md)。

## 设计边界

| 规则 | 行为 |
| --- | --- |
| 模型选择 | 每次请求显式传入，不按宿主当前激活项代选 |
| 额度与测试 | 普通请求不自动扩大为付费测试或并发验收 |
| 失败处理 | 结果未知时停止，不自动重发 |
| 配置安全 | 默认只读发现配置，不读取 OAuth，不输出密钥 |
| 图片展示 | 只展示本轮实际下载并解码成功的文件 |
| 工具兼容 | 按宿主、客户端、模型和网关组合判断，不按模型名跨客户端推断 |

真实生图、edit 和并发验收可能消耗额度。首次初始化和付费验收流程见 [`references/首次安装验收.md`](references/首次安装验收.md)。

## 自动更新

Skill 入口会运行：

```bash
python scripts/update.py --auto
```

更新前会在临时检出中运行测试，成功后才快进合并；失败会保留当前版本。更新源和分支位于 [`release.json`](release.json)，本地状态、配置、凭证、验收记录和任务产物保存在 `~/.imagegen-dual/` 或任务目录，不进入仓库。

## 仓库结构

```text
SKILL.md                  Agent 入口与核心约束
scripts/install.py        安装与首次初始化
scripts/update.py         自动更新与回退保护
scripts/client.py         图片 API 客户端
scripts/ask_capability.py 提问工具兼容性探测
references/               按需读取的操作、诊断与兼容性文档
capabilities.json         已知模型能力边界
version.json              Skill 版本与配置 schema
```

## 开发与验证

```bash
python -m pip install -r requirements.txt
python -B scripts/offline_test.py
python -B scripts/release_test.py
```

GitHub Actions 会在 `main` 推送和 Pull Request 中自动执行同一组检查。

## 文档入口

- [`SKILL.md`](SKILL.md)：给 Agent 读取的入口文件。
- [`references/首次安装验收.md`](references/首次安装验收.md)：初始化、只读检查和付费验收。
- [`references/提问与选择.md`](references/提问与选择.md)：额度来源、模型选择和工具降级。
- [`references/API调用.md`](references/API调用.md)：generate、edit、任务格式和结果处理。
- [`references/凭证与网关.md`](references/凭证与网关.md)：账户发现、网关和环境变量。
- [`references/故障恢复与诊断.md`](references/故障恢复与诊断.md)：请求失败、结果未知和恢复边界。
- [`references/维护与发布.md`](references/维护与发布.md)：版本、更新、回退和发布检查。

## 当前状态

版本 `0.2.0`。离线测试、本地 Git 更新测试和发布检查已完成；真实生图、edit、公网首次安装及全部宿主组合仍需按实际账户和客户端分别验收。
