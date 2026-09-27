import os
import re
import json
import time
import requests
import io
import base64
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
# 1. إعداد الصفحة والتهيئة الأساسية
# =========================================================
st.set_page_config(page_title=config.PAGE_TITLE, page_icon=config.PAGE_ICON, layout="wide")

current_channels = config.load_and_sync_channels()

if not os.path.exists(config.DEFAULT_LOGO_PATH):
    Image.new('RGBA', (200, 200), color=(255, 75, 75, 255)).save(config.DEFAULT_LOGO_PATH)
if not os.path.exists(config.ACTIVE_LOGO_PATH):
    Image.open(config.DEFAULT_LOGO_PATH).save(config.ACTIVE_LOGO_PATH)

# تهيئة الـ Session State للمصنع والمخزون
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
    "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0
}

for k, v in DEFAULT_SETTINGS.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "categories" not in st.session_state:
    st.session_state.categories = ["توك واكسسوارات", "خردوات", "استانليس", "بلاستيكات", "شغل مواسم"]

if "catalog" not in st.session_state:
    st.session_state.catalog = []

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .web-banner {
        background: linear-gradient(135deg, #111115 0%, #ff4b4b 100%);
        padding: 25px;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0px 6px 20px rgba(255, 75, 75, 0.4);
        margin-bottom: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .banner-title { color: #ffffff; font-size: 32px; font-weight: bold; margin-bottom: 5px; }
    .banner-subtitle { color: #e0e0e0; font-size: 20px; font-weight: 500; margin-bottom: 10px; }
    .product-card {
        background-color: #1a1c23;
        border-radius: 12px;
        padding: 16px;
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
    div[data-baseweb="popover"], div[data-baseweb="menu"] { z-index: 999999 !important; }
    </style>
""", unsafe_allow_html=True)

st.markdown(f"""
    <div class="web-banner">
        <div class="banner-title">🥷 Mr:- Bo0</div>
        <div class="banner-subtitle">{config.BRAND_NAME_AR}</div>
    </div>
""", unsafe_allow_html=True)

# =========================================================
# 2. الدوال المساعدة للصور والفيديوهات والأسعار
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

def process_image_template(image_path, blur_background=True, blur_intensity=12, opacity_val=0.8, 
                           fit_auto_logo=False, logo_custom_w=200, logo_custom_h=200,
                           brand_text_scale=0.035, brand_color="#FFD700", brand_pos="تحت شمال (Bottom-Left)", brand_off_x=0, brand_off_y=0,
                           extra_text="", extra_text_scale=0.025, extra_color="#FFFFFF", extra_pos="تحت يمين (Bottom-Right)", extra_off_x=0, extra_off_y=0,
                           target_size=None, enhance_quality=True, sharpness_val=2.0, quality_val=95, logo_pos_mode="فوق يمين (Top-Right)", logo_off_x=0, logo_off_y=0,
                           enable_watermark_pattern=False, color_preset="طبيعي (بدون فلتر)",
                           enable_crop=False, c_left=0, c_top=0, c_right=0, c_bottom=0):
    
    img = Image.open(image_path).convert("RGBA")
    if enable_crop and (c_left > 0 or c_top > 0 or c_right > 0 or c_bottom > 0):
        w, h = img.size
        img = img.crop((min(c_left, w - 1), min(c_top, h - 1), max(w - c_right, c_left + 1), max(h - c_bottom, c_top + 1)))

    img = apply_color_preset(img, color_preset)
    if enhance_quality and sharpness_val > 0:
        img = ImageEnhance.Sharpness(img).enhance(1.0 + sharpness_val)
        img = ImageEnhance.Contrast(img).enhance(1.15)

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

def download_from_link(url):
    output_template = 'web_input.mp4'
    if os.path.exists(output_template): os.remove(output_template)
    ydl_opts = {'format': 'best[ext=mp4]/best', 'outtmpl': output_template, 'quiet': True, 'nocheckcertificate': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
    return output_template

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

# =========================================================
# 3. الشريط الجانبي الرئيسي
# =========================================================
with st.sidebar:
    st.markdown("<h2 style='color:#ff4b4b;'>🛰️ التحكم العام</h2>", unsafe_allow_html=True)
    app_section = st.radio("اختر القسم المطلوب:", ["🥷 المصنع الإلكتروني (Mr:- Bo0)", "📦 الكتالوج والمخزون والمبيعات"])

    st.divider()
    st.header("📞 بيانات التواصل الثابتة")
    contact_phone = st.text_input("رقم الهاتف:", "01000000000")
    whatsapp_num = st.text_input("رقم الواتساب:", "201000000000")
    fb_page_link = st.text_input("رابط الفيسبوك:", "https://facebook.com/yourpage")
    store_address = st.text_input("العنوان / الشحن:", "القاهرة - شحن لجميع المحافظات 🚚")

    st.divider()
    persistent_note = st.text_area("نص ثابت في البوستات:", placeholder="مثال: خصم 5% للجملة!")

# =========================================================
# 4. القسم الأول: المصنع الإلكتروني
# =========================================================
if app_section == "🥷 المصنع الإلكتروني (Mr:- Bo0)":
    tab_factory1, tab_factory2, tab_factory3 = st.tabs([
        "🎬 مونتاج وتقطيع الفيديو", 
        "🖼️ ألبومات الصور والسلايد شو", 
        "🛰️ رادار القنوات والتسعير"
    ])

    with tab_factory1:
        st.subheader("🚀 منصة تسريع ومونتاج الفيديو")
        option = st.radio("مصدر الفيديو:", ("لصق رابط فيديو", "رفع ملف فيديو مباشر"))
        input_path = "web_input.mp4"
        output_path = "Bo0sViDClone_web_output.mp4"
        ready_to_process = False

        if option == "لصق رابط فيديو":
            url = st.text_input("ضع الرابط هنا:")
            if url and st.button("🚀 ابدأ المعالجة"):
                downloaded_file = download_from_link(url)
                if os.path.exists(input_path): os.remove(input_path)
                os.rename(downloaded_file, input_path)
                ready_to_process = True
        else:
            uploaded_file = st.file_uploader("ارفع الفيديو:", type=["mp4", "mov", "avi"])
            if uploaded_file and st.button("⚙️ ابدأ المعالجة"):
                with open(input_path, "wb") as f: f.write(uploaded_file.read())
                ready_to_process = True

        if ready_to_process:
            try:
                clip = VideoFileClip(input_path)
                clip.write_videofile(output_path, codec="libx264", audio_codec="aac", preset="ultrafast")
                st.success("🎉 تم المونتاج بنجاح!")
                st.video(output_path)
            except Exception as e: st.error(f"خطأ: {e}")

    with tab_factory2:
        st.subheader("🖼️ ألبومات صور المنتجات والسلايد شو")
        uploaded_images = st.file_uploader("ارفع الصور:", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        if uploaded_images and st.button("⚙️ معالجة الصور"):
            saved_paths = []
            for i, img_file in enumerate(uploaded_images):
                temp_p = f"temp_prod_{i}.png"
                with open(temp_p, "wb") as f: f.write(img_file.read())
                processed = process_image_template(temp_p)
                saved_paths.append(processed)
            st.success("تمت المعالجة بنجاح!")
            for p in saved_paths: st.image(p, width=200)

    with tab_factory3:
        st.subheader("🛰️ رادار القنوات وإعادة التسعير")
        target_ch = st.selectbox("اختر القناة:", current_channels)
        if st.button("🛰️ قنص المحتوى"):
            st.info("جاري سحب المحتوى والمنشورات...")

# =========================================================
# 5. القسم الثاني: إدارة المنتجات، الكتالوج والمخزون
# =========================================================
else:
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "➕ إضافة منتج ومخزون", 
        "📂 استيراد كتالوج (Excel/CSV)", 
        "📲 مولّد البوستات والهاشتاجات", 
        "💥 مولّد العروض والباقات", 
        "📖 الكتالوج والـ PDF"
    ])

    with tab1:
        st.header("📦 إضافة منتج جديد")
        col_img, col_inputs = st.columns([1, 2])
        with col_img:
            uploaded_image = st.file_uploader("ارفع صورة المنتج", type=["jpg", "png", "jpeg"])
            if uploaded_image: st.image(uploaded_image, width=200)

        with col_inputs:
            prod_name = st.text_input("اسم المنتج *")
            prod_code = st.text_input("كود المنتج")
            category = st.selectbox("التصنيف", st.session_state.categories)
            dozen_price = st.number_input("سعر الدستة (12 قطعة)", min_value=0.0, value=0.0)
            unit_price = dozen_price / 12.0 if dozen_price > 0 else 0.0
            st.number_input("سعر القطعة (محسوب)", value=round(unit_price, 2), disabled=True)
            stock_qty = st.number_input("المخزون (بالقطعة)", min_value=0, value=50)

        if st.button("➕ إضافة للكتالوج والمخزن", type="primary"):
            if not prod_name: st.error("أدخل اسم المنتج!")
            else:
                st.session_state.catalog.append({
                    "الاسم": prod_name, "الكود": prod_code if prod_code else "غير محدد",
                    "التصنيف": category, "سعر الدستة": dozen_price,
                    "سعر القطعة": round(unit_price, 2), "الكمية بالمخزن": stock_qty,
                    "الصورة": uploaded_image
                })
                st.success(f"تمت إضافة {prod_name} بنجاح!")

    with tab2:
        st.header("📂 استيراد من Excel أو CSV")
        uploaded_file = st.file_uploader("اختر ملف Excel أو CSV", type=["xlsx", "xls", "csv"])
        if uploaded_file:
            df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            st.dataframe(df)

    with tab3:
        st.header("📲 مولّد البوستات")
        if not st.session_state.catalog: st.warning("الكتالوج فارغ حالياً!")
        else:
            prod_names = [p['الاسم'] for p in st.session_state.catalog]
            sel_idx = st.selectbox("اختر المنتج:", range(len(prod_names)), format_func=lambda x: prod_names[x])
            item = st.session_state.catalog[sel_idx]
            
            post_text = f"🔥 **عرض خاص!** 🔥\n📦 **المنتج:** {item['الاسم']}\n💵 **سعر القطعة:** {item['سعر القطعة']} ج.م\n"
            if persistent_note: post_text += f"\n📌 **ملاحظة:** {persistent_note}\n"
            post_text += f"\n📲 **للتواصل:** {whatsapp_num}"
            st.markdown(f'<div class="post-box">{post_text}</div>', unsafe_allow_html=True)

    with tab4:
        st.header("💥 مولّد عروض الباقات المشكلة")
        st.info("اختر مجموعة منتجات لإنشاء باقة بسعر خاص!")

    with tab5:
        st.header("📖 الكتالوج الحالي")
        for p in st.session_state.catalog:
            st.markdown(f"### {p['الاسم']} ({p['التصنيف']})")
            st.write(f"الكود: {p['الكود']} | سعر القطعة: {p['سعر القطعة']} ج.م | المخزون: {p['الكمية بالمخزن']}")
