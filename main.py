import torch
import whisper

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright
from yt_dlp import YoutubeDL


DOWNLOAD_DIR = Path("/mnt/c/Users/sshuser/Downloads")


def format_timestamp(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def find_downloaded_video(output_stem):
    video_path = DOWNLOAD_DIR / f"{output_stem}.mp4"
    if video_path.exists():
        return video_path

    downloaded_files = sorted(
        DOWNLOAD_DIR.glob(f"{output_stem}.*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not downloaded_files:
        raise RuntimeError("ダウンロードしたファイルが見つかりませんでした。")
    return downloaded_files[0]


def detect_video_source(url, content_type=""):
    parsed_path = urlparse(url).path.lower()
    normalized_content_type = content_type.lower()

    if ".m3u8" in parsed_path or "mpegurl" in normalized_content_type:
        return "m3u8"
    if ".mp4" in parsed_path or "video/mp4" in normalized_content_type:
        return "mp4"

    return None


print("cuda available:", torch.cuda.is_available())
print("cuda version:", torch.version.cuda)
print("gpu count:", torch.cuda.device_count())

for i in range(torch.cuda.device_count()):
    print(i, torch.cuda.get_device_name(i))

print("Which GPU do you want to use?")
gpu_number = input("Enter the GPU number: ")
device = "cuda:" + gpu_number

print("Which mode do you want to use?")
print("1. turbo")
print("2. small")
print("3. medium")
model_name = input("Enter the mode number: ")

if model_name == "1":
    model = whisper.load_model("turbo", device=device)
elif model_name == "2":
    model = whisper.load_model("small", device=device)
elif model_name == "3":
    model = whisper.load_model("medium", device=device)
else:
    print("Invalid model number")
    exit()

print("このデバイスでモデルをロードしました。")
print(next(model.parameters()).device)

WATCH_URL = input("動画URLを入力: ").strip()
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_stem = f"airtime_{timestamp}"

video_source_url = WATCH_URL
video_source_type = detect_video_source(WATCH_URL)


def handle_response(response):
    global video_source_url, video_source_type
    if video_source_type:
        return

    url = response.url
    source_type = detect_video_source(url, response.headers.get("content-type", ""))
    if source_type:
        video_source_url = url
        video_source_type = source_type


if not video_source_type:
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False)
        except PlaywrightError as exc:
            raise RuntimeError(
                "Playwright Chromium failed to start. "
                "Install the Linux browser dependencies in WSL with: "
                "python3 -m playwright install-deps chromium"
            ) from exc

        context = browser.new_context()
        page = context.new_page()

        page.on("response", handle_response)
        page.goto(WATCH_URL, wait_until="networkidle")

        try:
            page.click("video")
        except PlaywrightError:
            pass

        page.wait_for_timeout(10000)

        if not video_source_type:
            try:
                video_urls = page.locator("video").evaluate_all(
                    "(videos) => videos.map((video) => video.currentSrc || video.src).filter(Boolean)"
                )
                for video_url in video_urls:
                    source_type = detect_video_source(video_url)
                    if source_type:
                        video_source_url = video_url
                        video_source_type = source_type
                        break
            except PlaywrightError:
                pass

        browser.close()

if not video_source_type:
    raise RuntimeError("m3u8 / mp4 URLが見つかりませんでした。")

print(f"{video_source_type} URLを取得しました:")
print(video_source_url)

ydl_opts = {
    "outtmpl": str(DOWNLOAD_DIR / f"{output_stem}.%(ext)s"),
    "format": "best",
    "merge_output_format": "mp4",
    "retries": 10,
    "fragment_retries": 10,
}

with YoutubeDL(ydl_opts) as ydl:
    ydl.download([video_source_url])

video_path = find_downloaded_video(output_stem)

print("ダウンロード完了:")
print(video_path)

print("文字起こしを開始します...")
result = model.transcribe(str(video_path))

markdown_path = DOWNLOAD_DIR / f"{output_stem}.md"
with markdown_path.open("w", encoding="utf-8") as f:
    f.write(f"# Transcription {timestamp}\n\n")
    f.write(f"- Source: `{video_path.name}`\n")
    f.write(f"- Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write("## Full Text\n\n")
    f.write(result["text"].strip() + "\n\n")
    f.write("## Segments\n\n")
    for segment in result.get("segments", []):
        start = format_timestamp(segment["start"])
        end = format_timestamp(segment["end"])
        text = segment["text"].strip()
        f.write(f"- `{start} - {end}` {text}\n")

print("文字起こしMarkdownを作成しました:")
print(markdown_path)
