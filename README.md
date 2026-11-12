# imagegen dual

面向 Agent 的图片生成与编辑 Skill。独立 API 客户端、显式模型与账户、结果验证、可回退更新。

[![Tests](https://github.com/ljy-studio/imagegen-dual/actions/workflows/test.yml/badge.svg)](https://github.com/ljy-studio/imagegen-dual/actions/workflows/test.yml)
[![Version](https://img.shields.io/badge/version-0.3.0--rc.3-111827)](version.json)

## 一句话安装

从这个仓库安装 imagegen dual skill：https://github.com/ljy-studio/imagegen-dual.git 。

Agent 收到安装请求后，先阅读 [INSTALL.md](INSTALL.md)，按其中流程完成清理、安装、离线验证和结果报告。用户无需复制额外操作细则。

安装验收必须包含清理记录。仅复制文件或通过离线测试，不代表完成安装。当前测试请使用 main 分支源码；旧版 Release 包不包含本轮清理校验修复。

## 安装方式

| 环境 | 方式 |
| --- | --- |
| Windows x64，无 Python/Git | 使用便携 ZIP，已包含运行时与依赖 |
| GitHub 不可访问 | 维护者经可信网盘、内网或文件传输提供同一便携包与 SHA256 |
| 已有 Python 3.11+ | 在 skill 专属虚拟环境安装源码 |
| 无 Git，但有 Python | 源码 ZIP，安装时增加 --archive |

先解压至暂存目录、核对 SHA256 并自检；执行 [安装前清理](references/安装前清理.md) 备份迁移旧版及同类 API 生图专用 skill，精确清除对应 Agent.md / AGENTS.md 约束。随后放入唯一的 imagegen-dual 目录并初始化。显示名统一为 imagegen dual。

```powershell
./imagegen-dual.exe self-test
./imagegen-dual.exe install --migration-backup <清理备份目录>
```

源码（Windows）：

```powershell
python -m venv .venv
./.venv/Scripts/python.exe scripts/install.py --migration-backup <清理备份目录>
```

macOS/Linux 使用 python3 和 .venv/bin/python，目前没有这两个平台的免依赖包。源码 ZIP 仍需 Python 和依赖。安装、自检可离线，实际生图仍需访问图片 API。当前没有部署国内镜像。完整流程见 [安装与离线分发](references/安装与离线分发.md)。

## 快速使用

用户已明确账户、模型和任务时直接执行；缺项合并询问，连续编辑沿用选择，不逐次问“是否开始”。安装不强制付费验收；迁移只清理已确认的旧专用工具及其约束，保留其他规则。

```powershell
./imagegen-dual.exe generate --job path/to/job.json
./imagegen-dual.exe edit --job path/to/edit-job.json
```

源码使用虚拟环境 Python + scripts/cli.py。任务必须显式包含 profile、model、prompt；编辑增加本地 image。默认 JSON images 数组及 data URL，明确支持文件上传的服务可显式使用 multipart。详见 [API调用](references/API调用.md)。

## 请求与授权边界

- 复用用户已有选择和明确项目偏好，不按软件激活项猜测收费来源。
- 用户请求本身授权约定范围内任务；额外测试、超预算或更换收费来源才补充确认。
- 结果未知时停止，不自动更换协议或重发；下载失败只恢复已有响应。
- 只展示本轮返回并完整解码的图片，不用历史图片代替。
- 旧专用工具迁出发现路径并留可恢复备份；本 skill 不声明覆盖项目通用规则。

## 更新

Git 源码可运行 scripts/cli.py update --auto：每安装目录一天最多一次检查，离线失败也退避。新版先测试再快进，保留本地修改。

便携包和源码 ZIP 使用验证新包、并排解压、自检后手动换包，保留旧版与 ~/.imagegen-dual 状态。

## 开发验证

```sh
python -B scripts/offline_test.py
python -B scripts/grey_test.py
python -B scripts/migration_test.py
python -B scripts/release_test.py
```

便携包由独立构建虚拟环境运行 scripts/package_release.py 生成，包含第三方许可证与 SHA256 清单。详见 [维护与发布](references/维护与发布.md)。

## 文档

- [SKILL.md](SKILL.md)：Agent 入口与范围。
- [提问与选择](references/提问与选择.md)：减少重复问题、复用授权。
- [凭证与网关](references/凭证与网关.md)：配置与只读发现。
- [首次安装验收](references/首次安装验收.md)：可选检查。
- [故障恢复与诊断](references/故障恢复与诊断.md)：错误记录与恢复。

## 当前状态

0.3.0-rc.3 为灰测修复候选。JSON edit 已按官方参考实现，两个 2.5 模型在实际网关上的兼容性仍需回测，不能用本地测试代替。Windows x64 是当前便携构建目标。
