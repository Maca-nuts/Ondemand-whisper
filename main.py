import torch
import whisper

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright
from yt_dlp import YoutubeDL


DOWNLOAD_DIR = Path("/mnt/c/Users/sshuser/Downloads")

VIDEO_EXTENSIONS = {
    ".m3u8": "m3u8",
    ".mpd": "mpd",
    ".f4m": "f4m",
    ".mp4": "mp4",
    ".m4v": "m4v",
    ".mov": "mov",
    ".webm": "webm",
    ".mkv": "mkv",
    ".avi": "avi",
    ".wmv": "wmv",
    ".flv": "flv",
    ".ts": "ts",
    ".m2ts": "m2ts",
    ".mts": "mts",
    ".3gp": "3gp",
    ".ogv": "ogv",
}

VIDEO_CONTENT_TYPES = {
    "mpegurl": "m3u8",
    "dash+xml": "mpd",
    "vnd.ms-sstr+xml": "ism",
    "f4m+xml": "f4m",
    "video/mp4": "mp4",
    "video/x-m4v": "m4v",
    "video/quicktime": "mov",
    "video/webm": "webm",
    "video/x-matroska": "mkv",
    "video/x-msvideo": "avi",
    "video/x-ms-wmv": "wmv",
    "video/x-flv": "flv",
    "video/mp2t": "ts",
    "video/3gpp": "3gp",
    "video/ogg": "ogv",
}

SOURCE_TYPE_PRIORITY = {
    "m3u8": 0,
    "mpd": 1,
    "ism": 2,
    "f4m": 3,
    "mp4": 4,
    "m4v": 5,
    "mov": 6,
    "webm": 7,
    "mkv": 8,
    "avi": 9,
    "wmv": 10,
    "flv": 11,
    "ogv": 12,
    "3gp": 13,
    "ts": 20,
    "m2ts": 21,
    "mts": 22,
    "video": 30,
}


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

    for content_type_part, source_type in VIDEO_CONTENT_TYPES.items():
        if content_type_part in normalized_content_type:
            return source_type

    for extension, source_type in VIDEO_EXTENSIONS.items():
        if parsed_path.endswith(extension) or f"{extension}/" in parsed_path:
            return source_type

    if parsed_path.endswith(".ism/manifest") or parsed_path.endswith("/manifest"):
        return "ism"

    if normalized_content_type.startswith("video/"):
        return "video"

    return None


def add_video_source_candidate(candidates, url, source_type):
    if not url or not source_type:
        return
    if any(candidate["url"] == url for candidate in candidates):
        return

    candidates.append({"url": url, "type": source_type})


def select_best_video_source(candidates):
    if not candidates:
        return None

    return sorted(
        enumerate(candidates),
        key=lambda item: (
            SOURCE_TYPE_PRIORITY.get(item[1]["type"], SOURCE_TYPE_PRIORITY["video"]),
            item[0],
        ),
    )[0][1]


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

video_source_candidates = []
add_video_source_candidate(
    video_source_candidates,
    WATCH_URL,
    detect_video_source(WATCH_URL),
)


def handle_response(response):
    url = response.url
    source_type = detect_video_source(url, response.headers.get("content-type", ""))
    add_video_source_candidate(video_source_candidates, url, source_type)


if not video_source_candidates:
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

        try:
            video_urls = page.locator("video, video source").evaluate_all(
                """(elements) => elements.flatMap((element) => [
                    element.currentSrc,
                    element.src,
                    element.getAttribute("src"),
                    element.getAttribute("data-src"),
                    element.getAttribute("data-url"),
                    element.getAttribute("data-hls-url"),
                    element.getAttribute("data-dash-url"),
                ]).filter(Boolean)"""
            )
            for video_url in video_urls:
                add_video_source_candidate(
                    video_source_candidates,
                    video_url,
                    detect_video_source(video_url),
                )
        except PlaywrightError:
            pass

        browser.close()

video_source = select_best_video_source(video_source_candidates)

if not video_source:
    raise RuntimeError("対応している動画URLが見つかりませんでした。")

print(f"{video_source['type']} URLを取得しました:")
print(video_source["url"])

ydl_opts = {
    "outtmpl": str(DOWNLOAD_DIR / f"{output_stem}.%(ext)s"),
    "format": "best",
    "merge_output_format": "mp4",
    "retries": 10,
    "fragment_retries": 10,
}

with YoutubeDL(ydl_opts) as ydl:
    ydl.download([video_source["url"]])

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
