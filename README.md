# HDHive 安装器（仅公开部署文件）

> **不公开核心代码。** 这里只包含安装向导、Compose、空白配置示例、中文文档与独立离线测试；不包含应用、网页资源、许可证客户端/服务端源码、构建文件或私有镜像。
>
> 本仓库仅分发安装器，不包含核心程序或镜像。公开文件不等于获得开源或再分发许可；未选择 MIT 或其他开源许可证。核心程序与私有镜像的使用、交付和授权条件由所有者另行确认。

## 1. 先向所有者获取两样东西

1. **所有者签发的激活码**：只在之后的私密交互提示中输入，不放入命令参数、环境变量、聊天、截图或工单。
2. **所有者交付的私有镜像文件及可信校验信息**：本安装器固定使用本机标签 `hdhive-official:licensed`。没有公开镜像仓库地址，不会自动拉取同名镜像，也不能从这个仓库编译核心程序。镜像只应按所有者授权私下保存，不上传到 GitHub、公开 Registry 或 release 附件。

安装器不附带镜像，也不声称你的机器已经有镜像。仅有激活码或仅有这些公开文件，都不足以运行程序。镜像内需要包含匹配版本的程序、网页静态资源与许可证启动器；获得镜像的信任与使用权限是前提，安装器不能保证恶意镜像安全，也不意味着镜像内程序不可被提取。

前置条件：Linux/macOS 或 WSL、Python 3.9+、Docker Engine/Desktop 和 Docker Compose v2+。秘密所在文件系统必须真实支持 POSIX 0600/0700；不要使用宽松的共享盘。实际激活、在线续验及业务操作需要网络；离线测试不访问业务服务。

在专用安装目录中操作。安装器地址为 `https://github.com/zg2088/hdhive`；该仓库不附带核心程序或镜像。下载的镜像放在仓库目录**之外**；先通过可信渠道核对所有者提供的校验信息，再在镜像所在目录执行：

```bash
# 文件名仅为示例，使用所有者实际交付的文件名。
docker load -i owner-delivered-image.tar

docker image inspect hdhive-official:licensed --format '{{.Id}}'
```

导入不等于已获得许可或已核对来源。如果导入结果没有上述标签，停止并向所有者索取正确交付物；不要随意重标未知镜像来绕过检查。不要运行他人提供的远程安装脚本。

## 2. 准备你自己的参数

| 参数 | 来源与要求 |
|---|---|
| `ADMIN_ID` | 你的 Telegram 数字用户 ID，正整数，不是 `@用户名` 或群 ID。务必核对，以免误授管理权限。 |
| `BOT_TOKEN` | 从 Telegram 官方 `@BotFather` 创建自己的 Bot 获取；向导仅检查语法，不验证真实性。 |
| `TG_API_ID` / `TG_API_HASH` | 自己在 [my.telegram.org](https://my.telegram.org) 创建的应用参数；正整数 ID 和32位十六进制 HASH，必须同时填写或同时留空。留空不能启用用户态监听。 |
| `TG_PHONE` | 可选，自己的 `+国家码` 国际格式手机号。向导不收验证码或两步验证密码。 |
| `WEB_USERNAME` / `WEB_PASSWORD` | 新建面板身份，用户名默认 `admin`；密码无默认值，至少16字符并确认，不要复用密码。 |
| `HDHIVE_CLIENT_ID` / `HDHIVE_CLIENT_SECRET` | 你自己的 HDHive OAuth/OpenAPI 应用参数，两者必填。 |
| `HDHIVE_API_KEY` | 可选兼容 App Secret 字段，不是 OAuth Access Token；留空时按镜像应用的兼容逻辑处理。 |
| `PANEL_ORIGIN` | 浏览器使用的完整 HTTPS 源，不含路径、尾斜线、查询或片段，例如 `https://panel.example.org`。默认 `https://localhost:8443` 仅为开发占位。 |
| `API_PORT` | 本机环回 HTTP 后端端口，默认8787；1–65535，避免占用已有端口。 |

官方 OAuth 应用必须登记**完全一致**的回调，即 `PANEL_ORIGIN` 加 `/callback`。不保证官方接受 localhost；不接受时必须使用自己的已登记 HTTPS 域名。所有者激活码与 HDHive OAuth 参数是两套不同用途的授权，不可混用。

## 3. 私密交互初始化

回到**安装器项目根目录**，在支持安全输入的私密终端运行：

```bash
python3 scripts/setup.py
```

所有身份 ID、Token、Hash、手机号、密码及 OAuth 参数均不回显；非秘密用户名、HTTPS 源和端口可以回显。向导只用 Python 标准库，不联网、不安装依赖、不启动 Docker、不读其他安装。管道、重定向或无法安全输入的终端会被拒绝。输入格式错误会退出，错误只包含字段名、不显示输入值。

生成内容：

- `app/data/config.json`：0600，私密 JSON；管理员 ID 为整数，开关为布尔值，规则为数组。
- `.env`：0600，仅含非秘密 `API_PORT/PANEL_ORIGIN/TZ`；不把 Token/密码传到 Compose 或 Docker 环境变量。
- 新建目录：0700；运行数据目录 `app/data/` 收紧为0700。这里的 `app/` 只是本地生成的数据容器目录，不是从公开仓库分发的核心代码。

秘密中的 `$`、引号不会由 shell/Compose 展开执行。拒绝首尾空白、控制字符及格式错误，不静默修改输入。`.env.example` 与 `config.example.json` 都是不可运行的空白示例，不应直接复制成真实配置。

默认发现 `.env`、配置文件或非空运行目录，会在询问凭据前拒绝；不读取旧凭据、不合并或备份旧配置。符号链接和异常文件类型被拒绝。若需要重建，必须先停服、自行完成仓库外的加密备份，再执行：

```bash
docker compose -f compose.yaml --profile listener down
python3 scripts/setup.py --replace-config --acknowledge-stopped
```

这会完全替换 `.env` 与配置 JSON，不删除其他 token、许可证、Telegram 会话等数据。切换身份时，旧授权需自行撤销/隔离。两个文件各自原子提交，不是跨文件事务；中断后保持停服、检查完成情况再重跑。锁文件可能表示另一个向导仍在执行，未核实前不要删除。不要在共享、可被其他用户改写的安装目录中运行。

## 4. 激活，再手动启动

以下入口契约与当前许可证启动器接口对齐：`activate` 交互激活；`run api`、`run bot`、`run listener` 启动指定服务。**最终交付镜像仍须由所有者验证这一契约；离线配置测试不能证明镜像存在或激活成功。** 不匹配时停止并向所有者索取匹配版本，不要改用绕过许可证的启动命令。

在初始化完成、镜像已正确导入之后，交互激活：

```bash
# 保持交互终端，不添加 -T；不在命令行中附加激活码。
# run 不发布 API 端口，--no-deps 避免附带启动其他服务。
docker compose -f compose.yaml run --rm --no-deps api python -m hdhive_license.supervisor activate
```

根据提示私密输入所有者给你的激活码。许可证状态与设备数据保存在共享私密数据目录，按秘密处理。激活失败时先检查网络、交付版本与授权状态，联系所有者；不要反复公开日志或修改验证地址/公钥。成功提示只表示本次激活成功，运行时仍需在线验证。

先按 [HTTPS.md](docs/HTTPS.md) 配好浏览器可信的 HTTPS 反向代理。Compose 本身不提供 TLS，默认仅将 API 后端发布为 `127.0.0.1:8787`。之后：

```bash
# 只校验，不启动容器，不输出完整配置。
docker compose -f compose.yaml config -q

# 仅使用已经导入的私有镜像，不自动拉取。
docker compose -f compose.yaml up -d --pull never bot api

docker compose -f compose.yaml ps
```

始终显式指定 `-f compose.yaml`，避免误用同目录的旧 Compose 文件。使用自己的 **HTTPS 地址**登录；HTTP 后端能打开不表示登录可用，Secure Cookie、可信源及 CSRF 校验不能为了省事关闭。宿主机反向代理示例不适用于另一个容器的 localhost。

运行约束：只有 `./app/data` 数据绑定挂载；网页资源必须已包含在镜像中，无需也不应该复制本地 `web/`。没有构建上下文、Docker socket、特权模式或固定容器名；默认丢弃全部 Linux capabilities、禁止提权，固定 exec 入口设置 umask 077。每个服务必须经许可证启动器启动，**无自动重启策略**；授权无效、续验失败、程序退出或主机重启后需检查原因，再手动启动。程序监督器提供单 API worker 与关闭访问日志的运行参数，交付时需一并核对。

### OAuth、Bot、可选监听

1. 通过自己的 HTTPS 面板登录并发起 HDHive OAuth，回调必须与官方登记完全一致。不手填或分享 Access/Refresh Token。
2. 在 Telegram 主动对自己的 Bot 发 `/start`，核对管理员身份。同一个 `BOT_TOKEN` 只能运行一个长轮询实例，不要与旧服务器同时启动。
3. 需要 Telegram 用户态监听时，先通过可信面板完成自己的 API 参数、用户登录和规则配置。验证码/两步验证密码仅在受信任交互页面输入，绝不放进安装向导或 shell。
4. 确认许可证包含所需功能后，再手动启动可选监听：

   ```bash
   docker compose -f compose.yaml --profile listener up -d --pull never listener
   ```

115等可选业务授权按登录凭据处理，只在受信任面板填写。不把 Cookie、会话、许可证、回调 URL 查询参数或完整日志贴到公开问题中。API重启可能使网页会话失效。先用 `docker compose -f compose.yaml ps` 检查服务状态；查看日志前自行脱敏。

停止全部服务：

```bash
docker compose -f compose.yaml --profile listener down
```

不要删除 `app/data/` 来尝试修复授权问题。更新前先停服、加密备份，私下获取并核验所有者交付的新镜像，再导入、检查标签并按上述命令手动启动；不要从别人的安装复制数据。

## 5. 安全与公开边界

- 公开文件只包含安装器与文档；私有镜像、应用代码、网页、授权服务代码、许可证状态、配置、日志和备份均不提交。`.gitignore` 排除常见秘密与核心目录，但不能阻止强制添加或清除历史。
- `config.json` 可能包含明文面板密码和应用参数。0600/0700不能抵挡 root、Docker daemon、主机失陷或不可信镜像；不适合给不受信任用户共享主机账户。
- 公开前要做**内容和完整 Git 历史审查**。文件白名单只能证明路径边界，不是秘密扫描、许可证强度证明或镜像审计。若已泄密，应先撤销/轮换再清理历史。
- 所有者确认公开范围、权利、许可证与最终仓库地址后，才可发布这个安装器；不得借发布安装器一并公开核心代码或镜像。

## 6. 离线验证（不需要私有镜像）

在**干净的发布候选目录**，初始化或放置镜像之前执行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -W error -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_public.py
```

测试只使用临时目录与合成假参数，不导入业务代码、不访问业务网络、不读已有账户、不构建镜像或启动容器。Git/Compose可用时真实执行 `git check-ignore`、`docker compose config -q` 和 JSON 解析；缺工具会 skipped，不能算已验证。包含真实伪终端不回显、输入验证、权限、拒绝覆盖/链接、显式替换、运行 umask 与源代码隔离检查。

文件白名单检查会拒绝未列出的文件、数据、私有镜像及 Python 缓存；生成真实配置后的安装目录不再是干净公开候选目录，拒绝是预期行为，**不要为通过发布检查而删除自己的运行数据**。重新使用单独干净的公开候选目录。详细验证范围与未验证项见 [VERIFICATION.md](docs/VERIFICATION.md)。
