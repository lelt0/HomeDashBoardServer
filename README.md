# Home Dashboard

家庭内情報表示ホワイトボード用Webアプリケーション。

## 技術スタック

- Python 3.13
- uv
- FastAPI / Uvicorn
- Jinja2
- HTML / CSS / Vanilla JavaScript
- TOML
- pytest / Ruff

## 起動

```bash
uv sync
uv run uvicorn home_dashboard.main:app --host 0.0.0.0 --port 8000
```

ローカルでは `http://127.0.0.1:8000/`、LAN内の別端末では `http://<サーバーIP>:8000/` を開く。

## ディレクトリ構成

```text
src/home_dashboard/
  main.py                  # FastAPIアプリ
  dashboard/layout.py      # ダッシュボードレイアウト読込
  features/<feature>/      # 機能単位のサーバー側実装

web/
  templates/               # ページ構造
  static/css/              # 共通CSS
  static/features/<id>/    # 機能単位のCSS/JavaScript

config/
  config.toml              # サーバー設定
  dashboard.toml           # グリッドレイアウト
```

`config/dashboard.toml` の `[[tiles]]` を変更することで、機能の配置・表示幅を機能実装から分離して変更できる。
