# GreyWind（灰风）AGENTS.md

> 完整项目规则见 `CLAUDE.md`。本文件补充所有代理在非 Claude Code 环境下必须遵守的编码与输出约束。

## 编码

**强制 UTF-8。**

- 所有文件读写必须使用 UTF-8。
- 所有终端输出、HTTP 请求体、日志、注释、生成文本、Review 评论都必须使用 UTF-8。
- 禁止输出或写入 `GBK`、`CP936`、`ANSI`、乱码文本或编码不明内容。
- 发现已有乱码时，不要继续追加污染内容；先修正编码，再继续修改。

## 输出要求

- 面向用户的回复必须是正常可读文本，不能出现 `????`、`鈥�`、`馃` 这类乱码。
- 向外部工具传中文内容时，优先走 UTF-8 文件或 UTF-8 stdin，不要把中文正文直接塞进易受编码影响的命令行参数。
- Windows 下调用原生命令且内容包含中文时，不能只依赖 `chcp 65001`。

在 PowerShell 中，调用 `gh`、`git`、`node`、`python` 等原生命令前，先显式设置：

```powershell
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
```

## 文件写入

- Python 写文件时显式使用 `encoding="utf-8"`。
- PowerShell 写文件时优先使用 `Set-Content -Encoding utf8` 或其他明确指定 UTF-8 的方式。
- 如果工具支持从 stdin 读取正文，优先使用 UTF-8 stdin。
- 如果工具对 stdin/管道的中文支持不稳定，先写入 UTF-8 临时文件，再让工具读取该文件。

## Code Review

- 做 PR review 时，如果已经形成明确 finding，默认直接用 `gh` 提交到对应 PR。
- 仅当用户明确要求不要提交时，才只保留本地结论。
- 提交 review/comment 时同样必须保证正文为 UTF-8。
