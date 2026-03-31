# dreamina-cli

一个给 Agent 用的 Dreamina CLI skill。

它不直接包装成黑盒插件，而是保留一层很薄的可读执行面:

- 用 Python wrapper 调 `dreamina`
- 统一参数名
- 校验本地路径
- 返回稳定 JSON
- 支持 `--dry-run`

适合需要把即梦能力接进 Agent、工作流、节点系统、自动化任务里的场景。

## 目录

```text
dreamina-cli/
├── SKILL.md
├── agents/
├── references/
└── scripts/
```

- `SKILL.md`: skill 触发规则和默认工作流
- `scripts/`: 对 `dreamina` 的 wrapper
- `references/commands.md`: 命令清单和参数说明
- `references/integration.md`: 集成到不同 runtime 的建议

## 先装 Dreamina CLI

先安装官方 CLI:

```bash
curl -fsSL https://jimeng.jianying.com/cli | bash
```

安装后检查:

```bash
dreamina -h
dreamina version
```

如果终端里找不到 `dreamina`，先重开 shell。还不行的话，检查 `PATH`。常见安装位置是:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## 登录与自检

发起登录:

```bash
dreamina login
```

浏览器没拉起，或者回调卡住时:

```bash
dreamina login --debug
```

登录后先做一次自检:

```bash
dreamina user_credit
```

如果能返回包含余额信息的 JSON，说明登录态和本地环境已经生效。

## 本地状态文件

Dreamina CLI 会在 `~/.dreamina_cli/` 下维护这些文件:

- `config.toml`: 环境配置
- `credential.json`: 本地登录态
- `tasks.db`: 本地任务记录
- `logs/`: 运行日志

如果生成命令报权限、登录或环境异常，先检查两件事:

1. `~/.dreamina_cli/config.toml` 是否存在且有效
2. `dreamina user_credit` 是否能正常返回

## 把 Skill 接进 Agent

把这个目录复制或挂载到你的 skill registry，保持相对路径不变。

运行环境至少要有:

- `python3`
- `dreamina`

推荐工作流:

1. 先做能力发现
2. 选最窄的 wrapper
3. 对高成本或高歧义任务先跑 `--dry-run`
4. 再执行真实命令
5. 读取 wrapper JSON
6. 保留 `submit_id`，供后续轮询

## 快速使用

能力发现:

```bash
python3 ./scripts/list_capabilities.py --format json
```

先 dry-run:

```bash
python3 ./scripts/text2image.py \
  --prompt "clean silver ring product shot" \
  --ratio 1:1 \
  --resolution-type 2k \
  --dry-run
```

真实提交:

```bash
python3 ./scripts/text2video.py \
  --prompt "camera pushes toward a necklace on a gray stage" \
  --duration 5 \
  --poll 30
```

查询异步结果:

```bash
python3 ./scripts/query_result.py \
  --submit-id 3f6eb41f425d23a3
```

查看成功任务:

```bash
python3 ./scripts/list_task.py --gen-status success --limit 20
```

## Wrapper 返回格式

成功:

```json
{
  "ok": true,
  "command": "text2image",
  "cli_args": ["dreamina", "text2image", "..."],
  "data": {}
}
```

失败:

```json
{
  "ok": false,
  "command": "text2image",
  "cli_args": ["dreamina", "text2image", "..."],
  "error": "normalized message",
  "details": ["detail 1", "detail 2"]
}
```

对生成任务来说，只有在 `submit_id` 存在且 `gen_status` 为 `querying` 或 `success` 时，才应视为提交成功。

## 常用 Dreamina CLI 命令

文生图:

```bash
dreamina text2image \
  --prompt="一只戴墨镜的橘猫" \
  --ratio=1:1 \
  --resolution_type=2k \
  --poll=30
```

文生视频:

```bash
dreamina text2video \
  --prompt="镜头推进，一只橘猫从沙发上跳下来" \
  --duration=5 \
  --ratio=16:9 \
  --video_resolution=720P \
  --poll=30
```

图生图:

```bash
dreamina image2image \
  --images ./input.png \
  --prompt="改成水彩风格" \
  --resolution_type=2k \
  --poll=30
```

图生视频:

```bash
dreamina image2video \
  --image ./first_frame.png \
  --prompt="镜头慢慢推近" \
  --duration=5 \
  --poll=30
```

查询并下载结果:

```bash
dreamina query_result --submit_id=<submit_id> --download_dir=./downloads
```

查看任务:

```bash
dreamina list_task
dreamina list_task --gen_status=success
dreamina list_task --submit_id=<submit_id>
```

## 运行约定

- 已支持的命令优先走 wrapper，不直接裸调 `dreamina`
- 默认复用当前本地登录态
- 遇到 `AigcComplianceConfirmationRequired` 时，先完成一次网页侧授权再重试
- 所有异步任务都保留 `submit_id`
- 需要更顺手的交互时，默认加 `--poll`

## 参考

- [SKILL.md](./SKILL.md)
- [references/commands.md](./references/commands.md)
- [references/integration.md](./references/integration.md)
