# HTTPS 与反向代理

本发行脚手架不启动 TLS 服务。`compose.yaml` 仅把 HTTP API 绑定在 **127.0.0.1:8787**；这是反向代理的后端，不是可以正常登录的面板地址。应用的 Secure Cookie 和可信源校验保持开启，不提供关闭认证/CSRF/HTTPS 的开关。

## 推荐：域名与已有宿主机反向代理

先把自己的域名解析到服务器、获取有效 TLS 证书，再在向导中填 `https://panel.example.org`（替换为自己的域名）。官方 OAuth 应用中必须登记完全一致的 `https://panel.example.org/callback`。向导把完整回调写入 `app/data/config.json`，避免沿用原安装的域名。

宿主机已有 Caddy 时，可参考以下配置（不是容器内 Caddy；域名必须替换）：

```caddyfile
panel.example.org {
    # 不启用访问日志，避免 OAuth code/state 出现在日志中。
    reverse_proxy 127.0.0.1:8787
}
```

Caddy 的安装、DNS、证书申请及公网防火墙由部署者负责，本脚手架不自动执行。若已有 Nginx，保持全站 HTTPS，使用固定域名、相同路径代理到 `http://127.0.0.1:8787`，保留正常 Host/Origin，不要添加跨域通配符，不要另行公开 API。将代理访问日志关闭或去除查询字符串；错误日志也要避免泄露 OAuth 查询参数。若自选后端端口，代理目标必须同步修改。

## 仅本机开发：可信 localhost TLS

默认 `https://localhost:8443` 只是向导默认值，**并不表示已经提供 TLS**。可在本机安装 Caddy，用其本地 CA；让浏览器实际信任该 CA，而不是长期点击证书警告：

```caddyfile
https://localhost:8443 {
    tls internal
    reverse_proxy 127.0.0.1:8787
}
```

需要部署者自己安装/运行 Caddy 并在浏览器使用的机器导入正确的本地 CA 根证书。私钥/CA 不应进入 Git 仓库。本文不声称该配置已在你的机器上运行，也未验证官方 HDHive 是否接受 localhost 回调。若官方不允许，就必须使用已登记的真实 HTTPS 域名；能打开本机面板不等于 OAuth 已可用。

服务器在远端、浏览器在本机时，可以先使用 SSH 本地转发，再在浏览器本机做 HTTPS 终止：

```bash
ssh -N -L 127.0.0.1:18787:127.0.0.1:8787 user@your-server
```

此时本机 Caddy 上游改成 `127.0.0.1:18787`，面板与向导仍用 `https://localhost:8443`；官方回调限制仍然存在。SSH 隧道本身不把 HTTP 升级成 HTTPS。不要把后端绑定改成 `0.0.0.0` 来绕过这些限制。

如果反向代理运行在另一个 Docker 容器，容器内 `127.0.0.1` 指向自己而不是宿主机，以上示例不能直接套用；请自行设计受控 Docker 网络与唯一入口。本脚手架不提供默认公网 API 或 Docker socket。
