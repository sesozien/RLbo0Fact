import os
import json

# =========================================================
# الإعدادات العامة للمشروع والمسارات
# =========================================================
PAGE_TITLE = "Bo0'sViDClone - مصنع الفيديوهات والصور"
PAGE_ICON = "🥷"

BRAND_NAME_AR = "مصنع المنتجات والمنصات الذكي"
DEVELOPER_SIGNATURE = "Developed with 💡 by Bo0"

# المسارات الأساسية
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
os.makedirs(TMP_DIR, exist_ok=True)

DEFAULT_LOGO_PATH = os.path.join(BASE_DIR, "default_logo.png")
ACTIVE_LOGO_PATH = os.path.join(BASE_DIR, "active_logo.png")
CUSTOM_AUDIO_TRACK = os.path.join(BASE_DIR, "default_audio.mp3")
CHANNELS_FILE = os.path.join(BASE_DIR, "channels.json")

# الإعدادات الافتراضية للتسعير
DEFAULT_PRICE_INC_RATE = 20
DEFAULT_BOX_ITEMS_COUNT = 12

# الكلمات الدلالية لكشف الأسعار في القنوات
PRICE_KEYWORDS = ["سعر", "جملة", "بـ", "بسعر", "المطلوب", "جنية", "ج"]

def load_and_sync_channels():
    """تحميل القنوات المفضلة من ملف JSON"""
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return ["montgk", "egypt_offers"]
    return ["montgk", "egypt_offers"]
