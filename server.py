import subprocess
import os
import re
import sys
import json
import uuid
import asyncio
from io import BytesIO
from typing import List, Optional, Dict, Any
import requests
import shutil
import socket
import traceback
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from playwright.async_api import async_playwright
import edge_tts
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont

# Vá lỗi MoviePy 1.0.3 không tương thích với Pillow >= 10
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS
from moviepy.editor import (
    VideoFileClip, AudioFileClip, ImageClip, ColorClip,
    CompositeVideoClip, concatenate_videoclips, CompositeAudioClip
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Cấu hình đường dẫn trình duyệt Playwright khi chạy độc lập / PyInstaller
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    ms_playwright = os.path.join(local_app_data, "ms-playwright")
    if os.path.exists(ms_playwright):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = ms_playwright

for b in [os.path.join(os.path.dirname(__file__), "bin"), os.path.abspath("bin")]:
    if os.path.exists(b) and b not in os.environ.get("PATH", ""):
        os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")

os.makedirs("outputs", exist_ok=True)
os.makedirs("temp", exist_ok=True)
os.makedirs("memes", exist_ok=True)
os.makedirs("bgm", exist_ok=True)
os.makedirs("backgrounds", exist_ok=True)

app = FastAPI(title="Ghiền Đọc Comment - AI Video Maker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
app.mount("/memes", StaticFiles(directory="memes"), name="memes")
app.mount("/bgm", StaticFiles(directory="bgm"), name="bgm")
app.mount("/backgrounds", StaticFiles(directory="backgrounds"), name="backgrounds")

# ==========================================
# DATA MODELS
# ==========================================
class SceneItem(BaseModel):
    author: str
    time_ago: str = "1 ngày"
    display_text: str          # Chữ giữ nguyên viết tắt hiển thị trên thẻ ảnh
    tts_text: str              # Chữ đã bung viết tắt & lách từ nhạy cảm để đọc voice
    reply_author: Optional[str] = None
    reply_display_text: Optional[str] = None  # Dùng cho bình luận nối tiếp (Stacked Reply)
    reply_tts_text: Optional[str] = None
    avatar_url: Optional[str] = None
    likes: str = "4.3K"
    comments: str = "24"
    reposts: str = "47"
    shares: str = "14"
    author_liked: bool = True
    meme_file: Optional[str] = None           # Tên file meme trong thư mục memes/ (VD: cat_punch.mp4)

class ScrapeRequest(BaseModel):
    url: str
    max_comments: int = 7
    gemini_api_key: Optional[str] = None

class NormalizeRequest(BaseModel):
    scenes: List[SceneItem]
    api_key: Optional[str] = None

class RenderRequest(BaseModel):
    scenes: List[SceneItem]
    voice: str = "vi-VN-HoaiMyNeural"
    speed: str = "+20%"
    watermark_text: str = "Fanpage: Ghiền đọc comment"
    moving_watermark: bool = True
    bg_video_path: Optional[str] = "background.mp4"
    bgm_path: Optional[str] = "bgm/chill_relax.mp3"
    bgm_volume: float = 0.12
    resolution: str = "1080x1920" # '720x1280' siêu tốc hoặc '1080x1920' Full HD

# ==========================================
# 1. MODULE DỊCH CHỮ ĐỌC TTS CHUẨN PHONG CÁCH "GHIỀN ĐỌC COMMENT"
# ==========================================
SLANG_TTS_MAP = [
    (r"\bvcl\b", "vãi cả lờ"),
    (r"\bvl\b", "vãi lờ"),
    (r"\bvđ\b", "vãi đạn"),
    (r"\bvãi l\b", "vãi lờ"),
    (r"\bhãm l\b", "hãm lờ"),
    (r"\bhãm lồn\b", "hãm lờ"),
    (r"\blồn\b", "lờ"),
    (r"\bđéo\b", "éo"),
    (r"\bđm\b", "đệt mẹ"),
    (r"\bđme\b", "đệt mẹ"),
    (r"\bđịt mẹ\b", "đệt mẹ"),
    (r"\bcứt\b", "cức"),
    (r"\bchết\b", "chớt"),
    (r"\btrc\b", "trước"),
    (r"\bngta\b", "người ta"),
    (r"\bnta\b", "người ta"),
    (r"\bvk\b", "vợ"),
    (r"\bck\b", "chồng"),
    (r"\bnv\b", "như vậy"),
    (r"\bcx\b", "cũng"),
    (r"\bko\b", "không"),
    (r"\bk\b", "không"),
    (r"\bđc\b", "được"),
    (r"\bdc\b", "được"),
    (r"\bmn\b", "mọi người"),
    (r"\bmng\b", "mọi người"),
    (r"\bnyc\b", "người yêu cũ"),
    (r"\bny\b", "người yêu"),
    (r"\bbn\b", "bạn"),
    (r"\bb\b", "bạn"),
    (r"\blp\b", "lớp"),
    (r"\bmít\b", "méc"),
    (r"\btn\b", "tin nhắn"),
    (r"\brep\b", "rép"),
    (r"\bmmc\b", "mờ mờ cờ"),
    (r"\bv\b", "vậy"),
    (r"\br\b", "rồi"),
    (r"\bt\b", "tao"),
    (r"\bm\b", "mày"),
    (r"\bmí\b", "mấy"),
    (r"\bthg\b", "thằng"),
    (r"\bnma\b", "nhưng mà"),
    (r"\bvs\b", "với"),
]

def local_slang_to_tts(text: str) -> str:
    """Chuyển đổi câu chứa từ viết tắt & nhạy cảm sang câu đọc giống hệt video mẫu"""
    if not text:
        return ""
    res = text
    # Chuyển giờ/phút: 30p -> 30 phút, 5h -> 5 giờ
    res = re.sub(r"(\d+)\s*p\b", r"\1 phút", res, flags=re.IGNORECASE)
    res = re.sub(r"(\d+)\s*h\b", r"\1 giờ", res, flags=re.IGNORECASE)
    # Chuyển các ký hiệu cười "=))", ":))", ":(" đi để TTS không đọc
    res = re.sub(r"[:=]+[\)\(\-D]+", "", res)
    res = re.sub(r"blah\s*blah", "bờ la bờ la", res, flags=re.IGNORECASE)

    for pattern, repl in SLANG_TTS_MAP:
        res = re.sub(pattern, repl, res, flags=re.IGNORECASE)

    res = re.sub(r"\.{2,}", ", ", res)
    return re.sub(r"\s+", " ", res).strip()

GEMINI_TTS_INSTRUCTION = """
Bạn là biên tập viên kịch bản đọc comment Threads cho kênh "Ghiền đọc comment".
Hãy chuyển từng câu bình luận gốc sang văn bản đọc lồng tiếng (TTS) theo đúng quy tắc sau:
1. Bung toàn bộ từ viết tắt theo đúng ngữ cảnh câu chuyện: "t" -> "tao", "m" -> "mày", "vk" -> "vợ", "ck" -> "chồng", "trc" -> "trước", "ngta" -> "người ta", "cx" -> "cũng", "v" -> "vậy", "r" -> "rồi", "lp" -> "lớp", "bn/b" -> "bạn", "tn" -> "tin nhắn", "nma" -> "nhưng mà", "mí thg" -> "mấy thằng", "30p" -> "30 phút".
2. Lách các từ nhạy cảm theo đúng phong cách đọc hài hước của kênh:
   - "vcl" -> "vãi cả lờ"
   - "vl" -> "vãi lờ"
   - "đéo" -> "éo"
   - "đm / đme / địt mẹ" -> "đệt mẹ"
   - "hãm lồn" -> "hãm lờ"
   - "chết" -> "chớt"
   - "blah blah" -> "bờ la bờ la"
3. Xóa bỏ các ký hiệu mặt cười như ":))", "=))", ":(" hoặc emoji để giọng đọc không bị khựng.
4. Trả về đúng mảng JSON các chuỗi chữ đọc tương ứng theo thứ tự đầu vào.
"""

async def convert_tts_with_gemini(scenes: List[SceneItem], custom_key: Optional[str] = None) -> List[SceneItem]:
    api_key = (custom_key or os.getenv("GEMINI_API_KEY", "")).strip()
    
    # Luôn chạy bước chuyển đổi cục bộ trước
    for s in scenes:
        s.tts_text = local_slang_to_tts(s.display_text)
        if s.reply_display_text:
            s.reply_tts_text = local_slang_to_tts(s.reply_display_text)

    if not api_key:
        return scenes

    try:
        client = genai.Client(api_key=api_key)
        raw_list = [s.display_text for s in scenes]
        resp = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=json.dumps(raw_list, ensure_ascii=False),
            config=types.GenerateContentConfig(
                system_instruction=GEMINI_TTS_INSTRUCTION,
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=list[str],
            ),
        )
        parsed = json.loads(resp.text)
        if isinstance(parsed, list) and len(parsed) == len(scenes):
            for i, val in enumerate(parsed):
                if val and val.strip():
                    scenes[i].tts_text = val.strip()
    except Exception as e:
        print(f"[Gemini Fallback] Dùng bộ từ điển nội bộ: {e}")

    return scenes

# ==========================================
# 2. VẼ GIAO DIỆN THẺ THREADS GIỐNG HỆT VIDEO MẪU
# ==========================================
def get_font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def fetch_avatar_with_plus_badge(url: Optional[str], size: int = 76) -> Image.Image:
    """Tạo ảnh Avatar tròn kèm nút dấu (+) màu đen ở góc dưới bên phải giống hệt Threads"""
    canvas = Image.new("RGBA", (size + 6, size + 6), (0, 0, 0, 0))
    av_img = None

    if url:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Referer": "https://www.threads.net/",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
            }
            r = requests.get(url, timeout=5, headers=headers)
            if r.status_code == 200:
                av_img = Image.open(BytesIO(r.content)).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        except Exception:
            pass

    if av_img is None:
        av_img = Image.new("RGBA", (size, size), (215, 218, 224, 255))
        d_av = ImageDraw.Draw(av_img)
        # Vẽ hình bóng người mặc định giống ảnh đầu tiên trong video
        d_av.ellipse((size*0.3, size*0.18, size*0.7, size*0.55), fill=(150, 155, 165))
        d_av.pieslice((size*0.15, size*0.52, size*0.85, size*1.15), 180, 360, fill=(150, 155, 165))

    # Bo tròn Avatar
    mask = Image.new("L", (size * 2, size * 2), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 2, size * 2), fill=255)
    mask = mask.resize((size, size), Image.Resampling.LANCZOS)
    canvas.paste(av_img, (0, 0), mask)

    # Vẽ huy hiệu dấu (+) đen viền trắng ở góc dưới bên phải
    badge_d = 28
    bx, by = size - badge_d + 4, size - badge_d + 4
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((bx, by, bx + badge_d, by + badge_d), fill=(15, 15, 15, 255), outline=(255, 255, 255, 255), width=3)
    # Dấu cộng trắng
    cx, cy = bx + badge_d // 2, by + badge_d // 2
    draw.line((cx - 5, cy, cx + 5, cy), fill=(255, 255, 255), width=2)
    draw.line((cx, cy - 5, cx, cy + 5), fill=(255, 255, 255), width=2)
    return canvas

def draw_single_box(
    author: str,
    time_ago: str,
    text: str,
    avatar_url: Optional[str],
    likes: str,
    comments: str,
    reposts: str,
    shares: str,
    author_liked: bool,
    show_footer: bool = True
) -> Image.Image:
    """Vẽ 1 hộp bình luận trắng chuẩn mẫu 'Ghiền đọc comment'"""
    width = 920
    pad_left = 128
    pad_right = 40
    max_text_w = width - pad_left - pad_right

    f_bold = get_font(31, bold=True)
    f_time = get_font(28, bold=False)
    f_body = get_font(32, bold=False)
    f_stat = get_font(26, bold=False)

    # Ngắt dòng tự động
    dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    lines = []
    for para in text.split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            test = f"{cur} {w}".strip()
            bbox = dummy.textbbox((0, 0), test, font=f_body)
            if (bbox[2] - bbox[0]) <= max_text_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)

    line_h = 46
    footer_space = 82 if show_footer else 28
    box_h = 88 + (len(lines) * line_h) + footer_space

    img = Image.new("RGBA", (width, box_h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    # 1. Avatar + dấu cộng
    av = fetch_avatar_with_plus_badge(avatar_url, size=76)
    img.paste(av, (28, 26), av)

    # 2. Tên username + thời gian + cụm icon góc phải
    draw.text((pad_left, 24), author, fill=(15, 15, 15), font=f_bold)
    name_w = draw.textbbox((0, 0), author, font=f_bold)[2]
    draw.text((pad_left + name_w + 18, 26), time_ago, fill=(150, 150, 155), font=f_time)

    # Cụm icon góc phải (Tim đỏ tác giả + Ghim + 3 chấm)
    if author_liked:
        draw.ellipse((width - 145, 26, width - 115, 56), fill=(255, 48, 64))
        draw.text((width - 137, 28), "♥", fill=(255, 255, 255), font=f_stat)
    draw.text((width - 75, 22), "•••", fill=(160, 160, 165), font=f_bold)

    # 3. Nội dung bình luận (giữ nguyên viết tắt)
    y_text = 74
    for ln in lines:
        draw.text((pad_left, y_text), ln, fill=(20, 20, 20), font=f_body)
        y_text += line_h

    # 4. Thanh 4 icon tương tác ở đáy (Tim, Comment, Repost, Share)
    if show_footer:
        fy = box_h - 54
        x_cur = pad_left

        # Icon Tim
        draw.text((x_cur, fy), f"♡  {likes}", fill=(40, 40, 45), font=f_stat)
        x_cur += 165
        # Icon Comment
        draw.text((x_cur, fy), f"💬  {comments}", fill=(40, 40, 45), font=f_stat)
        x_cur += 145
        # Icon Repost
        draw.text((x_cur, fy), f"↻  {reposts}", fill=(40, 40, 45), font=f_stat)
        x_cur += 145
        # Icon Share
        draw.text((x_cur, fy), f"➢  {shares}", fill=(40, 40, 45), font=f_stat)

    # Viền mảnh bo nhẹ quanh thẻ
    draw.rectangle([(0, 0), (width - 1, box_h - 1)], outline=(230, 230, 235), width=2)
    return img

def create_watermark_image(text: str) -> str:
    """Tạo ảnh Watermark chữ nghiêng trắng viền đen giống 'Fanpage: Ghiền đọc comment'"""
    path = f"temp/wm_{uuid.uuid4().hex[:6]}.png"
    font = get_font(30, bold=True)
    img = Image.new("RGBA", (620, 60), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Vẽ stroke đen và chữ trắng
    draw.text((15, 10), text, font=font, fill=(255, 255, 255, 235), stroke_width=3, stroke_fill=(0, 0, 0, 220))
    img.save(path, "PNG")
    return path

# ==========================================
# 3. ENGINE RENDER VIDEO (STACKED REPLY + MEME OVERLAY + MOVING WATERMARK)
# ==========================================
def is_image_file(file_path: str) -> bool:
    """Kiểm tra file có phải là định dạng ảnh hay không"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in [".png", ".jpg", ".jpeg", ".webp", ".jfif", ".bmp"]

def normalize_audio_to_aac(in_path: str, out_path: str, duration: Optional[float] = None):
    """Chuẩn hóa mọi âm thanh về chuẩn chung: AAC 44100Hz Stereo để concat mượt mà không lỗi"""
    cmd = ["ffmpeg", "-y", "-i", in_path]
    if duration is not None:
        cmd.extend(["-t", f"{duration:.3f}"])
    cmd.extend(["-vn", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k", out_path])
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def make_silence_aac(out_path: str, duration: float):
    """Tạo file âm thanh yên lặng chuẩn AAC 44100Hz Stereo"""
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", f"{duration:.3f}", "-c:a", "aac", "-b:a", "192k", out_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

async def make_tts_audio(text: str, voice: str, speed: str, out_path: str):
    raw_mp3 = out_path + ".raw.mp3"
    comm = edge_tts.Communicate(text, voice, rate=speed)
    await comm.save(raw_mp3)
    normalize_audio_to_aac(raw_mp3, out_path)
    if os.path.exists(raw_mp3):
        try:
            os.remove(raw_mp3)
        except OSError:
            pass

def get_media_duration(file_path: str) -> float:
    """Đo thời lượng file âm thanh hoặc video bằng ffprobe cực nhanh (chỉ vài mili-giây)"""
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        dur = float(out)
        return max(0.5, dur)
    except Exception:
        try:
            a = AudioFileClip(file_path)
            d = a.duration
            a.close()
            return max(0.5, d)
        except Exception:
            return 3.0

def has_audio_stream(file_path: str) -> bool:
    """Kiểm tra file video/audio có luồng âm thanh hay không"""
    try:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        return bool(out)
    except Exception:
        return False

@app.post("/api/render")
async def render_video(req: RenderRequest):
    if not req.scenes:
        raise HTTPException(status_code=400, detail="Kịch bản trống!")

    job_id = uuid.uuid4().hex[:8]
    temp_files = []

    # Phân giải kích thước (Mặc định 1080x1920, hỗ trợ 720x1280 siêu tốc)
    res_str = getattr(req, "resolution", "1080x1920") or "1080x1920"
    if res_str == "720x1280":
        vid_w, vid_h = 720, 1280
    else:
        vid_w, vid_h = 1080, 1920

    wm_img_path = create_watermark_image(req.watermark_text)
    temp_files.append(wm_img_path)

    try:
        # BƯỚC 1: TẢI TOÀN BỘ GIỌNG ĐỌC TTS SONG SONG (PARALLEL GATHER)
        tts_tasks = []
        scenes_meta = []

        for idx, sc in enumerate(req.scenes):
            a1_path = f"temp/{job_id}_{idx}_a1.aac"
            c1_path = f"temp/{job_id}_{idx}_c1.png"
            temp_files.extend([a1_path, c1_path])

            has_reply = bool(sc.reply_display_text and sc.reply_display_text.strip())
            tts_tasks.append((sc.tts_text or sc.display_text, req.voice, req.speed, a1_path))

            a2_path = None
            c2_path = None
            if has_reply:
                a2_path = f"temp/{job_id}_{idx}_a2.aac"
                c2_path = f"temp/{job_id}_{idx}_c2.png"
                temp_files.extend([a2_path, c2_path])
                tts_tasks.append((sc.reply_tts_text or local_slang_to_tts(sc.reply_display_text), req.voice, req.speed, a2_path))

            scenes_meta.append({
                "idx": idx,
                "scene": sc,
                "has_reply": has_reply,
                "a1_path": a1_path,
                "c1_path": c1_path,
                "a2_path": a2_path,
                "c2_path": c2_path
            })

        # Chạy đồng thời tất cả các yêu cầu TTS trong 1 nhịp duy nhất
        await asyncio.gather(*[make_tts_audio(txt, vc, sp, pth) for txt, vc, sp, pth in tts_tasks])

        # BƯỚC 2: TẠO ẢNH THẺ VÀ LẬP TIMELINE CHÍNH XÁC
        timeline_segments = []
        audio_segment_paths = []
        cur_time = 0.0

        for meta in scenes_meta:
            sc = meta["scene"]
            dur1 = get_media_duration(meta["a1_path"]) + 0.25
            has_reply = meta["has_reply"]

            box1_img = draw_single_box(
                sc.author, sc.time_ago, sc.display_text, sc.avatar_url,
                sc.likes, sc.comments, sc.reposts, sc.shares,
                sc.author_liked, show_footer=(not has_reply)
            )
            box1_img.save(meta["c1_path"], "PNG")

            timeline_segments.append({
                "type": "card",
                "img_path": meta["c1_path"],
                "dur": dur1,
                "start": cur_time,
                "end": cur_time + dur1
            })
            audio_segment_paths.append(meta["a1_path"])
            cur_time += dur1
            last_card_path = meta["c1_path"]

            if has_reply:
                dur2 = get_media_duration(meta["a2_path"]) + 0.25
                box2_img = draw_single_box(
                    sc.reply_author or sc.author, sc.time_ago, sc.reply_display_text, sc.avatar_url,
                    sc.likes, sc.comments, sc.reposts, sc.shares, sc.author_liked, show_footer=True
                )
                stacked_h = box1_img.height + box2_img.height + 6
                stacked_img = Image.new("RGBA", (box1_img.width, stacked_h), (0, 0, 0, 0))
                stacked_img.paste(box1_img, (0, 0))
                stacked_img.paste(box2_img, (0, box1_img.height + 6))
                stacked_img.save(meta["c2_path"], "PNG")
                last_card_path = meta["c2_path"]

                timeline_segments.append({
                    "type": "card",
                    "img_path": meta["c2_path"],
                    "dur": dur2,
                    "start": cur_time,
                    "end": cur_time + dur2
                })
                audio_segment_paths.append(meta["a2_path"])
                cur_time += dur2

            # Xử lý Meme reaction (Hỗ trợ cả Video MP4/MOV/WebM/AVI/MKV, Ảnh PNG/JPG/WebP và GIF)
            if sc.meme_file and sc.meme_file.strip():
                m_name = os.path.basename(sc.meme_file.strip())
                m_path = os.path.join("memes", m_name)
                if os.path.exists(m_path) and os.path.getsize(m_path) > 100:
                    is_img = is_image_file(m_path)
                    if is_img:
                        m_dur = 2.2 # Thời lượng hiển thị ảnh meme (2.2 giây)
                    else:
                        raw_mdur = get_media_duration(m_path)
                        m_dur = min(max(raw_mdur, 1.2), 3.5)

                    timeline_segments.append({
                        "type": "meme",
                        "img_path": last_card_path,
                        "meme_path": m_path,
                        "is_image": is_img,
                        "dur": m_dur,
                        "start": cur_time,
                        "end": cur_time + m_dur
                    })

                    m_audio = f"temp/{job_id}_m_{len(timeline_segments)}.aac"
                    temp_files.append(m_audio)
                    if (not is_img) and has_audio_stream(m_path):
                        normalize_audio_to_aac(m_path, m_audio, duration=m_dur)
                    else:
                        make_silence_aac(m_audio, duration=m_dur)

                    audio_segment_paths.append(m_audio)
                    cur_time += m_dur

        total_dur = cur_time

        # BƯỚC 3: XÂY DỰNG FFMPEG PIPELINE SIÊU TỐC (CHẠY TRỰC TIẾP TRONG C / HARDWARE)
        bg_input = req.bg_video_path.strip() if req.bg_video_path else ""
        if bg_input and not os.path.exists(bg_input):
            cand = os.path.join("backgrounds", os.path.basename(bg_input))
            if os.path.exists(cand):
                bg_input = cand

        has_bg_video = bool(bg_input and os.path.exists(bg_input) and os.path.getsize(bg_input) > 1024)

        bgm_input = req.bgm_path.strip() if req.bgm_path else ""
        if bgm_input and not os.path.exists(bgm_input):
            cand = os.path.join("bgm", os.path.basename(bgm_input))
            if os.path.exists(cand):
                bgm_input = cand
        has_bgm = bool(bgm_input and os.path.exists(bgm_input) and os.path.getsize(bgm_input) > 1024)

        # Gộp tất cả audio segment (Đã được chuẩn hoá AAC 44100Hz Stereo)
        concat_txt = f"temp/{job_id}_audios.txt"
        temp_files.append(concat_txt)
        with open(concat_txt, "w", encoding="utf-8") as f:
            for ap in audio_segment_paths:
                clean_p = os.path.abspath(ap).replace("\\", "/")
                f.write(f"file '{clean_p}'\n")

        voice_merged = f"temp/{job_id}_voice_full.aac"
        temp_files.append(voice_merged)
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c:a", "copy", voice_merged],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        cmd_inputs = []
        filter_parts = []
        cur_input_idx = 0

        # Input 0: Background
        if has_bg_video:
            cmd_inputs.extend(["-stream_loop", "-1", "-i", bg_input])
            filter_parts.append(
                f"[{cur_input_idx}:v]scale={vid_w}:{vid_h}:force_original_aspect_ratio=increase,crop={vid_w}:{vid_h},setsar=1[v_base];"
            )
            cur_input_idx += 1
        else:
            cmd_inputs.extend(["-f", "lavfi", "-i", f"color=c=0x120c18:s={vid_w}x{vid_h}:r=24:d={total_dur:.3f}"])
            filter_parts.append(f"[{cur_input_idx}:v]setsar=1[v_base];")
            cur_input_idx += 1

        last_v = "v_base"

        # Overlay từng thẻ comment & meme
        for s_idx, seg in enumerate(timeline_segments):
            cmd_inputs.extend(["-loop", "1", "-i", seg["img_path"]])
            v_card = cur_input_idx
            cur_input_idx += 1

            v_next = f"v_seg_{s_idx}"
            filter_parts.append(
                f"[{last_v}][{v_card}:v]overlay=(W-w)/2:(H-h)/2:enable='between(t,{seg['start']:.3f},{seg['end']:.3f})'[{v_next}];"
            )
            last_v = v_next

            # Nếu có meme (Hỗ trợ cả Video và Ảnh/GIF, căn chỉnh chuẩn tâm, giữ tỉ lệ không méo)
            if seg["type"] == "meme":
                is_img = seg.get("is_image", False)
                if is_img:
                    cmd_inputs.extend(["-loop", "1", "-i", seg["meme_path"]])
                else:
                    cmd_inputs.extend(["-stream_loop", "-1", "-i", seg["meme_path"]])

                v_meme_in = cur_input_idx
                cur_input_idx += 1
                v_meme_scaled = f"m_scale_{s_idx}"
                v_meme_applied = f"v_m_{s_idx}"

                max_w = int(vid_w * 0.90)
                max_h = int(vid_h * 0.46)
                filter_parts.append(
                    f"[{v_meme_in}:v]format=yuva420p,scale=w={max_w}:h={max_h}:force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1[{v_meme_scaled}];"
                    f"[{last_v}][{v_meme_scaled}]overlay=(W-w)/2:(H-h)/2:enable='between(t,{seg['start']:.3f},{seg['end']:.3f})'[{v_meme_applied}];"
                )
                last_v = v_meme_applied

        # Watermark overlay
        cmd_inputs.extend(["-loop", "1", "-i", wm_img_path])
        v_wm = cur_input_idx
        cur_input_idx += 1

        wm_y = "260+mod(t*95,980)" if req.moving_watermark else "260"
        filter_parts.append(f"[{last_v}][{v_wm}:v]overlay=(W-w)/2:'{wm_y}'[v_out]")

        # Audio stream
        audio_inputs = ["-i", voice_merged]
        v_voice_idx = cur_input_idx
        cur_input_idx += 1

        if has_bgm:
            audio_inputs.extend(["-stream_loop", "-1", "-i", bgm_input])
            v_bgm_idx = cur_input_idx
            cur_input_idx += 1
            vol = max(0.01, min(1.0, float(req.bgm_volume)))
            audio_filter = f"[{v_voice_idx}:a][{v_bgm_idx}:a]amix=inputs=2:duration=first:weights=1.0 {vol}[a_out]"
        else:
            audio_filter = f"[{v_voice_idx}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a_out]"

        full_filter = "".join(filter_parts) + ";" + audio_filter

        out_name = f"ghien_comment_{job_id}.mp4"
        out_path = f"outputs/{out_name}"

        cmd = [
            "ffmpeg", "-y",
            *cmd_inputs,
            *audio_inputs,
            "-filter_complex", full_filter,
            "-map", "[v_out]",
            "-map", "[a_out]",
            "-t", f"{total_dur:.3f}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "fastdecode",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-threads", "0",
            out_path
        ]

        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            err_msg = p.stderr.decode("utf-8", errors="ignore")[-800:]
            print(f"[FFmpeg Render Error] {err_msg}")
            raise HTTPException(status_code=500, detail=f"Lỗi khi mã hóa video: {err_msg}")

        return {"status": "success", "video_url": f"/outputs/{out_name}"}
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Render Fatal Error]\n{tb}")
        raise HTTPException(status_code=500, detail=f"Lỗi Render chi tiết:\n{tb}")
    finally:
        for f in temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass

# ==========================================
# 4. MODULE CÀO LINK VÀ LẤY BÀI VIẾT + BÌNH LUẬN GỐC TỪ THREADS
# ==========================================
IGNORED_HEADER_WORDS = {
    'đã ghim', 'tác giả', 'theo dõi', 'follow', 'following', 'pinned', 'author', '·', '•',
    'được tài trợ', 'sponsored'
}
STAT_REGEX = re.compile(r'^[0-9,.]+[KMBkmb]?$')
TIME_REGEX = re.compile(r'^\d+\s*(?:giờ|ngày|phút|giây|h|d|m|s|w|tuần|tháng|năm)(?:\s*trước)?$', re.IGNORECASE)

def parse_threads_container(lines: List[str], default_author: str = "", default_time: str = "1 ngày") -> Dict[str, Any]:
    """Phân tích các dòng văn bản thô từ container của Threads thành thông tin chuẩn"""
    if not lines:
        return {"author": default_author or "user", "time_ago": default_time, "text": "", "likes": "0", "comments": "0", "reposts": "0", "shares": "0"}

    # Tách các chỉ số thống kê ở đuôi (likes, comments, reposts, shares)
    stats = []
    idx = len(lines) - 1
    while idx >= 0 and STAT_REGEX.match(lines[idx]):
        stats.insert(0, lines[idx])
        idx -= 1
        
    content_lines = list(lines[:idx + 1])
    
    # Bỏ các nhãn tiêu đề như 'Đã ghim'
    while content_lines and content_lines[0].lower().strip() in IGNORED_HEADER_WORDS:
        content_lines.pop(0)
        
    author = default_author
    if content_lines:
        first = content_lines[0].strip()
        if not TIME_REGEX.match(first) and len(first.split()) == 1:
            author = content_lines.pop(0)
            
    time_ago = default_time
    while content_lines and (content_lines[0].lower().strip() in IGNORED_HEADER_WORDS or TIME_REGEX.match(content_lines[0].strip())):
        w = content_lines.pop(0).strip()
        if TIME_REGEX.match(w) and time_ago == default_time:
            time_ago = w
            
    while content_lines and content_lines[0].lower().strip() in IGNORED_HEADER_WORDS:
        content_lines.pop(0)
        
    text = "\n".join(content_lines).strip()
    
    likes = stats[0] if len(stats) > 0 else "0"
    comments = stats[1] if len(stats) > 1 else "0"
    reposts = stats[2] if len(stats) > 2 else "0"
    shares = stats[3] if len(stats) > 3 else "0"
    
    return {
        "author": author or default_author or "user",
        "time_ago": time_ago,
        "text": text,
        "likes": likes,
        "comments": comments,
        "reposts": reposts,
        "shares": shares
    }

async def scrape_threads_post(url: str, max_comments: int = 7) -> List[SceneItem]:
    clean_url = url.strip()
    if not clean_url.startswith("http"):
        clean_url = "https://" + clean_url
    clean_url = clean_url.split("?")[0]
    
    if "threads.net" not in clean_url and "threads.com" not in clean_url:
        raise ValueError("URL không phải liên kết Threads hợp lệ (cần chứa threads.net hoặc threads.com).")
        
    async with async_playwright() as p:
        browser = None
        launch_errors = []
        for l_opt in [
            {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]},
            {"channel": "msedge", "headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]},
            {"channel": "chrome", "headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]}
        ]:
            try:
                browser = await p.chromium.launch(**l_opt)
                break
            except Exception as le:
                launch_errors.append(str(le))
        
        if browser is None:
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khởi chạy trình duyệt: {launch_errors[-1] if launch_errors else 'Không tìm thấy Chromium hoặc Edge'}"
            )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            locale="vi-VN"
        )
        page = await context.new_page()
        # Chặn video / audio nặng để tăng tốc độ tải trang
        await page.route("**/*.{mp4,webm,ogg,wav,mp3,gif}", lambda r: r.abort())
        
        try:
            await page.goto(clean_url, wait_until="domcontentloaded", timeout=25000)
            try:
                await page.wait_for_selector('div[data-pressable-container="true"]', timeout=10000)
            except Exception:
                pass
                
            # Cuộn trang nhẹ để kích hoạt tải thêm bình luận
            for _ in range(2):
                await page.evaluate("window.scrollBy(0, 800)")
                await page.wait_for_timeout(800)
                
            extracted = await page.evaluate('''() => {
                const containers = Array.from(document.querySelectorAll('div[data-pressable-container="true"]'));
                return containers.map((c, idx) => {
                    const authorLink = c.querySelector('a[href*="/@"]');
                    let author = "";
                    if (authorLink) {
                        const href = authorLink.getAttribute('href') || "";
                        const m = href.match(/@([a-zA-Z0-9._]+)/);
                        author = m ? m[1] : authorLink.innerText.trim();
                    }
                    
                    let avatarUrl = "";
                    const imgs = Array.from(c.querySelectorAll('img'));
                    for (const img of imgs) {
                        const src = img.getAttribute('src') || "";
                        if (src.includes('fbcdn.net') || src.includes('cdninstagram.com')) {
                            avatarUrl = src;
                            break;
                        }
                    }
                    
                    const timeEl = c.querySelector('time');
                    const timeAgo = timeEl ? (timeEl.innerText.trim() || timeEl.getAttribute('datetime')) : "";
                    
                    const lines = c.innerText.split('\\n').map(s => s.trim()).filter(Boolean);
                    
                    return {
                        idx,
                        author,
                        avatarUrl,
                        timeAgo,
                        lines
                    };
                });
            }''')
            
            if not extracted:
                raise ValueError("Không tìm thấy dữ liệu bài viết trên trang Threads này (có thể bài bị xoá hoặc để chế độ riêng tư).")
                
            parsed_items = []
            for item in extracted:
                p_item = parse_threads_container(
                    item["lines"],
                    default_author=item["author"],
                    default_time=item["timeAgo"] or "1 ngày"
                )
                if not p_item["text"]:
                    continue
                p_item["avatar_url"] = item["avatarUrl"]
                p_item["raw_lines"] = item["lines"]
                parsed_items.append(p_item)
                
            if not parsed_items:
                raise ValueError("Không trích xuất được nội dung bài viết từ trang Threads.")
                
            root_post = parsed_items[0]
            root_author = root_post["author"]
            
            scenes: List[SceneItem] = []
            
            # 1. Thẻ Topic Gốc (Original Post)
            root_scene = SceneItem(
                author=root_post["author"],
                time_ago=root_post["time_ago"],
                display_text=root_post["text"],
                tts_text=local_slang_to_tts(root_post["text"]),
                avatar_url=root_post["avatar_url"],
                likes=root_post["likes"],
                comments=root_post["comments"],
                reposts=root_post["reposts"],
                shares=root_post["shares"],
                author_liked=True,
                meme_file=""
            )
            scenes.append(root_scene)
            
            # Lấy danh sách meme có sẵn trong thư mục memes/ để gợi ý
            available_memes = [f for f in os.listdir("memes") if f.lower().endswith((".mp4", ".mov", ".webm"))]
            
            # 2. Các bình luận gốc (Original Comments)
            for it in parsed_items[1:]:
                if len(scenes) - 1 >= max_comments:
                    break
                    
                lines_lower = [l.lower() for l in it.get("raw_lines", [])]
                is_author_reply = ('tác giả' in lines_lower) or (it["author"] == root_author)
                
                # Nếu là bình luận trả lời của chính tác giả ngay sau 1 bình luận khác -> Ghép thành Stacked Reply
                if is_author_reply and len(scenes) > 1 and not scenes[-1].reply_display_text:
                    scenes[-1].reply_author = it["author"]
                    scenes[-1].reply_display_text = it["text"]
                    scenes[-1].reply_tts_text = local_slang_to_tts(it["text"])
                    continue
                    
                meme_candidate = available_memes[(len(scenes) - 1) % len(available_memes)] if available_memes else ""
                cmt_scene = SceneItem(
                    author=it["author"],
                    time_ago=it["time_ago"],
                    display_text=it["text"],
                    tts_text=local_slang_to_tts(it["text"]),
                    avatar_url=it["avatar_url"],
                    likes=it["likes"],
                    comments=it["comments"],
                    reposts=it["reposts"],
                    shares=it["shares"],
                    author_liked=True,
                    meme_file=meme_candidate
                )
                scenes.append(cmt_scene)
                
            return scenes
        finally:
            await browser.close()

@app.post("/api/scrape")
async def scrape_api(req: ScrapeRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp đường link bài viết Threads!")
        
    try:
        scenes = await scrape_threads_post(req.url, req.max_comments)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        print(f"[Scrape Error] {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi cào dữ liệu Threads: {str(e)}")
        
    if req.gemini_api_key and req.gemini_api_key.strip():
        scenes = await convert_tts_with_gemini(scenes, req.gemini_api_key.strip())
        
    return {
        "status": "success",
        "topic": scenes[0] if scenes else None,
        "comments_count": max(0, len(scenes) - 1),
        "scenes": scenes
    }

@app.post("/api/normalize")
async def normalize_api(req: NormalizeRequest):
    updated = await convert_tts_with_gemini(req.scenes, req.api_key)
    return {"status": "success", "scenes": updated}


# ==========================================
# CÁC API QUẢN LÝ BGM & MEME & BACKGROUND
# ==========================================
@app.get("/api/bgm")
async def list_bgm():
    """Liệt kê các file nhạc nền có trong thư mục bgm/"""
    files = [f for f in os.listdir("bgm") if f.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg"))]
    return {"bgms": files}

@app.post("/api/upload-bgm")
async def upload_bgm(file: UploadFile = File(...)):
    """Tải lên file nhạc nền mới vào thư mục bgm/"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ!")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".mp3", ".wav", ".m4a", ".aac", ".ogg"]:
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file âm thanh: mp3, wav, m4a, aac, ogg!")
    
    clean_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file.filename)
    dest_path = os.path.join("bgm", clean_name)
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"status": "success", "filename": clean_name, "url": f"/bgm/{clean_name}"}

SUPPORTED_MEME_EXTS = [
    ".mp4", ".mov", ".webm", ".avi", ".mkv", ".flv",
    ".gif",
    ".png", ".jpg", ".jpeg", ".webp", ".jfif", ".bmp"
]

@app.post("/api/upload-meme")
async def upload_meme(file: UploadFile = File(...)):
    """Tải lên file meme mới (cả Video, GIF và Ảnh) vào thư mục memes/"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ!")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_MEME_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng {ext} không hỗ trợ! Vui lòng chọn Video (.mp4, .mov, .webm) hoặc Ảnh/GIF (.png, .jpg, .webp, .gif)."
        )
    
    raw_stem = os.path.splitext(file.filename)[0]
    safe_stem = re.sub(r"[^\w\-_.]", "_", raw_stem, flags=re.ASCII).strip("_")
    if not safe_stem:
        safe_stem = "meme"
    clean_name = f"{safe_stem}_{uuid.uuid4().hex[:4]}{ext}"
    dest_path = os.path.join("memes", clean_name)
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {
        "status": "success",
        "filename": clean_name,
        "url": f"/memes/{clean_name}",
        "type": "image" if is_image_file(dest_path) else "video"
    }

@app.delete("/api/memes/{filename}")
async def delete_meme(filename: str):
    """Xóa một meme khỏi thư mục memes/"""
    safe_name = os.path.basename(filename)
    p = os.path.join("memes", safe_name)
    if os.path.exists(p):
        try:
            os.remove(p)
            return {"status": "success", "deleted": safe_name}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=404, detail="Không tìm thấy meme!")

@app.post("/api/upload-bg")
async def upload_bg(file: UploadFile = File(...)):
    """Tải lên video nền mới (.mp4)"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ!")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".mp4", ".mov", ".webm"]:
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ video nền: mp4, mov, webm!")
        
    clean_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file.filename)
    dest_path = os.path.join("backgrounds", clean_name)
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    shutil.copyfile(dest_path, "background.mp4")
    return {"status": "success", "filename": clean_name, "path": dest_path}

@app.get("/api/memes")
async def list_memes():
    """Liệt kê các file meme (cả video, ảnh và gif) có trong thư mục memes/"""
    valid_exts = tuple(SUPPORTED_MEME_EXTS)
    files = []
    if os.path.exists("memes"):
        files = [f for f in os.listdir("memes") if f.lower().endswith(valid_exts)]
    return {"memes": files}

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

@app.get("/api/network-info")
async def get_network_info():
    lan_ip = get_lan_ip()
    port = int(os.environ.get("PORT", 8000))
    return {
        "lan_ip": lan_ip,
        "port": port,
        "local_url": f"http://127.0.0.1:{port}",
        "mobile_url": f"http://{lan_ip}:{port}"
    }

@app.get("/manifest.json")
async def get_manifest():
    return JSONResponse({
        "name": "Ghiền Đọc Comment Studio",
        "short_name": "ThreadViral",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0B0F17",
        "theme_color": "#0B0F17",
        "icons": [
            {
                "src": "https://img.icons8.com/color/192/threads.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "https://img.icons8.com/color/512/threads.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    })

@app.get("/")
async def index_page():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    bundle_path = os.path.join(getattr(sys, "_MEIPASS", ""), "index.html")
    if os.path.exists(bundle_path):
        return FileResponse(bundle_path)
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)