"""开发环境启动脚本：双栈监听 IPv4 + IPv6。

用法：
    python run.py             # 双栈监听（IPv4 + IPv6），无热重载
    python run.py --reload    # 热重载（IPv6 only，Vite 代理可用）

解决 Windows 上 Vite 代理走 ::1 而 uvicorn 默认只绑 IPv4 的问题。
双栈模式下 127.0.0.1 和 [::1] 都能访问后端。
"""
import socket
import sys

import uvicorn


def make_dualstack_socket(host: str = "::", port: int = 8000) -> socket.socket:
    """创建 IPv6 双栈 socket（同时接受 IPv4 和 IPv6 连接）。"""
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    # 关键：允许 IPv6 socket 同时接受 IPv4 连接
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(128)
    return sock


def main() -> None:
    port = 8000
    reload = "--reload" in sys.argv

    if reload:
        # reload 模式不支持自定义 socket，用 host="::"（IPv6，Vite 代理可用）
        print("✓ 启动（reload 模式，IPv6 ::1:8000）")
        uvicorn.run(
            "app.main:app",
            host="::",
            port=port,
            reload=True,
            reload_dirs=["app"],
            log_level="info",
        )
    else:
        # 双栈模式：IPv4 + IPv6 都监听
        sock = make_dualstack_socket(port=port)
        config = uvicorn.Config("app.main:app", log_level="info")
        server = uvicorn.Server(config)
        print("✓ 双栈监听 http://localhost:8000 (IPv4 127.0.0.1 + IPv6 ::1)")
        server.run(sockets=[sock])


if __name__ == "__main__":
    main()
