# Ondemand Whisper

動画ページの URL から `.m3u8` の動画ストリームを取得し、動画をダウンロードしたあと、OpenAI Whisper で文字起こしして Markdown ファイルを作成するスクリプトです。

出力ファイルは Windows の `Downloads` に保存されます。

```text
airtime_YYYYMMDD_HHMMSS.mp4
airtime_YYYYMMDD_HHMMSS.md
```

## 動作確認済み環境

- Windows + WSL Ubuntu 22.04
- Python 3.10
- NVIDIA GPU
- CUDA 対応の PyTorch
- Playwright Chromium
- ffmpeg

## 使用ライブラリ

- `torch`
  - Whisper の GPU 実行に使用
- `openai-whisper`
  - 文字起こし
- `playwright`
  - 動画の取得
- `yt-dlp`
  - 動画の取得
- `ffmpeg`
  - Whisperのため

## セットアップ

 - WSL 側で実行します。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
```

ffmpeg をインストールします。

```bash
sudo apt update
sudo apt install -y ffmpeg
```

Playwright と Chromium の依存関係をインストールします。

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
python3 -m playwright install-deps chromium
```

Whisper と yt-dlp をインストールします。

```bash
python3 -m pip install openai-whisper yt-dlp
```

PyTorch をインストールします。CUDA 版は GPU や CUDA バージョンによってコマンドが変わるため、基本的には PyTorch 公式ページで自分の環境に合うコマンドを確認してください。

## 使い方

```bash
source .venv/bin/activate
python3 main.py
```

実行すると、以下を順番に入力します。

1. 使用する GPU 番号
2. Whisper モデル
   - `1`: turbo
   - `2`: small
   - `3`: medium
3. 動画 URL

動画のダウンロードが完了すると、同じファイル名で Markdown の文字起こしも作成されます。

## 注意点

- `main.py` の出力先は`main.py`で固定されています。別ユーザー名や別フォルダで使う場合は `DOWNLOAD_DIR` を変更してください。
- Playwright 実行時に `libnspr4.so` などの共有ライブラリ不足エラーが出る場合があります。このときは下のコマンドを実行してみてください。

```bash
python3 -m playwright install-deps chromium
```

- URLを入力してから動画の取得に時間がかかる場合があります。
