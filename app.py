import os
import re
import json
import time
import requests
import io
import base64
import math
from datetime import datetime, timedelta
import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
from PIL import Image, ImageFilter, ImageDraw, ImageFont, ImageEnhance, ImageOps

# مكتبات الفيديو والصوت
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import ImageClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips as concat_video_clips
import moviepy.video.fx as vfx
import yt_dlp

import arabic_reshaper
from bidi.algorithm import get_display

import config

# =========================================================
# 1. إعداد الصفحة ونظام حفظ واسترجاع الإعدادات الدائم
# =========================================================
st.set_page_config(page_title=config.PAGE_TITLE, page_icon=config.PAGE_ICON, layout="wide")

current_channels = config.load_and_sync_channels()

if not os.path.exists(config.DEFAULT_LOGO_PATH):
    Image.new('RGBA', (200, 200), color=(255, 75, 75, 255)).save(config.DEFAULT_LOGO_PATH)
if not os.path.exists(config.ACTIVE_LOGO_PATH):
    Image.open(config.DEFAULT_LOGO_PATH).save(config.ACTIVE_LOGO_PATH)

SETTINGS_FILE = os.path.join(config.BASE_DIR, "user_settings.json")

# الإعدادات الافتراضية
DEFAULT_SETTINGS = {
    "l_pos": "فوق يمين (Top-Right)",
    "l_ox": 0, "l_oy": 0,
    "logo_opacity": 0.8,
    "logo_fit_auto": False,
    "logo_custom_w": 200, 
    "logo_custom_h": 200,
    "b_pos": "تحت شمال (Bottom-Left)",
    "b_ox": 0, "b_oy": 0,
    "b_sc": 0.035, "b_cl": "#FFD700",
    "e_pos": "تحت يمين (Bottom-Right)",
    "e_ox": 0, "e_oy": 0,
    "e_sc": 0.025, "e_cl": "#FFFFFF",
    "slide_dur": 3,
    "blur_bg": True,
    "blur_val": 15,
    "enhance_opt": True,
    "sharp_val": 2.0,
    "quality_val": 95,
    "color_preset": "طبيعي (بدون فلتر)",
    "dynamic_brand_text": "Montgk Brand",
    "enable_watermark_pattern": False,
    "enable_crop": False,
    "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0,
    "contact_phone": "01000000000",
    "whatsapp_num": "201000000000",
    "fb_page_link": "https://facebook.com/yourpage",
    "store_address": "القاهرة - شحن لجميع المحافظات 🚚",
    "persistent_note": "خصم خاص 5% لطلبات الجملة الكبيرة!"
}

def load_saved_settings():
    """تحميل الإعدادات من الملف المحفوظ"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                merged = DEFAULT_SETTINGS.copy()
                merged.update(saved)
                return merged
        except:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_current_settings(settings_dict):
    """حفظ الإعدادات في ملف JSON"""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings_dict, f, ensure_ascii=False, indent=4)
        return True
    except:
        return False

# تهيئة الـ Session State
saved_opts = load_saved_settings()
for k, v in saved_opts.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "categories" not in st.session_state:
    st.session_state.categories = ["توك واكسسوارات", "خردوات", "استانليس", "بلاستيكات", "شغل مواسم"]

if "catalog" not in st.session_state:
    st.session_state.catalog = []

if "cached_posts" not in st.session_state:
    st.session_state["cached_posts"] = []

# قاعدة بيانات الهاشتاجات حسب الصنف + التريند
CATEGORY_HASHTAGS = {
    "توك واكسسوارات": ["#توك_شعر", "#اكسسوارات_بنات", "#توك_اطفال", "#موضة_بنات", "#اكسسوارات_جملة", "#هدايا_بنات"],
    "خردوات": ["#خردوات", "#أدوات_منزلية", "#مستلزمات_بيت", "#تجهيز_عرائس", "#خردوات_جملة", "#أدوات_المطبخ"],
    "استانليس": ["#استانليس", "#استانلس_ستيل", "#مطبخ_حديث", "#أدوات_مطبخ", "#تجهيزات_مطابخ", "#جودة_عالية"],
    "بلاستيكات": ["#بلاستيكات", "#أدوات_بلاستيكية", "#منظمات_منزلية", "#مستلزمات_منزل", "#بلاستيكات_جملة"],
    "شغل مواسم": ["#شغل_مواسم", "#عروض_المواسم", "#تخفيضات_حصري", "#تجهيزات_العيد", "#منتجات_موسمية", "#عروض_خاصة"]
}
TRENDING_HASHTAGS = ["#مصر", "#تجارة_جملة", "#شحن_لجميع_المحافظات", "#توصيل_سريع", "#أونلاين_شوبينج", "#تسوق_الان", "#عروض_اليوم"]

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .web-banner {
        background: linear-gradient(135deg, #111115 0%, #ff4b4b 100%);
        padding: 30px;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0px 6px 20px rgba(255, 75, 75, 0.4);
        margin-bottom: 25px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .banner-title { color: #ffffff; font-size: 36px; font-weight: bold; margin-bottom: 5px; }
    .banner-subtitle { color: #e0e0e0; font-size: 22px; font-weight: 500; margin-bottom: 10px; }
    .banner-footer { color: #ffffff; background: rgba(0, 0, 0, 0.5); padding: 6px 18px; border-radius: 20px; display: inline-block; font-size: 14px; font-weight: bold; }
    .product-card {
        background-color: #1a1c23;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        border: 1px solid #2d323e;
        margin-bottom: 15px;
        color: #ffffff;
    }
    .post-box {
        background-color: #1e222d;
        border-right: 5px solid #1877f2;
        padding: 15px;
        border-radius: 8px;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        white-space: pre-wrap;
        color: #ffffff;
    }
    .status-ok { color: #28a745; font-weight: bold; }
    .status-low { color: #ffc107; font-weight: bold; }
    .status-out { color: #dc3545; font-weight: bold; }
    div[data-baseweb="popover"], div[data-baseweb="menu"] { z-index: 999999 !important; }
    </style>
""", unsafe_allow_html=True)

st.markdown(f"""
    <div class="web-banner">
        <div class="banner-title">🥷 Mr:- Bo0</div>
        <div class="banner-subtitle">{config.BRAND_NAME_AR}</div>
        <div class="banner-footer">🛸 Bo0's All-In-One Unified Factory & Marketing Suite</div>
    </div>
""", unsafe_allow_html=True)

# =========================================================
# 2. الدوال المساعدة والتعديل
# =========================================================
def apply_color_preset(pil_img, preset_name):
    if preset_name == "زاهي ومشرق (Vibrant Product)":
        pil_img = ImageEnhance.Color(pil_img).enhance(1.35)
        pil_img = ImageEnhance.Contrast(pil_img).enhance(1.1)
    elif preset_name == "تباين دافئ (Warm Pop)":
        pil_img = ImageEnhance.Color(pil_img).enhance(1.15)
        pil_img = ImageEnhance.Brightness(pil_img).enhance(1.05)
    elif preset_name == "سينمائي داكن (Cinematic Dark)":
        pil_img = ImageEnhance.Contrast(pil_img).enhance(1.25)
        pil_img = ImageEnhance.Brightness(pil_img).enhance(0.9)
    elif preset_name == "أبيض وأسود فاخر (Black & White)":
        pil_img = ImageOps.grayscale(pil_img).convert("RGBA")
    return pil_img

def get_arabic_font(font_size=24):
    for folder_name in ["Cairo", "cairo"]:
        if os.path.exists(folder_name) and os.path.isdir(folder_name):
            files = [f for f in os.listdir(folder_name) if f.lower().endswith('.ttf')]
            if files:
                font_path = os.path.join(folder_name, files[0])
                try: return ImageFont.truetype(font_path, font_size)
                except: pass
    font_dir = os.path.join(os.path.expanduser("~"), ".fonts")
    os.makedirs(font_dir, exist_ok=True)
    font_path = os.path.join(font_dir, "Cairo-Bold.ttf")
    if not os.path.exists(font_path):
        try:
            url = "https://github.com/google/fonts/raw/main/ofl/cairo/Cairo-Bold.ttf"
            r = requests.get(url, timeout=15)
            with open(font_path, "wb") as f: f.write(r.content)
        except: return None
    try: return ImageFont.truetype(font_path, font_size)
    except: return None

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def calculate_element_position(img_w, img_h, elem_w, elem_h, pos_mode, off_x, off_y):
    x, y = 15, 15
    if pos_mode == "فوق يمين (Top-Right)":
        x = img_w - elem_w - 15 - off_x
        y = 15 + off_y
    elif pos_mode == "فوق شمال (Top-Left)":
        x = 15 + off_x
        y = 15 + off_y
    elif pos_mode == "في المنتصف تماماً (Center)":
        x = (img_w - elem_w) // 2 + off_x
        y = (img_h - elem_h) // 2 + off_y
    elif pos_mode == "تحت يمين (Bottom-Right)":
        x = img_w - elem_w - 15 - off_x
        y = img_h - elem_h - 15 - off_y
    elif pos_mode == "تحت شمال (Bottom-Left)":
        x = 15 + off_x
        y = img_h - elem_h - 15 - off_y
    return int(max(0, min(x, img_w - elem_w))), int(max(0, min(y, img_h - elem_h)))

def draw_single_custom_text(img, text, font, fill_color, pos_mode, off_x, off_y):
    if not text.strip(): return
    draw = ImageDraw.Draw(img)
    w, h = img.size
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    
    if hasattr(font, 'getbbox'):
        bbox = font.getbbox(bidi_text)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    else:
        text_w, text_h = draw.textsize(bidi_text, font=font)
        
    pad_x, pad_y = 20, 12
    box_w, box_h = text_w + (pad_x * 2), text_h + (pad_y * 2)
    bx, by = calculate_element_position(w, h, box_w, box_h, pos_mode, off_x, off_y)
    
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle([bx, by, bx + box_w, by + box_h], radius=10, fill=(0, 0, 0, 140))
    img.alpha_composite(overlay)
    
    draw = ImageDraw.Draw(img)
    text_position = (bx + pad_x, by + pad_y - 2)
    draw.text((text_position[0] + 2, text_position[1] + 2), bidi_text, fill=(0, 0, 0, 220), font=font)
    draw.text(text_position, bidi_text, fill=fill_color, font=font)

def apply_watermark_pattern(img, text="MONTGK"):
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    font = get_arabic_font(22)
    for x in range(0, img.width, 220):
        for y in range(0, img.height, 160):
            draw.text((x, y), text, font=font, fill=(255, 255, 255, 25))
    return Image.alpha_composite(img, overlay)

def generate_smart_ai_description(raw_text):
    clean = re.sub(r'http[s]?://\S+|www\.\S+', '', raw_text)
    clean = re.sub(r'#\w+', '', clean)
    clean = re.sub(r'01[0125]\d{8}', '', clean)
    clean = re.sub(r'\d+\s*(?:شارع|طريق|ميدان|دور|شقة|مكرر)', '', clean)
    words = [w for w in clean.split() if not w.isdigit()]
    base_description = " ".join(words[:25])
    return (
        f"✨ **اللقطة اللي مستنيها وصلت!** ✨\n"
        f"🔥 {base_description} 🔥\n"
        f"شغل مستورد فاخر وخامات توب التوب، جبناهالك لحد عندك بأعلى جودة وأقل سعر في مصر عشان تكتسح السوق وتنافس بثقة! 😉👑"
    )

def generate_auto_hashtags(product_name):
    clean_name = re.sub(r'[^\w\s]', '', product_name).strip().replace(" ", "_")
    base_tags = ["#عروض_مصر", "#تسوق_اونلاين", "#تخفيضات", "#منتجات_تريند", "#توصيل_سريع"]
    if clean_name: base_tags.insert(0, f"#{clean_name}")
    return " ".join(base_tags)

def enhance_image_quality(pil_img, sharpness_factor=2.0):
    if sharpness_factor > 0:
        pil_img = ImageEnhance.Sharpness(pil_img).enhance(1.0 + sharpness_factor)
    return ImageEnhance.Contrast(pil_img).enhance(1.15)

def apply_image_crop(pil_img, c_left, c_top, c_right, c_bottom):
    w, h = pil_img.size
    return pil_img.crop((min(c_left, w - 1), min(c_top, h - 1), max(w - c_right, c_left + 1), max(h - c_bottom, c_top + 1)))

def process_image_template(image_path, blur_background=True, blur_intensity=12, opacity_val=0.8, 
                           fit_auto_logo=False, logo_custom_w=200, logo_custom_h=200,
                           brand_text_scale=0.035, brand_color="#FFD700", brand_pos="تحت شمال (Bottom-Left)", brand_off_x=0, brand_off_y=0,
                           extra_text="", extra_text_scale=0.025, extra_color="#FFFFFF", extra_pos="تحت يمين (Bottom-Right)", extra_off_x=0, extra_off_y=0,
                           target_size=None, enhance_quality=True, sharpness_val=2.0, quality_val=95, logo_pos_mode="فوق يمين (Top-Right)", logo_off_x=0, logo_off_y=0,
                           enable_watermark_pattern=False, color_preset="طبيعي (بدون فلتر)",
                           enable_crop=False, c_left=0, c_top=0, c_right=0, c_bottom=0):
    
    img = Image.open(image_path).convert("RGBA")
    if enable_crop and (c_left > 0 or c_top > 0 or c_right > 0 or c_bottom > 0):
        img = apply_image_crop(img, c_left, c_top, c_right, c_bottom)

    img = apply_color_preset(img, color_preset)
    if enhance_quality: img = enhance_image_quality(img, sharpness_val)

    if target_size:
        tw, th = target_size
        if blur_background:
            bg = img.copy().resize((tw, th), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=blur_intensity))
            bg = Image.alpha_composite(bg, Image.new("RGBA", (tw, th), (0, 0, 0, 50)))
        else:
            bg = Image.new("RGBA", target_size, (14, 17, 23, 255))
        fg = img.copy()
        fg.thumbnail((tw, th), Image.Resampling.LANCZOS)
        bg.paste(fg, ((tw - fg.size[0]) // 2, (th - fg.size[1]) // 2), fg)
        img = bg
    else:
        if blur_background:
            w, h = img.size
            bg = img.copy().filter(ImageFilter.GaussianBlur(radius=blur_intensity))
            bg = Image.alpha_composite(bg, Image.new("RGBA", (w, h), (0, 0, 0, 50)))
            fg = img.copy()
            fg.thumbnail((int(w * 0.9), int(h * 0.9)), Image.Resampling.LANCZOS)
            bg.paste(fg, ((w - fg.size[0]) // 2, (h - fg.size[1]) // 2), fg)
            img = bg

    w, h = img.size
    if os.path.exists(config.ACTIVE_LOGO_PATH):
        logo = Image.open(config.ACTIVE_LOGO_PATH).convert("RGBA")
        if fit_auto_logo:
            logo.thumbnail((int(w * (logo_custom_w / 1000.0)), int(h * (logo_custom_h / 1000.0))), Image.Resampling.LANCZOS)
        else:
            logo = logo.resize((max(10, logo_custom_w), max(10, logo_custom_h)), Image.Resampling.LANCZOS)
        r, g, b, a = logo.split()
        logo_transparent = Image.merge("RGBA", (r, g, b, a.point(lambda p: int(p * opacity_val))))
        lx, ly = calculate_element_position(w, h, logo.size[0], logo.size[1], logo_pos_mode, logo_off_x, logo_off_y)
        img.paste(logo_transparent, (lx, ly), logo_transparent)

    base_brand_text = st.session_state.get("dynamic_brand_text", "Montgk Brand")
    b_font = get_arabic_font(max(14, int(h * brand_text_scale)))
    if b_font: draw_single_custom_text(img, base_brand_text, b_font, hex_to_rgb(brand_color) + (255,), brand_pos, brand_off_x, brand_off_y)

    if extra_text.strip():
        e_font = get_arabic_font(max(12, int(h * extra_text_scale)))
        if e_font: draw_single_custom_text(img, extra_text, e_font, hex_to_rgb(extra_color) + (255,), extra_pos, extra_off_x, extra_off_y)

    if enable_watermark_pattern: img = apply_watermark_pattern(img, base_brand_text)

    out_img_path = os.path.join(config.TMP_DIR, f"templated_{os.path.basename(image_path)}")
    img.convert("RGB").save(out_img_path, "JPEG", quality=int(quality_val))
    return out_img_path

def create_image_collage(image_paths, target_size=(1080, 1080)):
    num_images = len(image_paths)
    collage_img = Image.new('RGB', target_size, color=(14, 17, 23))
    cols = 2 if num_images <= 4 else 3
    rows = math.ceil(num_images / cols)
    cell_w, cell_h = target_size[0] // cols, target_size[1] // rows
    
    for idx, p in enumerate(image_paths[:cols*rows]):
        im = Image.open(p)
        im.thumbnail((cell_w - 10, cell_h - 10), Image.Resampling.LANCZOS)
        x_offset = (idx % cols) * cell_w + (cell_w - im.size[0]) // 2
        y_offset = (idx // cols) * cell_h + (cell_h - im.size[1]) // 2
        collage_img.paste(im, (x_offset, y_offset))
        
    out_collage_path = os.path.join(config.TMP_DIR, "montgk_collage_output.jpg")
    collage_img.save(out_collage_path, "JPEG", quality=95)
    return out_collage_path

def download_from_link(url):
    output_template = 'web_input.mp4'
    if os.path.exists(output_template): os.remove(output_template)
    ydl_opts = {'format': 'best[ext=mp4]/best', 'outtmpl': output_template, 'quiet': True, 'nocheckcertificate': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
    return output_template

def check_if_single_piece_text(text):
    single_piece_keywords = ["سعر القطعه", "سعر القطعة", "سعر الحته", "سعر الحتة", "السعر للقطعه", "الواحدة", "سعر الواحدة"]
    for kw in single_piece_keywords:
        if kw in text: return True
    return False

def extract_original_price_only(text, max_limit=None, custom_keywords_str="", exclude_keywords_str=""):
    clean_text = re.sub(r'01[0125]\d{8}', '', text)
    clean_text = re.sub(r'\d+\s*(?:شارع|طريق|ميدان|دور|شقة|مكرر)', '', clean_text)
    default_exclude = ["كود", "موديل", "عام", "سنة", "تواصل", "رقم"]
    if exclude_keywords_str.strip(): default_exclude.extend([w.strip() for w in exclude_keywords_str.split(",") if w.strip()])
    for ex_word in default_exclude:
        clean_text = re.sub(re.escape(ex_word) + r'\s*[:\-=\s]*\s*\d+', '', clean_text, flags=re.IGNORECASE)
    all_keywords = list(config.PRICE_KEYWORDS)
    if custom_keywords_str.strip(): all_keywords.extend([w.strip() for w in custom_keywords_str.split(",") if w.strip()])
    for kw in all_keywords:
        for match in re.finditer(re.escape(kw) + r'\s*[:\-=\s]*\s*(\d+)', clean_text):
            val = int(match.group(1))
            if not max_limit or val <= max_limit: return val, match.group(1)
    for num_str in re.findall(r'\d+', clean_text):
        val = int(num_str)
        if (not max_limit or val <= max_limit) and val < 50000: return val, num_str
    return 0, ""

def fetch_egypt_trends(category="الكل"):
    trends_data = {
        "الكل": {
            "products": ["ساعات سمارت Smart Watches", "ماكينات حلاقة رجالي", "سماعات ايربودز Wireless", "حقائب واكسسوارات جلدية", "أجهزة تحضير القهوة"],
            "hashtags": ["#عروض_مصر", "#تريند_اليوم", "#تسوق_اونلاين", "#تخفيضات_مصر", "#منتجات_تريند"]
        },
        "أزياء وموضة": {
            "products": ["ملابس صيفية خفيفة", "أحذية رياضية Sneaker", "نظارات شمسية قطبية", "ملابس رياضية Gymwear"],
            "hashtags": ["#موضة_مصر", "#أزياء_2026", "#ستايل_مصر", "#عروض_الملابس"]
        },
        "إلكترونيات": {
            "products": ["باور بنك سريع الشحن", "ستاند موبايل تصوير", "سماعات بلوتوث رأس", "شواحن آيفون وسامسونج"],
            "hashtags": ["#إلكترونيات_مصر", "#اكسسوارات_موبايل", "#تكنولوجيا", "#عروض_الهواتف"]
        }
    }
    return trends_data.get(category, trends_data["الكل"])

def generate_post_template(body_text, category, selected_product):
    trends_info = fetch_egypt_trends(category)
    hashtags_str = " ".join(trends_info["hashtags"])
    brand_name = st.session_state.get("dynamic_brand_text", "متجرنا")
    return f"""🔥 **{brand_name} - عرض خاص لفترة محدودة!** 🔥\n\n📌 **المنتج الأكثر طلباً الآن:** {selected_product}\n\n{body_text}\n\n⚡ **ليه تشتري من {brand_name}؟**\n✅ جودة ممتازة مضمونة 100%\n✅ توصيل سريع لجميع المحافظات 🇪🇬\n✅ معاينة المنتج قبل الاستلام والادفع عند الاستلام\n\n📲 **للطلب أو الاستفسار:** ارسل لنا رسالة الآن!\n---\n{hashtags_str}"""

# =========================================================
# 3. الشريط الجانبي لوحة التحكم الشاملة 🛰️
# =========================================================
with st.sidebar:
    st.markdown("<h2 style='color:#ff4b4b;'>🛰️ ترسانة السيطرة والتوقيت</h2>", unsafe_allow_html=True)
    
    c_save, c_reset = st.columns(2)
    with c_save:
        if st.button("💾 حفظ الإعدادات"):
            # تجميع وحفظ كافة الإعدادات
            current_settings = {
                "l_pos": st.session_state.get("l_pos", DEFAULT_SETTINGS["l_pos"]),
                "l_ox": st.session_state.get("l_ox", DEFAULT_SETTINGS["l_ox"]),
                "l_oy": st.session_state.get("l_oy", DEFAULT_SETTINGS["l_oy"]),
                "logo_opacity": st.session_state.get("logo_opacity", DEFAULT_SETTINGS["logo_opacity"]),
                "logo_fit_auto": st.session_state.get("logo_fit_auto", DEFAULT_SETTINGS["logo_fit_auto"]),
                "logo_custom_w": st.session_state.get("logo_custom_w", DEFAULT_SETTINGS["logo_custom_w"]),
                "logo_custom_h": st.session_state.get("logo_custom_h", DEFAULT_SETTINGS["logo_custom_h"]),
                "b_pos": st.session_state.get("b_pos", DEFAULT_SETTINGS["b_pos"]),
                "b_ox": st.session_state.get("b_ox", DEFAULT_SETTINGS["b_ox"]),
                "b_oy": st.session_state.get("b_oy", DEFAULT_SETTINGS["b_oy"]),
                "b_sc": st.session_state.get("b_sc", DEFAULT_SETTINGS["b_sc"]),
                "b_cl": st.session_state.get("b_cl", DEFAULT_SETTINGS["b_cl"]),
                "e_pos": st.session_state.get("e_pos", DEFAULT_SETTINGS["e_pos"]),
                "e_ox": st.session_state.get("e_ox", DEFAULT_SETTINGS["e_ox"]),
                "e_oy": st.session_state.get("e_oy", DEFAULT_SETTINGS["e_oy"]),
                "e_sc": st.session_state.get("e_sc", DEFAULT_SETTINGS["e_sc"]),
                "e_cl": st.session_state.get("e_cl", DEFAULT_SETTINGS["e_cl"]),
                "blur_bg": st.session_state.get("blur_bg", DEFAULT_SETTINGS["blur_bg"]),
                "blur_val": st.session_state.get("blur_val", DEFAULT_SETTINGS["blur_val"]),
                "enhance_opt": st.session_state.get("enhance_opt", DEFAULT_SETTINGS["enhance_opt"]),
                "sharp_val": st.session_state.get("sharp_val", DEFAULT_SETTINGS["sharp_val"]),
                "quality_val": st.session_state.get("quality_val", DEFAULT_SETTINGS["quality_val"]),
                "color_preset": st.session_state.get("color_preset", DEFAULT_SETTINGS["color_preset"]),
                "dynamic_brand_text": st.session_state.get("dynamic_brand_text", DEFAULT_SETTINGS["dynamic_brand_text"]),
                "enable_watermark_pattern": st.session_state.get("enable_watermark_pattern", DEFAULT_SETTINGS["enable_watermark_pattern"]),
                "enable_crop": st.session_state.get("enable_crop", DEFAULT_SETTINGS["enable_crop"]),
                "crop_left": st.session_state.get("crop_left", DEFAULT_SETTINGS["crop_left"]),
                "crop_top": st.session_state.get("crop_top", DEFAULT_SETTINGS["crop_top"]),
                "crop_right": st.session_state.get("crop_right", DEFAULT_SETTINGS["crop_right"]),
                "crop_bottom": st.session_state.get("crop_bottom", DEFAULT_SETTINGS["crop_bottom"]),
                "contact_phone": st.session_state.get("contact_phone", DEFAULT_SETTINGS["contact_phone"]),
                "whatsapp_num": st.session_state.get("whatsapp_num", DEFAULT_SETTINGS["whatsapp_num"]),
                "fb_page_link": st.session_state.get("fb_page_link", DEFAULT_SETTINGS["fb_page_link"]),
                "store_address": st.session_state.get("store_address", DEFAULT_SETTINGS["store_address"]),
                "persistent_note": st.session_state.get("persistent_note", DEFAULT_SETTINGS["persistent_note"])
            }
            if save_current_settings(current_settings):
                st.success("✅ تم حفظ التفضيلات بشكل دائم!")
            else:
                st.error("فشل حفظ التفضيلات.")

    with c_reset:
        if st.button("🔄 إرجاع للافتراضي"):
            if os.path.exists(SETTINGS_FILE):
                os.remove(SETTINGS_FILE)
            for k, v in DEFAULT_SETTINGS.items(): st.session_state[k] = v
            st.rerun()

    st.write("---")
    st.markdown("### 🎨 فلاتر الألوان الذكية الخفيفة")
    color_preset = st.selectbox(
        "اختر فلتر لتحسين الصورة:",
        ["طبيعي (بدون فلتر)", "زاهي ومشرق (Vibrant Product)", "تباين دافئ (Warm Pop)", "سينمائي داكن (Cinematic Dark)", "أبيض وأسود فاخر (Black & White)"],
        key="color_preset"
    )

    st.write("---")
    st.markdown("### 📐 أبعاد وهندسة قوالب المنصات")
    platform_dimension = st.selectbox(
        "اختر مقاس منصة العرض المستهدفة:",
        ["تلقائي (حجم الملف الأصلي)", "تيك توك / ريلز (9:16 - 1080x1920)", "يوتيوب عريض (16:9 - 1920x1080)", "فيسبوك وانستجرام مربع (1:1 - 1080x1080)"]
    )
    dim_map = {
        "تلقائي (حجم الملف الأصلي)": None,
        "تيك توك / ريلز (9:16 - 1080x1920)": (1080, 1920),
        "يوتيوب عريض (16:9 - 1920x1080)": (1920, 1080),
        "فيسبوك وانستجرام مربع (1:1 - 1080x1080)": (1080, 1080)
    }
    chosen_size = dim_map[platform_dimension]

    st.write("---")
    st.markdown("### 🎯 1. التحكم في حجم ومكان اللوجو المائي")
    logo_position_choice = st.selectbox("مكان اللوجو:", ["فوق يمين (Top-Right)", "فوق شمال (Top-Left)", "في المنتصف تماماً (Center)", "تحت يمين (Bottom-Right)", "تحت شمال (Bottom-Left)"], key="l_pos")
    logo_offset_x = st.slider("زق اللوجو أفقي (X):", -300, 300, key="l_ox")
    logo_offset_y = st.slider("زق اللوجو رأسي (Y):", -300, 300, key="l_oy")
    logo_opacity = st.slider("شفافية اللوجو:", 0.1, 1.0, key="logo_opacity")
    fit_auto_logo = st.checkbox("التكيف التلقائي مع أبعاد الصورة (Auto Fit)", key="logo_fit_auto")
    
    c_lw, c_lh = st.columns(2)
    with c_lw: logo_custom_w = st.slider("عرض اللوجو (px):", 10, 1000, key="logo_custom_w")
    with c_lh: logo_custom_h = st.slider("ارتفاع اللوجو (px):", 10, 1000, key="logo_custom_h")

    st.write("---")
    st.markdown("### 🏷️ 2. التحكم في اسم البراند")
    input_brand_text = st.text_input("نص البراند:", key="dynamic_brand_text")
    brand_position_choice = st.selectbox("مكان اسم البراند:", ["تحت شمال (Bottom-Left)", "تحت يمين (Bottom-Right)", "فوق شمال (Top-Left)", "فوق يمين (Top-Right)", "في المنتصف تماماً (Center)"], key="b_pos")
    brand_offset_x = st.slider("زق البراند أفقي (X):", -300, 300, key="b_ox")
    brand_offset_y = st.slider("زق البراند رأسي (Y):", -300, 300, key="b_oy")
    brand_text_scale = st.slider("حجم خط البراند:", 0.015, 0.080, key="b_sc")
    brand_color = st.color_picker("لون خط البراند:", key="b_cl")

    st.write("---")
    st.markdown("### ✍️ 3. الجملة الإضافية المخصصة")
    extra_brand_suffix = st.text_input("الجملة الإضافية:", value="", placeholder="مثال: Premium Quality")
    extra_position_choice = st.selectbox("مكان الجملة الإضافية:", ["تحت يمين (Bottom-Right)", "تحت شمال (Bottom-Left)", "فوق يمين (Top-Right)", "فوق شمال (Top-Left)", "في المنتصف تماماً (Center)"], key="e_pos")
    extra_offset_x = st.slider("زق الجملة أفقي (X):", -300, 300, key="e_ox")
    extra_offset_y = st.slider("زق الجملة رأسي (Y):", -300, 300, key="e_oy")
    extra_text_scale = st.slider("حجم خط الجملة:", 0.010, 0.060, key="e_sc")
    extra_color = st.color_picker("لون خط الجملة:", key="e_cl")

    st.write("---")
    st.markdown("### ⏱️ 4. التسريع والمدة الزمانية الذكية")
    time_control_mode = st.radio("طريقة تحديد وقت فيديو الصور:", ["مدة محددة لكل صورة", "وقت إجمالي مستهدف للفيديو كامل"])
    if time_control_mode == "مدة محددة لكل صورة":
        image_duration_per_slide = st.slider("مدة عرض الصورة (بالثواني):", min_value=1, max_value=10, value=3)
        total_target_video_duration = None
    else:
        total_target_video_duration = st.slider("المدة الإجمالية المستهدفة للفيديو (بالثواني):", min_value=5, max_value=60, value=15)
        image_duration_per_slide = 3

    st.write("---")
    st.markdown("### 🖼️ 5. فلاتر الصور، الجودة والقص")
    blur_bg_opt = st.checkbox("تفعيل خلفية Blur من نفس الصورة", key="blur_bg")
    blur_intensity_val = st.slider("قوة تغبيش الخلفية (Blur Radius):", 1, 30, key="blur_val")
    enhance_quality_opt = st.checkbox("تفعيل فلتر الجودة والحدة 🚀", key="enhance_opt")
    sharpness_slider_val = st.slider("مستوى حدة التفاصيل (Sharpness):", 0.0, 5.0, key="sharp_val")
    quality_slider_val = st.slider("نسبة جودة الضغط (Quality %):", 10, 100, key="quality_val")
    protect_watermark = st.checkbox("إضافة علامة مائية شبكية لحماية الصور", key="enable_watermark_pattern")
    
    st.markdown("#### ✂️ أداة قص الصور (Crop)")
    enable_crop_opt = st.checkbox("تفعيل قص أطراف الصور (Crop)", key="enable_crop")
    if enable_crop_opt:
        crop_l = st.slider("قص من اليسار (Left px):", 0, 500, key="crop_left")
        crop_t = st.slider("قص من الأعلى (Top px):", 0, 500, key="crop_top")
        crop_r = st.slider("قص من اليمين (Right px):", 0, 500, key="crop_right")
        crop_b = st.slider("قص من الأسفل (Bottom px):", 0, 500, key="crop_bottom")
    else:
        crop_l = crop_t = crop_r = crop_b = 0

    if os.path.exists(config.ACTIVE_LOGO_PATH):
        st.image(config.ACTIVE_LOGO_PATH, caption="اللوجو النشط", width=100)
    uploaded_logo = st.file_uploader("تغيير اللوجو:", type=["png", "jpg", "jpeg"])
    if uploaded_logo is not None:
        Image.open(uploaded_logo).save(config.ACTIVE_LOGO_PATH)
        st.success("✅ تم التحديث!")
        st.rerun()

    st.write("---")
    audio_mode = st.radio("مصدر الصوت:", ["تراك المزيكا الحصري التلقائي", "رفع تراك أوديو MP3 مخصص"])
    uploaded_custom_audio = None
    if audio_mode == "رفع تراك أوديو MP3 مخصص":
        uploaded_custom_audio = st.file_uploader("ارفع الأوديو:", type=["mp3", "wav", "ogg"])

    st.divider()
    st.header("📞 بيانات التواصل الثابتة")
    contact_phone = st.text_input("رقم الهاتف:", key="contact_phone")
    whatsapp_num = st.text_input("رقم الواتساب:", key="whatsapp_num")
    fb_page_link = st.text_input("رابط الفيسبوك:", key="fb_page_link")
    store_address = st.text_input("العنوان / الشحن:", key="store_address")

    st.divider()
    persistent_note = st.text_area("📌 نص ثابت إضافي في البوستات:", key="persistent_note")

# =========================================================
# 4. التبويبات الشاملة المدمجة بالكامل 🔥
# =========================================================
main_tab1, main_tab2, main_tab3, main_tab4, main_tab5, main_tab6 = st.tabs([
    "🎬 تشفير ومونتاج الفيديو", 
    "🖼️ قوالب ألبومات الصور والسلايد شو", 
    "🛰️ رادار القنوات والـ Forward",
    "📦 إضافة المنتجات والمخزون",
    "📲 مولّد البوستات والعروض",
    "📖 الكتالوج وتصدير PDF/Excel"
])

# ---------------------------------------------------------
# TAB 1: تشفير وتقطيع ومونتاج الفيديو
# ---------------------------------------------------------
with main_tab1:
    st.subheader("🚀 منصة تسريع، تقطيع ومونتاج الفيديو الذكي")
    option = st.radio("إدخال الفيديو:", ("لصق رابط فيديو (يوتيوب، فيسبوك، تيك توك)", "رفع ملف فيديو مباشر من جهازك"), key="vid_option")
    input_path = "web_input.mp4"
    output_path = "Bo0sViDClone_web_output.mp4"
    ready_to_process = False

    st.markdown("#### ✂️ 1. أداة قص وتقطيع جزء معين من الفيديو (Trimmer)")
    enable_trim = st.checkbox("تفعيل قص جزء محدد من الفيديو", value=False)
    c_t1, c_t2 = st.columns(2)
    with c_t1: trim_start = st.number_input("بداية القص (بالثواني):", min_value=0, value=0)
    with c_t2: trim_end = st.number_input("نهاية القص (بالثواني - 0 للكل):", min_value=0, value=0)

    st.markdown("#### ⚡ 2. ضبط السرعة والمدّة المستهدفة للفيديو")
    speed_mode = st.radio("طريقة معالجة مدة الفيديو:", ["تسريع / تبطيء يدوي", "مُطابقة تلقائية مع مدة مستهدفة (Smart Speed-up)"])
    if speed_mode == "تسريع / تبطيء يدوي":
        manual_speed_factor = st.slider("مُعامل السرعة (1.0 عادي | 2.0 أسرع مرتين):", 0.5, 4.0, 1.0)
    else:
        target_video_duration_sec = st.slider("المدة النهائية المستهدفة للفيديو (بالثواني):", 5, 120, 15)

    if option == "لصق رابط فيديو (يوتيوب، فيسبوك، تيك توك)":
        url = st.text_input("ضع الرابط:", placeholder="https://...", key="vid_url")
        if url and re.match(r'http[s]?://', url):
            if st.button("🚀 ابدأ معالجة وتقطيع الفيديو"):
                with st.spinner("جاري سحب المحتوى..."):
                    try:
                        downloaded_file = download_from_link(url)
                        if os.path.exists(input_path): os.remove(input_path)
                        os.rename(downloaded_file, input_path)
                        ready_to_process = True
                    except Exception as e: st.error(f"خطأ في السحب: {str(e)}")
    else:
        uploaded_file = st.file_uploader("اسحب الفيديو هنا", type=["mp4", "mov", "avi"], key="vid_file")
        if uploaded_file is not None and st.button("⚙️ ابدأ معالجة وتقطيع الفيديو"):
            with st.spinner("جاري تهيئة الملف..."):
                if os.path.exists(input_path): os.remove(input_path)
                with open(input_path, "wb") as f: f.write(uploaded_file.read())
                ready_to_process = True

    if ready_to_process:
        with st.spinner("⚡ جاري تقطيع، تسريع ورندرة الفيديو..."):
            try:
                clip = VideoFileClip(input_path)
                if enable_trim:
                    end_val = clip.duration if trim_end <= 0 or trim_end > clip.duration else trim_end
                    clip = clip.subclip(min(trim_start, clip.duration - 1), end_val)

                if speed_mode == "مُطابقة تلقائية مع مدة مستهدفة (Smart Speed-up)":
                    calculated_speed = clip.duration / float(target_video_duration_sec)
                    if calculated_speed > 0: clip = clip.fx(vfx.speedx, calculated_speed)
                else:
                    if manual_speed_factor != 1.0: clip = clip.fx(vfx.speedx, manual_speed_factor)

                if chosen_size: clip = clip.fx(vfx.resize, width=chosen_size[0], height=chosen_size[1])
                
                modified_clip = clip.fx(vfx.colorx, 1.05)
                if audio_mode == "رفع تراك أوديو MP3 مخصص" and uploaded_custom_audio is not None:
                    temp_audio_path = os.path.join(config.TMP_DIR, "user_custom_audio.mp3")
                    with open(temp_audio_path, "wb") as f: f.write(uploaded_custom_audio.read())
                    modified_clip = modified_clip.set_audio(AudioFileClip(temp_audio_path).subclip(0, modified_clip.duration))
                elif audio_mode == "تراك المزيكا الحصري التلقائي" and os.path.exists(config.CUSTOM_AUDIO_TRACK):
                    modified_clip = modified_clip.set_audio(AudioFileClip(config.CUSTOM_AUDIO_TRACK).subclip(0, modified_clip.duration))
                
                if os.path.exists(config.ACTIVE_LOGO_PATH):
                    vx, vy = calculate_element_position(modified_clip.w, modified_clip.h, logo_custom_w, logo_custom_h, logo_position_choice, logo_offset_x, logo_offset_y)
                    logo = (ImageClip(config.ACTIVE_LOGO_PATH)
                            .set_duration(modified_clip.duration)
                            .resize(newsize=(logo_custom_w, logo_custom_h))
                            .set_pos((vx, vy))
                            .set_opacity(logo_opacity))
                    final_clip = CompositeVideoClip([modified_clip, logo])
                else: final_clip = modified_clip
                
                final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", preset="ultrafast", threads=4)
                clip.close()
                final_clip.close()
                st.success("🎉 تم المونتاج، التقطيع والتسريع بنجاح!")
                st.video(output_path)
            except Exception as e: st.error(f"حدث خطأ: {str(e)}")

# ---------------------------------------------------------
# TAB 2: ألبومات الصور والسلايد شو
# ---------------------------------------------------------
with main_tab2:
    st.subheader("🖼️ مصنع تجميل صور المنتجات وفيديوهات السلايد شو الذكية")
    uploaded_images = st.file_uploader("ارفع الصور هنا:", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    show_orig_toggle = st.checkbox("👁️ عرض الصور الأصلية (قبل التعديل للمعاينة)", value=False)

    if uploaded_images:
        if len(uploaded_images) > 1:
            album_choice = st.radio("اختر نمط التصدير:", ("📥 ألبوم صور مفرودة منفصلة", "🎬 دمجهم فيديو متحرك (Slideshow)", "🖼️ تجميع في صورة واحدة (Collage)"))
        else: album_choice = "📥 ألبوم صور مفرودة منفصلة"

        if show_orig_toggle:
            st.info("📷 الصورة الأصلية بدون إضافات:")
            for idx, img_f in enumerate(uploaded_images): st.image(img_f, caption=f"أصل صورة {idx+1}", use_container_width=True)
        else:
            if st.button("⚙️ ابدأ معالجة الصور"):
                saved_paths = []
                for i, img_file in enumerate(uploaded_images):
                    temp_p = f"temp_product_{i}.png"
                    with open(temp_p, "wb") as f: f.write(img_file.read())
                    processed_p = process_image_template(
                        temp_p, blur_background=blur_bg_opt, blur_intensity=blur_intensity_val, opacity_val=logo_opacity,
                        fit_auto_logo=fit_auto_logo, logo_custom_w=logo_custom_w, logo_custom_h=logo_custom_h,
                        brand_text_scale=brand_text_scale, brand_color=brand_color, brand_pos=brand_position_choice,
                        brand_off_x=brand_offset_x, brand_off_y=brand_offset_y,
                        extra_text=extra_brand_suffix, extra_text_scale=extra_text_scale, extra_color=extra_color,
                        extra_pos=extra_position_choice, extra_off_x=extra_offset_x, extra_off_y=extra_offset_y,
                        target_size=chosen_size, enhance_quality=enhance_quality_opt, sharpness_val=sharpness_slider_val,
                        quality_val=quality_slider_val, logo_pos_mode=logo_position_choice, logo_off_x=logo_offset_x,
                        logo_off_y=logo_offset_y, enable_watermark_pattern=protect_watermark, color_preset=color_preset,
                        enable_crop=enable_crop_opt, c_left=crop_l, c_top=crop_t, c_right=crop_r, c_bottom=crop_b
                    )
                    saved_paths.append(processed_p)
                    if os.path.exists(temp_p): os.remove(temp_p)
                
                if album_choice == "📥 ألبوم صور مفرودة منفصلة":
                    st.success("🎉 تمت المعالجة وخلفية الـ Blur واللوجو جاهزة!")
                    for idx, p in enumerate(saved_paths): st.image(p, caption=f"🖼️ منتج رقم {idx+1}", use_container_width=True)
                elif album_choice == "🖼️ تجميع في صورة واحدة (Collage)":
                    st.success("🎉 تم دمج الصور في كولاج شبكي!")
                    collage_result = create_image_collage(saved_paths, target_size=(1080, 1080) if not chosen_size else chosen_size)
                    st.image(collage_result, caption="📸 صورة الكولاج المجمعة", use_container_width=True)
                else:
                    per_slide_duration = total_target_video_duration / len(saved_paths) if (total_target_video_duration and total_target_video_duration > 0) else image_duration_per_slide
                    with st.spinner(f"🎬 جاري رندرة السلايد شو ({per_slide_duration:.1f} ثانية/صورة)..."):
                        img_clips = [ImageClip(p).set_duration(per_slide_duration) for p in saved_paths]
                        video_slideshow = concat_video_clips(img_clips, method="compose")
                        if audio_mode == "رفع تراك أوديو MP3 مخصص" and uploaded_custom_audio is not None:
                            temp_audio_p2 = os.path.join(config.TMP_DIR, "user_custom_audio_slide.mp3")
                            with open(temp_audio_p2, "wb") as f: f.write(uploaded_custom_audio.read())
                            video_slideshow = video_slideshow.set_audio(AudioFileClip(temp_audio_p2).subclip(0, video_slideshow.duration))
                        elif os.path.exists(config.CUSTOM_AUDIO_TRACK):
                            video_slideshow = video_slideshow.set_audio(AudioFileClip(config.CUSTOM_AUDIO_TRACK).subclip(0, video_slideshow.duration))
                        video_slideshow_path = "images_slideshow_output.mp4"
                        video_slideshow.write_videofile(video_slideshow_path, codec="libx264", fps=24, preset="ultrafast")
                        st.video(video_slideshow_path)

# ---------------------------------------------------------
# TAB 3: رادار القنوات والتسعير
# ---------------------------------------------------------
with main_tab3:
    st.subheader("🛰️ مركز الفحص والـ Forward وإعادة التسعير التلقائي")
    col1, col2 = st.columns(2)
    with col1: price_inc_rate = st.number_input("نسبة زيادة السعر (%):", min_value=0, max_value=100, value=config.DEFAULT_PRICE_INC_RATE)
    with col2: box_items_count = st.number_input("عدد القطع بالعلبة:", min_value=1, max_value=100, value=config.DEFAULT_BOX_ITEMS_COUNT)
    
    extra_price_keywords = st.text_input("💡 كلمات إيجابية لكشف السعر (بفاصلة ,):", placeholder="مثال: جملتها, بسعر, المطلوب, بـ")
    exclude_price_keywords = st.text_input("🛡️ كلمات مستبعدة (بفاصلة ,):", value="كود, موديل, تواصل, عام, سنة, مقاس, رقم")

    max_price_threshold = st.number_input("الحد الأقصى للسعر:", min_value=1, max_value=9999999, value=5000)
    date_filter = st.radio("النطاق الزمني:", ("اليوم فقط", "الأمس واليوم", "قبل أمس والـ 3 أيام الأخيرة", "كل البوستات المتاحة للقناة"), index=3, horizontal=True)
    
    st.write("---")
    radar_mode = st.radio("مصدر المحتوى:", ("🛰️ سحب رادار حي وفوري", "📋 إدخل يدوي لبوست معموله Forward"), key="mode_9")
    
    if radar_mode == "🛰️ سحب رادار حي وفوري":
        target_channel_input = st.selectbox("اختر القناة:", current_channels)
        if st.button("🛰️ قنص المحتوى"):
            with st.spinner("جاري السحب..."):
                try:
                    res = requests.get(f"https://t.me/s/{target_channel_input}", headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
                    if res.status_code == 200:
                        soup = BeautifulSoup(res.content, "html.parser")
                        messages = soup.find_all("div", class_=lambda x: x and 'tgme_widget_message_wrap' in x)
                        temp_collected = []
                        today_date = datetime.now().date()
                        for msg in reversed(messages):
                            text_div = msg.find("div", class_=lambda x: x and 'message_text' in x)
                            if text_div:
                                p_text = text_div.text.strip()
                                photo_url = None
                                photo_tag = msg.find("a", class_=lambda x: x and 'message_photo' in x)
                                if photo_tag:
                                    match = re.search(r"url\(['\"]?(.*?)['\"]?\)", photo_tag.get("style", ""))
                                    if match: photo_url = match.group(1)
                                if photo_url and photo_url.startswith('//'): photo_url = 'https:' + photo_url
                                auto_price, old_str = extract_original_price_only(p_text, max_limit=max_price_threshold, custom_keywords_str=extra_price_keywords, exclude_keywords_str=exclude_price_keywords)
                                temp_collected.append({"text": p_text, "image": photo_url, "auto_price": auto_price, "old_str": old_str})
                        st.session_state["cached_posts"] = temp_collected
                        st.success(f"🎯 تم قنص {len(temp_collected)} بوست!")
                except Exception as e: st.error(f"خطأ: {str(e)}")
    else:
        forwarded_text = st.text_area("نص البوست:")
        uploaded_image = st.file_uploader("الصورة:")
        if st.button("⚡ تعديل فوراً"):
            if forwarded_text:
                auto_price, old_str = extract_original_price_only(forwarded_text, max_limit=max_price_threshold, custom_keywords_str=extra_price_keywords, exclude_keywords_str=exclude_price_keywords)
                st.session_state["cached_posts"] = [{"text": forwarded_text, "image": uploaded_image, "auto_price": auto_price, "old_str": old_str}]

    if st.session_state["cached_posts"]:
        st.write("---")
        if st.button("📊 توليد شيت إكسيل Montgk"):
            excel_data_list = [{"رقم المنتج": i + 1, "اسم الصورة المائية": f"watermarked_{i+1}.jpg", "اسم المنتج": "", "السعر الجديد": "", "الوصف المقترح": ""} for i, item in enumerate(st.session_state["cached_posts"])]
            output_io = io.BytesIO()
            with pd.ExcelWriter(output_io, engine='openpyxl') as writer: pd.DataFrame(excel_data_list).to_excel(writer, index=False, sheet_name="Montgk")
            st.download_button(label="📥 تحميل Excel", data=output_io.getvalue(), file_name="Montgk_Products.xlsx")
        st.write("---")

        for idx, item in enumerate(st.session_state["cached_posts"]):
            st.markdown(f"#### 📦 منتج رقم {idx + 1}")
            if item["image"]: st.image(item["image"], width=200)
            is_single_piece = check_if_single_piece_text(item["text"])
            chosen_orig_price = st.number_input(f"✍️ السعر الأصلي {idx+1}:", min_value=0, max_value=2000000, value=int(item["auto_price"]), key=f"manual_price_{idx}")
            base_new_price = int(chosen_orig_price * (1 + (price_inc_rate / 100)))
            
            piece_p = base_new_price if is_single_piece else round(base_new_price / box_items_count, 1)
            price_status_note = f"📌 سعر القطعة واصل عليك بـ {piece_p} ج بس! 🔥"
            
            temp_post_text = re.sub(r'#\w+|http[s]?://\S+|www\.\S+', '', item["text"])
            final_clean_text = temp_post_text.replace(item["old_str"], str(base_new_price), 1) if (item["old_str"] and item["old_str"] in temp_post_text) else temp_post_text + f"\n سعر العرض الجديد: {base_new_price} ج"
            
            smart_ai_proposal = generate_smart_ai_description(item["text"])
            auto_hashtags = generate_auto_hashtags(item["text"][:15])
            
            apply_ai = st.checkbox("🔄 اعتماد الوصف الذكي؟", value=False, key=f"ai_check_{idx}")
            chosen_description = smart_ai_proposal if apply_ai else final_clean_text
            
            final_commercial_post = f"{chosen_description}\n\n{price_status_note}\n\n🎁 **خصم خاص للكميات!** 💣🔥\n\n🔗 للتواصل: {st.session_state.get('fb_page_link', '')}\n\n{auto_hashtags}"
            st.text_area(f"📋 البوست الجاهز {idx + 1}:", value=final_commercial_post, height=180, key=f"post_area_{idx}")
            st.markdown("---")

# ---------------------------------------------------------
# TAB 4: إضافة المنتجات والمخزون (مع تطبيق اللوجو أوتوماتيك)
# ---------------------------------------------------------
with main_tab4:
    st.header("📦 إضافة منتج جديد وإدارة المخزون والأرباح")
    
    auto_apply_logo_cat = st.checkbox("🎨 تطبيق إعدادات اللوجو والستايل تلقائياً على صورة المنتج عند الإضافة", value=True)
    
    col_img, col_inputs = st.columns([1, 2])

    processed_catalog_image = None

    with col_img:
        uploaded_image = st.file_uploader("ارفع صورة المنتج", type=["jpg", "png", "jpeg"], key="single_img")
        if uploaded_image:
            if auto_apply_logo_cat:
                temp_cat_p = os.path.join(config.TMP_DIR, "temp_catalog_upload.png")
                with open(temp_cat_p, "wb") as f: f.write(uploaded_image.getvalue())
                
                processed_cat_path = process_image_template(
                    temp_cat_p, blur_background=blur_bg_opt, blur_intensity=blur_intensity_val, opacity_val=logo_opacity,
                    fit_auto_logo=fit_auto_logo, logo_custom_w=logo_custom_w, logo_custom_h=logo_custom_h,
                    brand_text_scale=brand_text_scale, brand_color=brand_color, brand_pos=brand_position_choice,
                    brand_off_x=brand_offset_x, brand_off_y=brand_offset_y,
                    extra_text=extra_brand_suffix, extra_text_scale=extra_text_scale, extra_color=extra_color,
                    extra_pos=extra_position_choice, extra_off_x=extra_offset_x, extra_off_y=extra_offset_y,
                    target_size=chosen_size, enhance_quality=enhance_quality_opt, sharpness_val=sharpness_slider_val,
                    quality_val=quality_slider_val, logo_pos_mode=logo_position_choice, logo_off_x=logo_offset_x,
                    logo_off_y=logo_offset_y, enable_watermark_pattern=protect_watermark, color_preset=color_preset,
                    enable_crop=enable_crop_opt, c_left=crop_l, c_top=crop_t, c_right=crop_r, c_bottom=crop_b
                )
                processed_catalog_image = Image.open(processed_cat_path)
                st.image(processed_catalog_image, caption="معاينة الصورة المعدلة باللوجو والستايل 🔥", use_container_width=True)
            else:
                processed_catalog_image = Image.open(uploaded_image)
                st.image(uploaded_image, caption="معاينة الصورة الأصلية", use_container_width=True)

    with col_inputs:
        col1, col2 = st.columns(2)
        with col1:
            prod_name = st.text_input("اسم المنتج *")
            prod_code = st.text_input("كود المنتج")
            category = st.selectbox("تصنيف المنتج", options=st.session_state.categories)
            stock_qty = st.number_input("الكمية بالمخزن (بالقطعة)", min_value=0, value=50)

        with col2:
            cost_price = st.number_input("تكلفة القطعة عليك (سعر الشراء)", min_value=0.0, value=0.0, step=0.5)
            dozen_price = st.number_input("سعر البيع للدستة (12 قطعة)", min_value=0.0, value=0.0, step=0.5)
            unit_price = dozen_price / 12.0 if dozen_price > 0 else 0.0
            st.number_input("سعر القطعة (محسوب تلقائياً)", value=round(unit_price, 2), disabled=True)
            carton_qty = st.number_input("عدد الكرتونة", min_value=0, value=0)
            carton_price = st.number_input("سعر الكرتونة", min_value=0.0, value=0.0)

        if unit_price > 0 and cost_price > 0:
            profit_per_unit = unit_price - cost_price
            st.success(f"📈 ربح القطعة: {round(profit_per_unit, 2)} ج.م (هامش ربح: {round((profit_per_unit/unit_price)*100, 1)}%)")

    if st.button("➕ إضافة المنتج للكتالوج والمخزن", type="primary", use_container_width=True):
        if not prod_name: st.error("⚠️ يرجى إدخال اسم المنتج!")
        else:
            st.session_state.catalog.append({
                "الاسم": prod_name, "الكود": prod_code if prod_code else "غير محدد",
                "التصنيف": category, "تكلفة القطعة": cost_price, "سعر الدستة": dozen_price,
                "سعر القطعة": round(unit_price, 2), "عدد الكرتونة": carton_qty, "سعر الكرتونة": carton_price,
                "الكمية بالمخزن": stock_qty, "الصورة": processed_catalog_image
            })
            st.success(f"تمت إضافة ({prod_name}) بالصورة المعدلة بنجاح!")

# ---------------------------------------------------------
# TAB 5: مولّد البوستات والعروض التجميعية
# ---------------------------------------------------------
with main_tab5:
    st.header("📲 مولّد البوستات والعروض التجميعية (Bundles)")
    sub_mode = st.radio("اختر نمط المنشور:", ["منشور لمنتج منفرد", "💥 عرض تجميعي/باقة (Bundle)"], horizontal=True)

    if sub_mode == "منشور لمنتج منفرد":
        if not st.session_state.catalog: st.warning("👈 لا توجد منتجات بالكتالوج!")
        else:
            prod_names = [f"{p['الاسم']} (كود: {p['الكود']})" for p in st.session_state.catalog]
            selected_prod_idx = st.selectbox("اختر المنتج:", range(len(prod_names)), format_func=lambda x: prod_names[x])
            item = st.session_state.catalog[selected_prod_idx]

            col_p1, col_p2 = st.columns(2)
            with col_p1:
                post_style = st.selectbox("أسلوب المنشور:", ["💥 عرض خاص وتخفيضات", "🏬 تجارة جملة للمحلات", "🌟 عرض قطاعي راقي"])
                price_display = st.selectbox("إظهار الأسعار؟", ["سعر القطعة وسعر الدستة", "سعر الدستة فقط", "سعر القطعة فقط", "بدون أسعار"])
            
            with col_p2:
                cat_tags = CATEGORY_HASHTAGS.get(item["التصنيف"], ["#منتجات_مميزة"])
                selected_hashtags = st.multiselect("الهاشتاجات المقترحة:", options=cat_tags + TRENDING_HASHTAGS, default=cat_tags[:4])
                custom_hashtags = st.text_input("هاشتاجات إضافية:", "#اسم_محلكم #جديد")

            post_text = f"🔥 **{post_style}** 🔥\n\n📦 **اسم المنتج:** {item['الاسم']}\n"
            if item['الكود'] != "غير محدد": post_text += f"🔢 **الكود:** {item['الكود']}\n"
            if price_display == "سعر القطعة وسعر الدستة":
                post_text += f"💰 **سعر الدستة:** {item['سعر الدستة']} ج.م\n💵 **سعر القطعة:** {item['سعر القطعة']} ج.م\n"
            elif price_display == "سعر الدستة فقط": post_text += f"💰 **سعر الدستة:** {item['سعر الدستة']} ج.م\n"
            elif price_display == "سعر القطعة فقط": post_text += f"💵 **سعر القطعة:** {item['سعر القطعة']} ج.م\n"

            p_note = st.session_state.get('persistent_note', '')
            if p_note.strip(): post_text += f"\n📌 **ملاحظة:** {p_note.strip()}\n"
            
            w_num = st.session_state.get('whatsapp_num', '')
            c_phone = st.session_state.get('contact_phone', '')
            s_addr = st.session_state.get('store_address', '')
            
            post_text += f"\n-----------------------------------\n📲 **للطلب:**\n💬 **واتساب:** https://wa.me/{w_num.replace('+', '').strip()}\n📞 **تليفون:** {c_phone}\n📍 **العنوان:** {s_addr}\n\n"
            post_text += " ".join(selected_hashtags) + " " + custom_hashtags.strip()

            st.markdown(f'<div class="post-box">{post_text}</div>', unsafe_allow_html=True)

    else:
        st.subheader("💥 مولّد باقات العروض المشكلة")
        if len(st.session_state.catalog) < 2: st.info("يلزم وجود منتجين على الأقل لعمل باقة!")
        else:
            selected_bundle_items = st.multiselect(
                "اختر المنتجات بالباقة:", options=range(len(st.session_state.catalog)),
                format_func=lambda x: f"{st.session_state.catalog[x]['الاسم']} ({st.session_state.catalog[x]['سعر القطعة']} ج.م)"
            )
            if selected_bundle_items:
                discount_percent = st.slider("نسبة الخصم (%):", 0, 50, 10)
                bundle_title = st.text_input("اسم الباقة:", "عرض التوفير السوبر 🔥")
                total_orig = sum([st.session_state.catalog[i]['سعر القطعة'] for i in selected_bundle_items])
                final_p = total_orig * (1 - discount_percent/100.0)

                b_post = f"🎁 **{bundle_title}** 🎁\n\n📦 **محتويات الباقة:**\n"
                for i in selected_bundle_items: b_post += f"• {st.session_state.catalog[i]['الاسم']}\n"
                b_post += f"\n❌ **قبل الخصم:** ~~{round(total_orig, 2)} ج.م~~\n✅ **بعد الخصم:** {round(final_p, 2)} ج.م فقط! 🔥\n"
                
                p_note = st.session_state.get('persistent_note', '')
                if p_note.strip(): b_post += f"\n📌 **ملاحظة:** {p_note.strip()}\n"
                
                w_num = st.session_state.get('whatsapp_num', '')
                c_phone = st.session_state.get('contact_phone', '')
                b_post += f"\n💬 **للطلب واتساب:** https://wa.me/{w_num.replace('+', '').strip()}\n📞 **تليفون:** {c_phone}"

                st.markdown(f'<div class="post-box">{b_post}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# TAB 6: الكتالوج والتصدير
# ---------------------------------------------------------
with main_tab6:
    st.header("📖 الكتالوج والمخزون وتصدير البيانات")
    if not st.session_state.catalog: st.write("الكتالوج فارغ حالياً.")
    else:
        for idx, item in enumerate(st.session_state.catalog):
            st.markdown('<div class="product-card">', unsafe_allow_html=True)
            c1, c2 = st.columns([1, 3])
            with c1:
                if item["الصورة"]: st.image(item["الصورة"], width=130)
                else: st.caption("📷 لا توجد صورة")
            with c2:
                st.subheader(f"{item['الاسم']} ({item['التصنيف']})")
                st.write(f"**الكود:** {item['الكود']} | **سعر القطعة:** {item['سعر القطعة']} ج.م | **سعر الدستة:** {item['سعر الدستة']} ج.م")
                qty = item['الكمية بالمخزن']
                if qty > 10: st.markdown(f"المخزون: <span class='status-ok'>متوفر ({qty} قطعة)</span>", unsafe_allow_html=True)
                elif 0 < qty <= 10: st.markdown(f"المخزون: <span class='status-low'>مخزون منخفض ({qty} قطعة)</span>", unsafe_allow_html=True)
                else: st.markdown("المخزون: <span class='status-out'>نفذت الكمية!</span>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        df_export = pd.DataFrame(st.session_state.catalog).drop(columns=["الصورة"], errors="ignore")
        csv_data = df_export.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📄 تحميل الكتالوج كملف Excel (CSV)", data=csv_data, file_name="catalog_products.csv", mime="text/csv")

st.markdown(f"<br><p style='text-align: center; color: #2a4d69; font-weight: bold;'>{config.DEVELOPER_SIGNATURE}</p>", unsafe_allow_html=True)
