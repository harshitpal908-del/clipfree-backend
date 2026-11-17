import os
import json
import uuid
import subprocess
import cv2
import mediapipe as mp
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from faster_whisper import WhisperModel
from google import genai
import yt_dlp

app = FastAPI(title="ClipFree AI - 100% Free Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("outputs", exist_ok=True)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY)
whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")

class ClipRequest(BaseModel):
    youtube_url: str
    aspect_ratio: str = "9:16"   # 9:16, 4:5, 1:1, 16:9
    face_mode: str = "speaker"   # speaker, split, gaming
    caption_lang: str = "en"     # en, hi, off
    style_id: str = "mastersoft-yellow"

def detect_face_center_x(video_path: str, start_sec: int) -> float:
    """MediaPipe se video frame mein speaker ke face ki X position (0.0 to 1.0) nikalna"""
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return 0.5

    mp_face = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
    results = mp_face.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    if results.detections:
        bbox = results.detections[0].location_data.relative_bounding_box
        return max(0.2, min(0.8, bbox.xmin + bbox.width / 2))
    return 0.5

def generate_ass_subtitles(segments, ass_path: str, lang: str, style_id: str):
    """English ya Hinglish captions ki .ass subtitle file banana"""
    primary_color = "&H0000E6FF" if "yellow" in style_id else "&H00FFFFFF"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,68,{primary_color},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,40,40,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for seg in segments:
        text = seg["text"].strip().upper()
        if lang == "hi":
            # Gemini se Hinglish mein convert karein
            res = ai_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"Convert this text into natural Roman Hinglish (Hindi in English alphabet) in max 5 punchy words: {text}"
            )
            text = res.text.strip().upper()
        s_t = f"0:{int(seg['start']//60):02d}:{seg['start']%60:05.2f}"
        e_t = f"0:{int(seg['end']//60):02d}:{seg['end']%60:05.2f}"
        lines.append(f"Dialogue: 0,{s_t},{e_t},Default,,0,0,0,,{text}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

@app.post("/api/clip")
async def create_free_clips(req: ClipRequest, request: Request):
    job_id = str(uuid.uuid4())[:8]
    raw_video = f"outputs/raw_{job_id}.mp4"

    try:
        # 1. YouTube Video Download (Max 720p for fast free processing)
        ydl_opts = {
            "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
            "outtmpl": raw_video,
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.youtube_url, download=True)
            title = info.get("title", "Podcast Video")
            duration = int(info.get("duration", 180))

        # 2. Gemini AI se 4 Viral Moments nikalna
        prompt = f'Pick 4 viral 40-second moments from video "{title}" (duration {duration}s). Return ONLY JSON list: [{{"title":"...","start":10,"end":50,"score":"98%"}}]'
        ai_res = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        moments = json.loads(ai_res.text)

        # Aspect ratio dimensions
        dims = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080), "16:9": (1920, 1080)}
        out_w, out_h = dims.get(req.aspect_ratio, (1080, 1920))

        results = []
        base_url = str(request.base_url).rstrip("/")

        for i, m in enumerate(moments[:4]):
            out_file = f"clip_{job_id}_{i+1}.mp4"
            out_path = f"outputs/{out_file}"
            ass_path = f"outputs/sub_{job_id}_{i+1}.ass"

            # 3. AI Face Tracking Center X
            face_x = detect_face_center_x(raw_video, m["start"])
            crop_filter = f"scale=-2:{out_h},crop={out_w}:{out_h}:(iw-{out_w})*{face_x}:0"

            # 4. Captions (agar Off nahi hai)
            if req.caption_lang != "off":
                segs, _ = whisper_model.transcribe(raw_video, clip_timestamps=[m["start"], m["end"]])
                seg_list = [{"start": s.start - m["start"], "end": s.end - m["start"], "text": s.text} for s in segs]
                generate_ass_subtitles(seg_list, ass_path, req.caption_lang, req.style_id)
                vf = f"{crop_filter},ass={ass_path}"
            else:
                vf = crop_filter

            cmd = [
                "ffmpeg", "-y", "-ss", str(m["start"]), "-t", str(m["end"] - m["start"]),
                "-i", raw_video, "-vf", vf,
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", out_path
            ]
            subprocess.run(cmd, check=True)

            if os.path.exists(ass_path):
                os.remove(ass_path)

            results.append({
                "title": m["title"],
                "time": f"{m['start']}s - {m['end']}s",
                "score": m.get("score", "95%"),
                "download_url": f"{base_url}/outputs/{out_file}"
            })

        return {"clips": results}

    finally:
        if os.path.exists(raw_video):
            os.remove(raw_video)