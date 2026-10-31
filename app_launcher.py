import os
import sys
import time
import shutil
import webbrowser
import threading

# Determine bundle directory
if getattr(sys, "frozen", False):
    bundle_dir = sys._MEIPASS
else:
    bundle_dir = os.path.abspath(os.path.dirname(__file__))

# Cấu hình Playwright browser path cho môi trường đóng gói EXE
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    ms_playwright = os.path.join(local_app_data, "ms-playwright")
    if os.path.exists(ms_playwright):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = ms_playwright

# Ensure bin directory with ffmpeg & ffprobe is in PATH
bin_candidates = [
    os.path.join(bundle_dir, "bin"),
    bundle_dir,
    os.path.abspath("bin")
]
for b in bin_candidates:
    if os.path.exists(b):
        os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")

# Ensure user workspace directories exist
for folder in ["outputs", "temp", "memes", "bgm", "backgrounds"]:
    os.makedirs(folder, exist_ok=True)

# Copy default assets if missing in user directory
def extract_defaults():
    try:
        # index.html
        idx_src = os.path.join(bundle_dir, "index.html")
        if os.path.exists(idx_src) and not os.path.exists("index.html"):
            shutil.copyfile(idx_src, "index.html")
        
        # background.mp4
        bg_src = os.path.join(bundle_dir, "background.mp4")
        if os.path.exists(bg_src) and not os.path.exists("background.mp4"):
            shutil.copyfile(bg_src, "background.mp4")
            
        # bgm
        bgm_dir = os.path.join(bundle_dir, "bgm")
        if os.path.exists(bgm_dir):
            for f in os.listdir(bgm_dir):
                s = os.path.join(bgm_dir, f)
                d = os.path.join("bgm", f)
                if os.path.isfile(s) and not os.path.exists(d):
                    shutil.copyfile(s, d)

        # memes
        memes_dir = os.path.join(bundle_dir, "memes")
        if os.path.exists(memes_dir):
            for f in os.listdir(memes_dir):
                s = os.path.join(memes_dir, f)
                d = os.path.join("memes", f)
                if os.path.isfile(s) and not os.path.exists(d):
                    shutil.copyfile(s, d)
    except Exception as e:
        print(f"[Warning] Khong the sao chep asset mac dinh: {e}")

extract_defaults()

# Import server app
from server import app
import uvicorn

def open_browser():
    time.sleep(1.5)
    url = "http://127.0.0.1:8000"
    print(f"\n>>> Dang tu dong mo trinh duyet tai: {url} ...")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[Warning] Khong the tu dong mo trinh duyet: {e}")

def print_banner():
    banner = """
======================================================================
   GHIEN DOC COMMENT - AI VIDEO MAKER v2.0
   FastAPI + Direct FFmpeg Render Engine (Ultra Fast ~5s)
======================================================================
 * Server Localhost (May tinh)   : http://127.0.0.1:8000
 * Dien thoai (iPhone & Android) : http://192.168.0.106:8000 (chung Wi-Fi)
 * Thu muc video xuat ra       : outputs/
 * Thu muc Meme                : memes/
 * Thu muc Nhac nen            : bgm/
 * De thoat ung dung           : Nhan [Ctrl + C] hoac dong cua so nay
======================================================================
"""
    print(banner)

if __name__ == "__main__":
    import asyncio
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    print_banner()
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run uvicorn server
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
