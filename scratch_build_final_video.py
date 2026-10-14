"""
Refined video generator:
- Targets exact ~4:00 (240s) duration.
- Generates polished crisp text banners (top ribbon and bottom subtitle pill).
- No obscured navbar or cut-off sidebars.
- Generates 1080p MP4 with h264 encoding and smooth cross-dissolve/fades.
- Zero extraneous cursor noise, smooth clean display.
"""

import subprocess, os, sys
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
PAGES_DIR = r'C:\Users\arati.joshi\.gemini\antigravity-ide\brain\55c61af4-97e3-45e8-ab13-c03d60800693\live_pages2'
OUT_DIR   = r'C:\Users\arati.joshi\.gemini\antigravity-ide\brain\55c61af4-97e3-45e8-ab13-c03d60800693'
OUT_VIDEO = os.path.join(OUT_DIR, 'kaims_demo_final.mp4')
SCRATCH   = os.path.join(OUT_DIR, 'scratch', 'video_build_v2')
os.makedirs(SCRATCH, exist_ok=True)

W, H = 1920, 1080
FPS = 30

# Flow definition tailored to the user's updated 4-minute demo walkthrough
# Total target duration: 240 seconds (4:00)
SECTIONS = [
    # 0: Intro Title Card
    (None, 8, "KaiMS: Autonomous Operations Intelligence", "Next-Gen AI Incident Detection, Correlation, and Governed Action"),
    
    # 1: Architecture / Vision Overview
    ("p01_overview.png", 22, "Platform Overview & Command Center", "Unified operations health, active system pulse, and AI-recommended actions"),
    
    # 2: Incident Management & Unified Inbox
    ("p02_incidents.png", 24, "Incident Lifecycle: Unified Inbox", "Detect, correlate, and prioritize canonical incidents with high-fidelity signal grouping"),
    
    # 3: Decision & Human-in-the-Loop Governance
    ("p03_approvals.png", 24, "Human-in-the-Loop: Governed Approvals", "Explainable decision packets with blast-radius analysis, plan identity, and safe rollback gates"),
    
    # 4: Context Gaps & Evidence Intake
    ("p04_evidence_requests.png", 18, "Evidence Requests Queue", "Resolving investigation ambiguities by requesting verified human observations"),
    
    # 5: AI Operations Assistant (Ask Kai / Copilot)
    ("p05_copilot.png", 24, "Ask Kai: AI Operations Copilot", "Context-aware conversational assistant grounded in enterprise operational evidence"),
    
    # 6: Operational Knowledge & Runbooks
    ("p06_runbooks_knowledge.png", 20, "Runbooks & Knowledge Hub", "Curated standard operating procedures, documentation, and dynamic RAG grounding"),
    
    # 7: Wave 9 Control Plane & Health
    ("p07_platform_health.png", 24, "Wave 9 Control Plane & Platform Health", "Real-time posture across telemetry intake, reasoning pipelines, and governance controls"),
    
    # 8: Enterprise Integrations & Connectors
    ("p08_connections.png", 18, "Connections & Integrations", "Bidirectional connectors for Jira, ServiceNow, Datadog, Prometheus, and Cloud providers"),
    
    # 9: Automation Readiness & Execution Cockpit
    ("p09_automation_readiness.png", 20, "Automation Readiness Cockpit", "Pre-flight safety checks, automated remediation eligibility, and execution policies"),
    
    # 10: Immutable Audit Logging
    ("p10_audit_log.png", 16, "Immutable Audit Trail", "Complete compliance logging tracking operator identity, model decisions, and state changes"),
    
    # 11: Closed Incidents & Outcome Verification
    ("p11_closed_incidents.png", 14, "Closed Incidents & Continuous Learning", "Verified post-incident outcomes and automated feedback loops"),
    
    # 12: Outro Title Card
    (None, 8, "KaiMS AI Operations Command Center", "Autonomous operations. Governed execution. Zero operational downtime.")
]

total_target = sum(s[1] for s in SECTIONS)
print(f"Configured 13 sections with total planned length: {total_target}s ({total_target//60}m {total_target%60}s)")

# Load fonts
font_title = None
font_sub = None
font_huge = None
for fpath in ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/calibrib.ttf", "C:/Windows/Fonts/arialbd.ttf"]:
    if os.path.exists(fpath):
        font_title = ImageFont.truetype(fpath, 32)
        font_huge = ImageFont.truetype(fpath, 64)
        break

for fpath in ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/arial.ttf"]:
    if os.path.exists(fpath):
        font_sub = ImageFont.truetype(fpath, 24)
        font_huge_sub = ImageFont.truetype(fpath, 30)
        break

if not font_title:
    font_title = font_sub = font_huge = font_huge_sub = ImageFont.load_default()

def create_slide_image(img_name, title, subtitle, out_png):
    # Canvas 1920x1080
    if img_name is None:
        # High-impact branded slide
        img = Image.new("RGBA", (W, H), (15, 23, 42, 255)) # Dark navy slate
        draw = ImageDraw.Draw(img)
        # Accent glowing border
        draw.rectangle([60, 60, W - 60, H - 60], outline=(14, 165, 233, 180), width=3)
        # Title
        bbox = draw.textbbox((0, 0), title, font=font_huge)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, (H // 2) - 80), title, fill=(255, 255, 255), font=font_huge)
        # Subtitle
        sbbox = draw.textbbox((0, 0), subtitle, font=font_huge_sub)
        stw = sbbox[2] - sbbox[0]
        draw.text(((W - stw) // 2, (H // 2) + 20), subtitle, fill=(56, 189, 248), font=font_huge_sub)
    else:
        # Load screenshot
        base = Image.open(os.path.join(PAGES_DIR, img_name)).convert("RGBA")
        if base.size != (W, H):
            base = base.resize((W, H), Image.Resampling.LANCZOS)
        img = base.copy()
        draw = ImageDraw.Draw(img)
        
        # Subtitle card (bottom floating capsule)
        # Draw sleek floating bar at the bottom
        bar_w = 1600
        bar_h = 70
        bar_x = (W - bar_w) // 2
        bar_y = H - 95
        
        # Semi-transparent pill
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ol_draw = ImageDraw.Draw(overlay)
        # Top banner pill
        top_w = 1700
        top_h = 56
        top_x = (W - top_w) // 2
        top_y = 12
        ol_draw.rounded_rectangle([top_x, top_y, top_x + top_w, top_y + top_h], radius=10, fill=(15, 23, 42, 230), outline=(14, 165, 233, 200), width=2)
        
        # Bottom subtitle pill
        ol_draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=10, fill=(15, 23, 42, 235), outline=(56, 189, 248, 160), width=1)
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)
        
        # Draw section badge + title in top banner
        draw.text((top_x + 24, top_y + 11), f"KAIMS FLOW  |  {title}", fill=(241, 245, 249), font=font_title)
        
        # Draw subtitle text centered in bottom pill
        sbbox = draw.textbbox((0, 0), subtitle, font=font_sub)
        stw = sbbox[2] - sbbox[0]
        draw.text((bar_x + (bar_w - stw) // 2, bar_y + 20), subtitle, fill=(224, 242, 254), font=font_sub)

    final_rgb = img.convert("RGB")
    final_rgb.save(out_png, "PNG")

print("\nGenerating refined high-res slide graphics...")
slide_files = []
for idx, (img_name, dur, title, subtitle) in enumerate(SECTIONS):
    png_path = os.path.join(SCRATCH, f"slide_{idx:02d}.png")
    create_slide_image(img_name, title, subtitle, png_path)
    slide_files.append((png_path, dur))
    print(f"  Slide {idx:02d}: {title} ({dur}s)")

# Now compile each segment with ffmpeg
print("\nEncoding video segments with fade transitions...")
seg_files = []
fade_dur = 0.5
for idx, (png_path, dur) in enumerate(slide_files):
    seg_mp4 = os.path.join(SCRATCH, f"seg_{idx:02d}.mp4")
    fade_out_start = dur - fade_dur
    vf = f"fade=t=in:st=0:d={fade_dur}:color=black,fade=t=out:st={fade_out_start}:d={fade_dur}:color=black"
    cmd = [
        FFMPEG, '-y',
        '-loop', '1', '-i', png_path,
        '-t', str(dur),
        '-vf', vf,
        '-r', str(FPS),
        '-pix_fmt', 'yuv420p',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '18',
        seg_mp4
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    seg_files.append(seg_mp4)
    print(f"  Encoded seg_{idx:02d}.mp4")

# Concatenate all segments
print("\nConcatenating segments into final demo video...")
concat_list = os.path.join(SCRATCH, 'concat_final.txt')
with open(concat_list, 'w', encoding='utf-8') as f:
    for seg in seg_files:
        f.write(f"file '{seg}'\n")

cmd_concat = [
    FFMPEG, '-y',
    '-f', 'concat', '-safe', '0',
    '-i', concat_list,
    '-c', 'copy',
    OUT_VIDEO
]
subprocess.run(cmd_concat, capture_output=True, check=True)

# Check output properties
dur_proc = subprocess.run([FFMPEG, '-i', OUT_VIDEO], capture_output=True, text=True)
dur_str = "Unknown"
for line in dur_proc.stderr.split('\n'):
    if "Duration:" in line:
        dur_str = line.strip()
        break

size_mb = os.path.getsize(OUT_VIDEO) / (1024 * 1024)
print(f"\nSUCCESS: Created {OUT_VIDEO}")
print(f"  File Size: {size_mb:.2f} MB")
print(f"  Properties: {dur_str}")
