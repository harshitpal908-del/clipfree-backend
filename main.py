import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai

# FastAPI app initialization (Yeh zaroori hai taaki Render 'app' attribute dhund sake)
app = FastAPI(title="ClipFree AI Backend")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Google Gemini client
AI_API_KEY = os.environ.get("GEMINI_API_KEY", "dummy_key")
ai_client = genai.Client(api_key=AI_API_KEY)

class ClipRequest(BaseModel):
    youtube_url: str
    aspect_ratio: str = "9:16"
    caption_lang: str = "hi"
    style_id: str = "ms-1"

def generate_ass_subtitles(segments, ass_path: str, lang: str, style_id: str):
    """Basic, Glowing aur Floating .ass subtitles generator for Mastersoft, CapCut & VN Editor styles"""
    
    # Default styling values
    primary_color = "&H0000E6FF" # Yellow
    outline_color = "&H00000000" # Black outline
    back_color = "&H80000000"    # Shadow background
    font_size = "68"
    shadow_val = "2"
    outline_val = "4"
    
    # Style ke hisaab se colors aur glow adjust karna
    if "cc-" in style_id: # CapCut styles
        if "3" in style_id: # Red Alert
            primary_color = "&H00FFFFFF"
            back_color = "&H000000FF" # Red box
        elif "2" in style_id or "5" in style_id: # Neon/Purple Glow
            primary_color = "&H00FFFF00" # Cyan/Purple
            outline_val = "6"
    elif "vn-" in style_id: # VN Editor styles
        if "3" in style_id or "25" in style_id: # Glowing RGB
            primary_color = "&H00F900D5"
            outline_val = "5"

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},{primary_color},&H000000FF,{outline_color},{back_color},-1,0,0,0,100,100,0,0,1,{outline_val},{shadow_val},2,40,40,260,1

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
def create_clips(req: ClipRequest):
    # Mocking response for testing integration
    return {
        "clips": [
            {
                "title": "Viral Podcast Moment #1",
                "score": "9.8/10",
                "time": "00:15 - 00:45",
                "download_url": "https://www.w3schools.com/html/mov_bbb.mp4"
            }
        ]
    }

@app.get("/")
def root():
    return {"status": "ClipFree AI Backend is running successfully 🚀"}