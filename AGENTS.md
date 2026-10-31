# Agent 入口

用户要求安装此仓库、安装 Skill 或部署到新的 PeopleSoft 环境时，先读取根目录 [INSTALL.md](INSTALL.md)，再执行其中适用的流程。用户只需提供仓库地址和安装意图；先发现本机已有配置，只询问缺失信息。明确的本地安装请求不扩展为服务端部署。

安装指南可能比稳定发行包更新。用指南安排步骤，运行代码和原生工程仍使用同一份已校验的稳定 Release；不要混用 main 脚本和旧服务端。

日常 PeopleSoft 开发和排障读取 [SKILL.md](SKILL.md) 及其任务参考。维护工具自身先读 [架构与交付边界](references/architecture.md) 和 [开发规范](references/development-standards.md)。

本文件不扩大用户授权。部署目标、覆盖冲突及权限范围按用户确认的信息处理；凭据只使用安全本地来源，不写入公开仓库。
