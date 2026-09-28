"""生产 WSGI 入口。

    waitress-serve --listen=0.0.0.0:5000 wsgi:app

启动前设置 APP_ENV=production、DATABASE_URL 与 SECRET_KEY（见 .env.example）。
本文件只组装应用，不建表、不写数据。
"""

from __future__ import annotations

from app import create_app

app = create_app()

if __name__ == "__main__":  # 仅便于本地排查，不作为生产启动方式
    app.run(host="127.0.0.1", port=5000)
