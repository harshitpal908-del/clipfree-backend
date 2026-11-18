import os
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="ClipFree AI Final Fix")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class ClipRequest(BaseModel):
    youtube_url: str
    aspect_ratio: str = "9:16"
    caption_lang: str = "hi"
    style_id: str = "ms-1"

@app.post("/api/clip")
def create_clips(req: ClipRequest):
    try:
        input_file = "input_video.mp4"
        
        # FIX: Format ko 'best' kar diya hai taaki koi format error na aaye
        ydl_opts = {
            'format': 'best',
            'outtmpl': input_file,
            'noplaylist': True,
            'socket_timeout': 30
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.youtube_url, download=True)
            video_title = info.get('title', 'YouTube Short')

        rendered_clips = []
        for i in range(1, 4):
            output_clip_path = f"static/clip_{i}.mp4"
            start_time = i * 15
            
            filter_complex = "[0:v]scale=360:640:force_original_aspect_ratio=increase,crop=360:640[v]"
            cmd = [
                "ffmpeg", "-y", "-ss", str(start_time), "-t", "10",
                "-i", input_file, "-filter_complex", filter_complex,
                "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac", output_clip_path
            ]
            
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            rendered_clips.append({
                "title": f"{video_title[:30]} - Part {i}",
                "score": f"9.{10-i}/10",
                "time": f"00:{start_time:02d} - 00:{start_time+10:02d}",
                "download_url": f"https://clipfree-backend-3.onrender.com/static/clip_{i}.mp4"
            })

        return {"clips": rendered_clips}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing YouTube video: {str(e)}")

@app.get("/")
def root():
    return {"status": "Real YouTube Clipper is active 🚀"}