
import os
import re
import json
import time
import threading
from collections import deque

import cv2
import numpy as np
import pyautogui
import keyboard
import pytesseract
import ctypes



# ============================================================
# PKMD BOT - versão mais robusta (V12)
# - HP lido pela barra vermelha (sem OCR)
# - Coordenadas lidas da linha do minimapa (OCR em região fixa)
# - Calibração por clique/seleção com OpenCV
# - Cavebot + revive + rotas JSON
# - Revive por HP OU Mana (mana por OCR do número)
# ============================================================

# ------------------------------
# Caminhos
# ------------------------------
BASE_DIR = os.path.join(os.path.expanduser("~"), "Documents", "pkmd_bot")
ROUTES_DIR = os.path.join(BASE_DIR, "routes")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(ROUTES_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# ------------------------------
# Tesseract
# ------------------------------
DEFAULT_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(DEFAULT_TESSERACT):
    pytesseract.pytesseract.tesseract_cmd = DEFAULT_TESSERACT

# ------------------------------
# Config padrão
# ------------------------------
DEFAULT_CONFIG = {
    "teclas": {"right": "d", "left": "a", "down": "s", "up": "w"},
    "tecla_revive": "2",
    "hp_revive_percent": 35.0,
    "mana_revive_percent": 30.0,
    "mana_max_value": None,
    "hp_confirmacoes": 3,
    "hp_cooldown": 10.0,
    "tick_movimento": 0.12,
    "timeout_waypoint": 8.0,
    "distancia_chegada": 2,
    "progresso_minimo": 1,
    "coord_max_salto": 8,
    "coord_min_x": 50,
    "coord_min_y": 50,
    "coord_max_x": 9999,
    "coord_max_y": 9999,
    "template_threshold_minimap": 0.82,
    "template_threshold_poke": 0.82,
    "tesseract_psm": 7,
    "minimap_header_template": "minimap_header.png",
    "poke_header_template": "poke_header.png",
    "minimap_header_size": None,        # [w, h]
    "poke_header_size": None,           # [w, h]
    "coords_offset": None,              # [dx, dy, w, h]
    "hp_bar_offset": None,              # [dx, dy, w, h]
    "mana_bar_offset": None,            # [dx, dy, w, h]
    "minimap_header_anchor_template": "minimap_header_anchor.png",
    "poke_header_anchor_template": "poke_header_anchor.png",
    "minimap_anchor_offset": None,      # [dx, dy] do anchor dentro do header
    "poke_anchor_offset": None,         # [dx, dy] do anchor dentro do header
    "minimap_header_rect_abs": None,    # [x, y, w, h]
    "poke_header_rect_abs": None,       # [x, y, w, h]
    "anchor_threshold_minimap": 0.75,
    "anchor_threshold_poke": 0.75
}

_config = None
_pyautogui_lock = threading.Lock()
_stop_hp = threading.Event()
_stop_requested = threading.Event()
_hotkey_registered = False

# cache de localização dos painéis
_panel_cache = {
    "minimap": None,  # (x, y, w, h)
    "poke": None
}


def get_console_hwnd():
    try:
        return ctypes.windll.kernel32.GetConsoleWindow()
    except Exception:
        return 0


def minimize_console():
    hwnd = get_console_hwnd()
    if hwnd:
        try:
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        except Exception:
            pass


def restore_console():
    hwnd = get_console_hwnd()
    if hwnd:
        try:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass


def ensure_game_focus(delay_after_minimize=0.35):
    """Minimiza o console para devolver o foco ao jogo antes do bot enviar teclas."""
    minimize_console()
    time.sleep(delay_after_minimize)


def send_revive_key():
    """Envia a tecla configurada do revive usando o evento de teclado do Windows.
    Ainda depende do jogo estar em foco, por isso chamamos ensure_game_focus() antes."""
    cfg = require_config()
    key = str(cfg.get("tecla_revive", "2")).strip()
    if not key:
        key = "2"

    vk = None
    if len(key) == 1:
        ch = key.upper()
        if '0' <= ch <= '9':
            vk = ord(ch)
        elif 'A' <= ch <= 'Z':
            vk = ord(ch)

    if vk is None:
        try:
            pyautogui.press(key)
            return
        except Exception:
            return

    KEYEVENTF_KEYUP = 0x0002
    try:
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        sleep_interruptible(0.03)
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        try:
            pyautogui.press(key)
        except Exception:
            pass


def request_stop():
    _stop_requested.set()
    _stop_hp.set()
    try:
        soltar_todas_teclas()
    except Exception:
        pass


def clear_stop_request():
    _stop_requested.clear()


def stop_requested():
    return _stop_requested.is_set()


def ensure_hotkey():
    global _hotkey_registered
    if _hotkey_registered:
        return
    try:
        keyboard.add_hotkey("end", request_stop, suppress=False, trigger_on_release=False)
        _hotkey_registered = True
    except Exception:
        _hotkey_registered = False


def sleep_interruptible(seconds, stop_event=None, slice_seconds=0.02):
    end_at = time.time() + max(0.0, seconds)
    while time.time() < end_at:
        if stop_requested():
            return False
        if stop_event is not None and stop_event.is_set():
            return False
        remaining = end_at - time.time()
        time.sleep(min(slice_seconds, max(0.0, remaining)))
    return True


# ============================================================
# UTIL
# ============================================================
def load_config():
    global _config
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        cfg = DEFAULT_CONFIG.copy()
        cfg.update(loaded)

        # Migração simples: versões antigas vinham com 13%/18%.
        # Como você pediu 35%, ajustamos automaticamente nesses casos.
        old_hp = loaded.get("hp_revive_percent")
        if old_hp in (13, 13.0, 18, 18.0):
            cfg["hp_revive_percent"] = 35.0
        if "mana_revive_percent" not in loaded:
            cfg["mana_revive_percent"] = 30.0

        # saneia mana máxima gravada por OCR bugado em versões anteriores
        try:
            mana_max_loaded = cfg.get("mana_max_value")
            if mana_max_loaded is not None and int(mana_max_loaded) > 99999:
                cfg["mana_max_value"] = None
        except Exception:
            cfg["mana_max_value"] = None

        _config = cfg
        save_config()
    else:
        _config = DEFAULT_CONFIG.copy()
        save_config()
    return _config


def save_config():
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(_config, f, indent=2, ensure_ascii=False)


def require_config():
    if _config is None:
        load_config()
    return _config


def tpath(*parts):
    return os.path.join(TEMPLATES_DIR, *parts)


def route_path(name):
    return os.path.join(ROUTES_DIR, f"{name}.json")


def soltar_todas_teclas():
    cfg = require_config()
    for t in cfg["teclas"].values():
        try:
            pyautogui.keyUp(t)
        except Exception:
            pass


def screenshot_bgr(region=None):
    if region:
        left, top, width, height = region
        img = pyautogui.screenshot(region=(left, top, width, height))
    else:
        img = pyautogui.screenshot()
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def capture_clean_frame(delay=2.5):
    cv2.destroyAllWindows()
    try:
        cv2.waitKey(1)
    except Exception:
        pass
    print(f"\nCapturando a tela em {delay:.1f}s... deixe SOMENTE o jogo visível.")
    minimize_console()
    time.sleep(delay)
    frame = screenshot_bgr()
    restore_console()
    return frame


def select_roi_from_frame(title, frame):
    print(f"\n[CALIBRAÇÃO] {title}")
    print("Selecione a área e pressione ENTER. Para cancelar, ESC.\n")
    frame_copy = frame.copy()
    roi = cv2.selectROI(title, frame_copy, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow(title)
    try:
        cv2.waitKey(1)
    except Exception:
        pass
    x, y, w, h = [int(v) for v in roi]
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h


def crop(frame, rect):
    x, y, w, h = rect
    return frame[y:y+h, x:x+w].copy()


def build_right_anchor(rect, min_w=42, max_w=64):
    x, y, w, h = rect
    aw = max(min_w, min(max_w, max(1, w // 3)))
    ax = x + (w - aw)
    ay = y
    return (ax, ay, aw, h), [w - aw, 0]


def template_gray_from_file(path):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    return img


def bgr_to_gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def wp_str(wp):
    z = ""
    if len(wp) > 2 and wp[2] is not None:
        z = f" Z={wp[2]}"
    return f"X={wp[0]} Y={wp[1]}{z}"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def normalize_text(s):
    if not s:
        return s
    trans = str.maketrans({
        "O": "0", "o": "0", "Q": "0", "D": "0",
        "I": "1", "l": "1", "|": "1", "!": "1",
        "S": "5", "$": "5",
        "B": "8"
    })
    s = s.translate(trans)
    s = s.replace(",", ":").replace(";", ":")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def detect_panel_from_existing_templates(frame_bgr, panel_name):
    """Tenta localizar um painel usando os templates já salvos.
    Útil para calibração individual sem precisar refazer tudo."""
    try:
        return get_panel_rect(frame_bgr, panel_name)
    except Exception:
        return None


def ensure_rect_inside_frame(rect, frame):
    if rect is None:
        return None
    x, y, w, h = [int(v) for v in rect]
    fh, fw = frame.shape[:2]
    if w <= 0 or h <= 0:
        return None
    x = clamp(x, 0, fw - 1)
    y = clamp(y, 0, fh - 1)
    w = clamp(w, 1, fw - x)
    h = clamp(h, 1, fh - y)
    return (x, y, w, h)


def print_calibration_tips():
    print("\nDicas rápidas de calibração:")
    print("- Cabeçalho do minimapa: pegue só a faixa preta de cima; de preferência a parte fixa da direita.")
    print("- Coordenadas: pegue só a linha 'X: ... Y: ... Z: ...'.")
    print("- Cabeçalho do Poke Inventario: só a faixa preta superior.")
    print("- Barra do HP: somente a barra vermelha, sem número e sem barra azul.")
    print("- Barra da Mana: somente a barra azul, sem número e sem barra vermelha.\n")


# ============================================================
# CALIBRAÇÃO
# ============================================================
def calibrar_completo():
    cfg = require_config()

    print("\n=== CALIBRAÇÃO COMPLETA ===")
    print("Deixe o jogo aberto e visível.")
    print("A calibração usa UMA captura limpa da tela.")
    print("Você vai selecionar 5 áreas nessa mesma imagem:")
    print("1) cabeçalho do minimapa")
    print("2) linha das coordenadas")
    print("3) cabeçalho do Poke Inventario")
    print("4) barra vermelha do HP")
    print("5) barra azul da Mana")
    print_calibration_tips()
    input("Pressione ENTER para capturar a tela limpa...")

    base_frame = capture_clean_frame(delay=2.5)

    # 1) minimapa header
    r1 = select_roi_from_frame("1 - Selecione o cabeçalho do minimapa", base_frame)
    if not r1:
        print("Calibração cancelada.")
        return
    x1, y1, w1, h1 = r1
    cv2.imwrite(tpath(cfg["minimap_header_template"]), crop(base_frame, (x1, y1, w1, h1)))
    anchor_rect, anchor_off = build_right_anchor((x1, y1, w1, h1))
    cv2.imwrite(tpath(cfg["minimap_header_anchor_template"]), crop(base_frame, anchor_rect))
    cfg["minimap_header_size"] = [w1, h1]
    cfg["minimap_anchor_offset"] = anchor_off
    cfg["minimap_header_rect_abs"] = [x1, y1, w1, h1]

    # 2) coords line
    r2 = select_roi_from_frame("2 - Selecione a linha das coordenadas", base_frame)
    if not r2:
        print("Calibração cancelada.")
        return
    x2, y2, w2, h2 = r2
    cfg["coords_offset"] = [x2 - x1, y2 - y1, w2, h2]

    # 3) poke header
    r3 = select_roi_from_frame("3 - Selecione o cabeçalho do Poke Inventario", base_frame)
    if not r3:
        print("Calibração cancelada.")
        return
    x3, y3, w3, h3 = r3
    cv2.imwrite(tpath(cfg["poke_header_template"]), crop(base_frame, (x3, y3, w3, h3)))
    anchor_rect, anchor_off = build_right_anchor((x3, y3, w3, h3))
    cv2.imwrite(tpath(cfg["poke_header_anchor_template"]), crop(base_frame, anchor_rect))
    cfg["poke_header_size"] = [w3, h3]
    cfg["poke_anchor_offset"] = anchor_off
    cfg["poke_header_rect_abs"] = [x3, y3, w3, h3]

    # 4) hp bar
    r4 = select_roi_from_frame("4 - Selecione SOMENTE a barra vermelha do HP", base_frame)
    if not r4:
        print("Calibração cancelada.")
        return
    x4, y4, w4, h4 = r4
    cfg["hp_bar_offset"] = [x4 - x3, y4 - y3, w4, h4]

    # 5) mana bar
    r5 = select_roi_from_frame("5 - Selecione SOMENTE a barra azul da Mana", base_frame)
    if not r5:
        print("Calibração cancelada.")
        return
    x5, y5, w5, h5 = r5
    cfg["mana_bar_offset"] = [x5 - x3, y5 - y3, w5, h5]

    save_config()
    reset_panel_cache()
    cv2.destroyAllWindows()
    print("\nCalibração completa salva com sucesso!")


def calibrar_minimap_header():
    cfg = require_config()
    print("\n=== CALIBRAR: CABEÇALHO DO MINIMAPA ===")
    print_calibration_tips()
    input("Pressione ENTER para capturar a tela limpa...")
    base_frame = capture_clean_frame(delay=2.5)

    r = select_roi_from_frame("Minimapa - cabeçalho", base_frame)
    if not r:
        print("Calibração cancelada.")
        return

    x, y, w, h = r
    cv2.imwrite(tpath(cfg["minimap_header_template"]), crop(base_frame, (x, y, w, h)))
    anchor_rect, anchor_off = build_right_anchor((x, y, w, h))
    cv2.imwrite(tpath(cfg["minimap_header_anchor_template"]), crop(base_frame, anchor_rect))
    cfg["minimap_header_size"] = [w, h]
    cfg["minimap_anchor_offset"] = anchor_off
    cfg["minimap_header_rect_abs"] = [x, y, w, h]

    save_config()
    reset_panel_cache()
    cv2.destroyAllWindows()
    print("Cabeçalho do minimapa recalibrado com sucesso!")


def calibrar_coords_line():
    cfg = require_config()
    print("\n=== CALIBRAR: LINHA DAS COORDENADAS ===")
    print("O bot vai tentar localizar automaticamente o cabeçalho atual do minimapa usando o template já salvo.")
    print_calibration_tips()
    input("Pressione ENTER para capturar a tela limpa...")
    base_frame = capture_clean_frame(delay=2.5)

    panel = detect_panel_from_existing_templates(base_frame, "minimap")
    if panel is None:
        abs_rect = cfg.get("minimap_header_rect_abs")
        panel = ensure_rect_inside_frame(abs_rect, base_frame)

    if panel is None:
        print("Não consegui localizar o cabeçalho do minimapa atual.")
        print("Recalibre primeiro o cabeçalho do minimapa ou faça a calibração completa.")
        return

    r = select_roi_from_frame("Coordenadas - linha X/Y/Z", base_frame)
    if not r:
        print("Calibração cancelada.")
        return

    px, py, pw, ph = panel
    x, y, w, h = r
    cfg["coords_offset"] = [x - px, y - py, w, h]

    save_config()
    reset_panel_cache()
    cv2.destroyAllWindows()
    print("Linha das coordenadas recalibrada com sucesso!")


def calibrar_poke_header():
    cfg = require_config()
    print("\n=== CALIBRAR: CABEÇALHO DO POKE INVENTARIO ===")
    print_calibration_tips()
    input("Pressione ENTER para capturar a tela limpa...")
    base_frame = capture_clean_frame(delay=2.5)

    r = select_roi_from_frame("Poke Inventario - cabeçalho", base_frame)
    if not r:
        print("Calibração cancelada.")
        return

    x, y, w, h = r
    cv2.imwrite(tpath(cfg["poke_header_template"]), crop(base_frame, (x, y, w, h)))
    anchor_rect, anchor_off = build_right_anchor((x, y, w, h))
    cv2.imwrite(tpath(cfg["poke_header_anchor_template"]), crop(base_frame, anchor_rect))
    cfg["poke_header_size"] = [w, h]
    cfg["poke_anchor_offset"] = anchor_off
    cfg["poke_header_rect_abs"] = [x, y, w, h]

    save_config()
    reset_panel_cache()
    cv2.destroyAllWindows()
    print("Cabeçalho do Poke Inventario recalibrado com sucesso!")


def calibrar_hp_bar():
    cfg = require_config()
    print("\n=== CALIBRAR: BARRA DO HP ===")
    print("O bot vai tentar localizar automaticamente o cabeçalho atual do Poke Inventario usando o template já salvo.")
    print_calibration_tips()
    input("Pressione ENTER para capturar a tela limpa...")
    base_frame = capture_clean_frame(delay=2.5)

    panel = detect_panel_from_existing_templates(base_frame, "poke")
    if panel is None:
        abs_rect = cfg.get("poke_header_rect_abs")
        panel = ensure_rect_inside_frame(abs_rect, base_frame)

    if panel is None:
        print("Não consegui localizar o cabeçalho atual do Poke Inventario.")
        print("Recalibre primeiro o cabeçalho do Poke Inventario ou faça a calibração completa.")
        return

    r = select_roi_from_frame("HP - somente a barra vermelha", base_frame)
    if not r:
        print("Calibração cancelada.")
        return

    px, py, pw, ph = panel
    x, y, w, h = r
    cfg["hp_bar_offset"] = [x - px, y - py, w, h]

    save_config()
    reset_panel_cache()
    cv2.destroyAllWindows()
    print("Barra do HP recalibrada com sucesso!")


def calibrar_mana_bar():
    cfg = require_config()
    print("\n=== CALIBRAR: BARRA DA MANA ===")
    print("O bot vai tentar localizar automaticamente o cabeçalho atual do Poke Inventario usando o template já salvo.")
    print_calibration_tips()
    input("Pressione ENTER para capturar a tela limpa...")
    base_frame = capture_clean_frame(delay=2.5)

    panel = detect_panel_from_existing_templates(base_frame, "poke")
    if panel is None:
        abs_rect = cfg.get("poke_header_rect_abs")
        panel = ensure_rect_inside_frame(abs_rect, base_frame)

    if panel is None:
        print("Não consegui localizar o cabeçalho atual do Poke Inventario.")
        print("Recalibre primeiro o cabeçalho do Poke Inventario ou faça a calibração completa.")
        return

    r = select_roi_from_frame("Mana - somente a barra azul", base_frame)
    if not r:
        print("Calibração cancelada.")
        return

    px, py, pw, ph = panel
    x, y, w, h = r
    cfg["mana_bar_offset"] = [x - px, y - py, w, h]

    save_config()
    reset_panel_cache()
    cv2.destroyAllWindows()
    print("Barra da Mana recalibrada com sucesso!")


def calibrar():
    while True:
        print("\n=== CALIBRAÇÃO ===")
        print("[1] Calibração completa")
        print("[2] Só cabeçalho do minimapa")
        print("[3] Só linha das coordenadas")
        print("[4] Só cabeçalho do Poke Inventario")
        print("[5] Só barra do HP")
        print("[6] Só barra da Mana")
        print("[0] Voltar")

        op = input("Escolha: ").strip()

        if op == "1":
            calibrar_completo()
            return
        elif op == "2":
            calibrar_minimap_header()
            return
        elif op == "3":
            calibrar_coords_line()
            return
        elif op == "4":
            calibrar_poke_header()
            return
        elif op == "5":
            calibrar_hp_bar()
            return
        elif op == "6":
            calibrar_mana_bar()
            return
        elif op == "0":
            return
        else:
            print("Opção inválida.")


def reset_panel_cache():
    _panel_cache["minimap"] = None
    _panel_cache["poke"] = None


def config_ok():
    cfg = require_config()
    if not cfg.get("coords_offset") or not cfg.get("hp_bar_offset"):
        return False
    if not os.path.exists(tpath(cfg["minimap_header_template"])):
        return False
    if not os.path.exists(tpath(cfg["poke_header_template"])):
        return False
    # anchor templates são o principal método para localizar painéis mesmo quando o nome da área muda
    if not os.path.exists(tpath(cfg["minimap_header_anchor_template"])):
        return False
    if not os.path.exists(tpath(cfg["poke_header_anchor_template"])):
        return False
    return True


# ============================================================
# TEMPLATE MATCHING
# ============================================================
def locate_template(frame_bgr, template_gray, threshold=0.82, near_rect=None, margin=120):
    frame_gray = bgr_to_gray(frame_bgr)

    if near_rect is not None:
        nx, ny, nw, nh = near_rect
        sx = max(0, nx - margin)
        sy = max(0, ny - margin)
        ex = min(frame_gray.shape[1], nx + nw + margin)
        ey = min(frame_gray.shape[0], ny + nh + margin)

        local = frame_gray[sy:ey, sx:ex]
        if local.shape[0] >= template_gray.shape[0] and local.shape[1] >= template_gray.shape[1]:
            res = cv2.matchTemplate(local, template_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= threshold:
                th, tw = template_gray.shape[:2]
                return (sx + max_loc[0], sy + max_loc[1], tw, th, max_val)

    if frame_gray.shape[0] < template_gray.shape[0] or frame_gray.shape[1] < template_gray.shape[1]:
        return None

    res = cv2.matchTemplate(frame_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val >= threshold:
        th, tw = template_gray.shape[:2]
        return (max_loc[0], max_loc[1], tw, th, max_val)

    return None


def get_panel_rect(frame_bgr, panel_name):
    cfg = require_config()

    if panel_name == "minimap":
        tpl_path = tpath(cfg["minimap_header_template"])
        threshold = cfg["template_threshold_minimap"]
        cache = _panel_cache["minimap"]
    elif panel_name == "poke":
        tpl_path = tpath(cfg["poke_header_template"])
        threshold = cfg["template_threshold_poke"]
        cache = _panel_cache["poke"]
    else:
        return None

    tpl = template_gray_from_file(tpl_path)
    if tpl is None:
        return None

    match = locate_template(frame_bgr, tpl, threshold=threshold, near_rect=cache)
    if not match:
        return None

    x, y, w, h, _ = match
    rect = (x, y, w, h)

    if panel_name == "minimap":
        _panel_cache["minimap"] = rect
    else:
        _panel_cache["poke"] = rect

    return rect


# ============================================================
# BARRAS DO POKE INVENTARIO
# ============================================================
def get_bar_offset(cfg, bar_name):
    if bar_name == "hp":
        off = cfg.get("hp_bar_offset")
        return tuple(off) if off else None

    off = cfg.get("mana_bar_offset")
    if off:
        return tuple(off)

    # fallback simples para configs antigas sem calibração da mana
    hp = cfg.get("hp_bar_offset")
    if hp and len(hp) == 4:
        dx, dy, rw, rh = hp
        return (dx, dy + rh + 2, rw, rh)

    return None


def _bar_mask_for_name(roi, bar_name):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    b, g, r = cv2.split(roi)

    if bar_name == "hp":
        mask1 = cv2.inRange(hsv, (0, 65, 45), (14, 255, 255))
        mask2 = cv2.inRange(hsv, (165, 65, 45), (180, 255, 255))
        color_mask = cv2.bitwise_or(mask1, mask2)
        dom = ((r.astype(np.int16) >= g.astype(np.int16) + 22) &
               (r.astype(np.int16) >= b.astype(np.int16) + 22) &
               (r.astype(np.int16) >= 70)).astype(np.uint8) * 255
    else:
        # Mana neste cliente tende a ficar azul/ciano, com números brancos no meio.
        # Por isso a máscara precisa ser mais permissiva e ignorar a faixa central.
        mask1 = cv2.inRange(hsv, (82, 45, 40), (145, 255, 255))
        mask2 = cv2.inRange(hsv, (75, 20, 25), (155, 255, 255))
        color_mask = cv2.bitwise_or(mask1, mask2)
        dom = (((b.astype(np.int16) >= r.astype(np.int16) + 12) &
                (b.astype(np.int16) >= 70)) |
               ((b.astype(np.int16) >= 85) &
                (g.astype(np.int16) >= 55) &
                (r.astype(np.int16) <= 170))).astype(np.uint8) * 255

    mask = cv2.bitwise_or(color_mask, dom)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((2, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return mask


def _sample_bar_rows(mask):
    h, w = mask.shape[:2]
    if h <= 0 or w <= 0:
        return mask

    # Evita a região central onde os números ficam sobre a barra.
    top_y1 = max(0, int(h * 0.08))
    top_y2 = max(top_y1 + 1, int(h * 0.34))
    bot_y1 = min(h - 1, int(h * 0.66))
    bot_y2 = h

    top = mask[top_y1:top_y2, :]
    bot = mask[bot_y1:bot_y2, :]

    if top.size == 0:
        return bot
    if bot.size == 0:
        return top
    return np.vstack([top, bot])


def _percent_from_bar_mask(mask, gap_limit=9, occupancy_threshold=0.10):
    sampled = _sample_bar_rows(mask)
    if sampled.size == 0:
        return None

    ocupacao = (sampled > 0).mean(axis=0)
    filled_cols = ocupacao > occupancy_threshold

    if not np.any(filled_cols):
        return 0.0

    started = False
    gap = 0
    first = None
    last = None

    for i, v in enumerate(filled_cols):
        if v:
            if first is None:
                first = i
            last = i
            gap = 0
            started = True
        elif started:
            gap += 1
            if gap > gap_limit:
                break

    if first is None or last is None or last < first:
        return 0.0

    pct = ((last - first + 1) / max(1, mask.shape[1])) * 100.0
    return float(clamp(pct, 0.0, 100.0))


def read_bar_percent_from_frame(frame_bgr, bar_name="hp"):
    cfg = require_config()
    panel = get_panel_rect(frame_bgr, "poke")
    if not panel:
        return None

    bar_offset = get_bar_offset(cfg, bar_name)
    if not bar_offset:
        return None

    px, py, pw, ph = panel
    dx, dy, rw, rh = bar_offset
    rx = px + dx
    ry = py + dy

    if rx < 0 or ry < 0 or rx + rw > frame_bgr.shape[1] or ry + rh > frame_bgr.shape[0]:
        return None

    roi = frame_bgr[ry:ry+rh, rx:rx+rw]
    if roi.size == 0:
        return None

    # Remove 1px de borda para reduzir interferência da moldura preta.
    if roi.shape[0] > 3 and roi.shape[1] > 3:
        roi = roi[1:-1, 1:-1]

    mask = _bar_mask_for_name(roi, bar_name)
    pct = _percent_from_bar_mask(
        mask,
        gap_limit=9 if bar_name == "mana" else 7,
        occupancy_threshold=0.08 if bar_name == "mana" else 0.10,
    )

    return pct


def _ocr_number_from_roi(roi_bgr, min_digits=1, max_digits=5):
    if roi_bgr is None or roi_bgr.size == 0:
        return None

    candidates = []
    gray = bgr_to_gray(roi_bgr)
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)

    variants = []

    big_gray = cv2.resize(gray, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
    variants.append(big_gray)

    _, th_hi = cv2.threshold(big_gray, 160, 255, cv2.THRESH_BINARY)
    variants.append(th_hi)

    _, th_otsu = cv2.threshold(big_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(th_otsu)

    white_mask = cv2.inRange(hsv, (0, 0, 145), (180, 90, 255))
    white_big = cv2.resize(white_mask, None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST)
    variants.append(white_big)

    # Dígitos claros com contorno escuro: às vezes inverter ajuda.
    variants.extend([cv2.bitwise_not(v) for v in variants[:3]])

    cfg_tess = '--psm 7 -c tessedit_char_whitelist=0123456789'

    for img in variants:
        if img.ndim == 3:
            img = bgr_to_gray(img)
        bordered = cv2.copyMakeBorder(img, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
        try:
            text = pytesseract.image_to_string(bordered, config=cfg_tess)
        except Exception:
            text = ""
        nums = re.findall(r'\d{%d,%d}' % (min_digits, max_digits), normalize_text(text))
        for n in nums:
            try:
                candidates.append(int(n))
            except Exception:
                pass

    if not candidates:
        return None

    counts = {}
    for c in candidates:
        counts[c] = counts.get(c, 0) + 1

    # prioriza o número mais frequente; em empate, o maior (evita "910" ganhar de "9100")
    best = max(counts.items(), key=lambda kv: (kv[1], len(str(kv[0])), kv[0]))[0]
    return best


def read_mana_value_from_frame(frame_bgr):
    cfg = require_config()
    panel = get_panel_rect(frame_bgr, "poke")
    if not panel:
        return None

    bar_offset = get_bar_offset(cfg, "mana")
    if not bar_offset:
        return None

    px, py, pw, ph = panel
    dx, dy, rw, rh = bar_offset
    rx = px + dx
    ry = py + dy

    if rx < 0 or ry < 0 or rx + rw > frame_bgr.shape[1] or ry + rh > frame_bgr.shape[0]:
        return None

    roi = frame_bgr[ry:ry+rh, rx:rx+rw]
    if roi.size == 0:
        return None

    if roi.shape[0] > 2 and roi.shape[1] > 2:
        roi = roi[1:-1, 1:-1]

    # Mantém a região mais útil para os dígitos; evita bordas e sombras extremas.
    x_margin = max(0, int(roi.shape[1] * 0.03))
    y_margin = max(0, int(roi.shape[0] * 0.08))
    roi_num = roi[y_margin:roi.shape[0]-y_margin if roi.shape[0]-y_margin > y_margin else roi.shape[0],
                  x_margin:roi.shape[1]-x_margin if roi.shape[1]-x_margin > x_margin else roi.shape[1]]

    value = _ocr_number_from_roi(roi_num, min_digits=2, max_digits=6)
    return value


def _update_mana_max_if_needed(mana_value):
    if mana_value is None or mana_value <= 0:
        return None

    cfg = require_config()
    current_max = cfg.get("mana_max_value")

    # Corrige automaticamente valores claramente bugados que podem ter sido
    # gravados por OCR ruim em versões anteriores, ex.: 468276.
    if current_max is not None:
        try:
            current_max = int(current_max)
        except Exception:
            current_max = None

    if current_max is not None:
        if current_max > 99999 or (mana_value <= 20000 and current_max >= mana_value * 5):
            current_max = None
            cfg["mana_max_value"] = None
            save_config()

    # Primeira aprendizagem: aceita o valor atual como base temporária.
    if current_max is None:
        cfg["mana_max_value"] = int(mana_value)
        save_config()
        return int(mana_value)

    # Só aumenta a mana máxima quando o novo valor parece plausível.
    # Isso evita que um OCR errado 46827 substitua 9100.
    if mana_value > current_max:
        crescimento_ok = (
            mana_value <= current_max * 1.5
            or (current_max <= 15000 and mana_value <= 30000)
        )
        if crescimento_ok:
            cfg["mana_max_value"] = int(mana_value)
            save_config()
            return int(mana_value)

    return int(current_max)


def format_mana_status(mana_pct=None, mana_value=None, mana_max=None):
    if mana_pct is not None and mana_value is not None and mana_max:
        return f"{mana_pct:5.1f}% ({mana_value}/{mana_max})"
    if mana_pct is not None:
        return f"{mana_pct:5.1f}%"
    if mana_value is not None and mana_max:
        return f"{mana_value}/{mana_max}"
    if mana_value is not None:
        return f"{mana_value}/?"
    return "lendo..."



def build_revive_decision(frame_bgr, hp_low_hist, mana_low_hist, allow_update_mana_max=True):
    cfg = require_config()

    hp_pct = read_hp_percent_from_frame(frame_bgr)
    mana_value = read_mana_value_from_frame(frame_bgr)
    mana_pct = read_mana_percent_from_frame(frame_bgr, allow_update_max=allow_update_mana_max)
    mana_max = _get_valid_mana_max_from_config()

    motivo = None
    if hp_pct is not None:
        hp_low_hist.append(hp_pct <= cfg["hp_revive_percent"])
        if sum(hp_low_hist) >= cfg["hp_confirmacoes"]:
            motivo = f"HP BAIXO CONFIRMADO ({hp_pct:.1f}% <= {cfg['hp_revive_percent']:.1f}%)"

    if mana_pct is not None:
        mana_low_hist.append(mana_pct <= cfg["mana_revive_percent"])
        if motivo is None and sum(mana_low_hist) >= cfg["hp_confirmacoes"]:
            extra = ""
            if mana_value is not None and mana_max:
                extra = f" ({mana_value}/{mana_max})"
            motivo = f"MANA BAIXA CONFIRMADA ({mana_pct:.1f}% <= {cfg['mana_revive_percent']:.1f}%){extra}"

    return {
        "hp_pct": hp_pct,
        "mana_value": mana_value,
        "mana_pct": mana_pct,
        "mana_max": mana_max,
        "motivo": motivo,
    }


# ============================================================
# HP POR BARRA
# ============================================================
def read_hp_percent_from_frame(frame_bgr):
    return read_bar_percent_from_frame(frame_bgr, "hp")


def _get_valid_mana_max_from_config():
    cfg = require_config()
    mana_max = cfg.get("mana_max_value")
    try:
        mana_max = int(mana_max) if mana_max is not None else None
    except Exception:
        mana_max = None

    if mana_max is not None and mana_max > 99999:
        mana_max = None

    return mana_max


def _calculate_mana_percent(mana_value, mana_max):
    if mana_value is None or mana_max is None or mana_max <= 0:
        return None
    return float(clamp((mana_value / mana_max) * 100.0, 0.0, 100.0))


def read_mana_percent_from_frame(frame_bgr, allow_update_max=True):
    mana_value = read_mana_value_from_frame(frame_bgr)
    if mana_value is None:
        return None

    if allow_update_max:
        mana_max = _update_mana_max_if_needed(mana_value)
    else:
        mana_max = _get_valid_mana_max_from_config()

    return _calculate_mana_percent(mana_value, mana_max)


# ============================================================
# COORDS POR OCR NA LINHA DO MINIMAPA
# ============================================================
def parse_coords_text(text):
    text = normalize_text(text)
    text = text.upper()

    m = re.search(r'X[:\s]*([0-9]{2,5})\s*Y[:\s]*([0-9]{1,5})\s*Z[:\s]*([0-9]{1,3})', text)
    if m:
        x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return (x, y, z)

    m = re.search(r'X[:\s]*([0-9]{2,5})\s*Y[:\s]*([0-9]{1,5})', text)
    if m:
        x, y = int(m.group(1)), int(m.group(2))
        return (x, y, None)

    return None


def coord_candidates_from_roi(roi_bgr):
    cfg = require_config()
    gray = bgr_to_gray(roi_bgr)

    # tenta também aproveitar contraste com pixels claros
    variants = []

    big = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    sharp = cv2.filter2D(big, -1, np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]]))
    blur = cv2.GaussianBlur(sharp, (3, 3), 0)

    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inv_otsu = cv2.bitwise_not(otsu)
    adap = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY, 31, 5)
    inv_adap = cv2.bitwise_not(adap)

    variants.extend([big, sharp, otsu, inv_otsu, adap, inv_adap])

    cfg_tess = f'--psm {cfg["tesseract_psm"]} -c tessedit_char_whitelist=XYZxyz0123456789: '

    candidates = []

    for img in variants:
        bordered = cv2.copyMakeBorder(img, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
        try:
            text = pytesseract.image_to_string(bordered, config=cfg_tess)
        except Exception:
            text = ""
        cand = parse_coords_text(text)
        if cand:
            candidates.append(cand)

    return candidates


def choose_best_coord_candidate(candidates):
    if not candidates:
        return None

    counts = {}
    for c in candidates:
        counts[c] = counts.get(c, 0) + 1

    best = max(counts.items(), key=lambda kv: kv[1])[0]
    return best


def read_coords_raw_from_frame(frame_bgr):
    cfg = require_config()
    panel = get_panel_rect(frame_bgr, "minimap")
    if not panel:
        return None

    px, py, pw, ph = panel
    dx, dy, rw, rh = cfg["coords_offset"]
    rx = px + dx
    ry = py + dy

    if rx < 0 or ry < 0 or rx + rw > frame_bgr.shape[1] or ry + rh > frame_bgr.shape[0]:
        return None

    roi = frame_bgr[ry:ry+rh, rx:rx+rw]
    cands = coord_candidates_from_roi(roi)
    best = choose_best_coord_candidate(cands)
    if not best:
        return None

    x, y, z = best

    if not (cfg["coord_min_x"] <= x <= cfg["coord_max_x"]):
        return None
    if not (cfg["coord_min_y"] <= y <= cfg["coord_max_y"]):
        return None

    return (x, y, z)


def read_coords_filtered(last_valid=None):
    cfg = require_config()
    frame = screenshot_bgr()
    raw = read_coords_raw_from_frame(frame)

    if not raw:
        return last_valid

    if last_valid is not None:
        salto = manhattan(raw, last_valid)
        if salto > cfg["coord_max_salto"]:
            return last_valid

    return raw


def read_coords_reliable(samples=3, delay=0.05, last_valid=None):
    vals = []
    current_last = last_valid
    for _ in range(samples):
        v = read_coords_filtered(last_valid=current_last)
        if v:
            vals.append(v)
            current_last = v
        time.sleep(delay)

    if not vals:
        return last_valid

    # maioria exata primeiro
    counts = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    best, qty = max(counts.items(), key=lambda kv: kv[1])

    if qty >= 2:
        return best

    # senão usa a última válida da sequência
    return vals[-1]


# ============================================================
# ROTAS
# ============================================================
def list_routes():
    files = [f for f in os.listdir(ROUTES_DIR) if f.lower().endswith(".json")]
    return sorted(files)


def select_route():
    files = list_routes()
    if not files:
        print("Nenhuma rota salva.")
        return None

    print("\nRotas disponíveis:")
    for i, f in enumerate(files, start=1):
        try:
            with open(os.path.join(ROUTES_DIR, f), "r", encoding="utf-8") as fp:
                data = json.load(fp)
            count = len(data)
        except Exception:
            count = "?"
        print(f"[{i}] {f[:-5]} ({count} pontos)")

    while True:
        choice = input("Escolha: ").strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(files):
                name = files[idx - 1][:-5]
                with open(route_path(name), "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                return data, name
        print("Inválido.")


def nearest_waypoint_index(waypoints, pos):
    cx, cy = pos[0], pos[1]
    return min(range(len(waypoints)),
               key=lambda i: abs(waypoints[i][0] - cx) + abs(waypoints[i][1] - cy))


def save_route(name, waypoints):
    with open(route_path(name), "w", encoding="utf-8") as f:
        json.dump(waypoints, f, indent=2, ensure_ascii=False)


def record_waypoints():
    clear_stop_request()
    if not config_ok():
        print("Faça a calibração primeiro.")
        return

    name = input("\nNome da rota: ").strip()
    if not name:
        return

    path = route_path(name)
    if os.path.exists(path):
        if input(f"A rota '{name}' já existe. Sobrescrever? (s/n): ").strip().lower() != "s":
            return

    waypoints = []
    last = None

    print("\nINSERT = adicionar waypoint | END = finalizar")
    print("O jogo deve ficar focado. Aguarde 3s...\n")
    sleep_interruptible(3.0)

    while True:
        if stop_requested() or keyboard.is_pressed("end"):
            break

        if keyboard.is_pressed("insert"):
            pos = read_coords_reliable(samples=3, delay=0.06, last_valid=last)
            if pos:
                if last and manhattan(pos, last) > 500:
                    print(f"Rejeitado: {wp_str(pos)} (salto muito grande)")
                else:
                    waypoints.append([pos[0], pos[1], pos[2]])
                    last = pos
                    print(f"[{len(waypoints)}] {wp_str(pos)}")
            else:
                print("Falha ao ler coordenadas.")
            sleep_interruptible(0.5)

        sleep_interruptible(0.05)

    if waypoints:
        save_route(name, waypoints)
        print(f"\n{len(waypoints)} waypoints salvos em '{name}'.")
    else:
        print("Nenhum waypoint gravado.")


def edit_waypoints():
    selected = select_route()
    if not selected:
        return
    waypoints, name = selected

    while True:
        print(f"\n[{name}] {len(waypoints)} pontos")
        print("[1] Ver")
        print("[2] Remover")
        print("[3] Adicionar posição atual")
        print("[4] Salvar")
        print("[5] Deletar rota")
        print("[0] Voltar")
        op = input("Opção: ").strip()

        if op == "1":
            for i, wp in enumerate(waypoints, start=1):
                print(f"  [{i}] {wp_str(wp)}")

        elif op == "2":
            for i, wp in enumerate(waypoints, start=1):
                print(f"  [{i}] {wp_str(wp)}")
            idx = input("Número para remover: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(waypoints):
                removed = waypoints.pop(int(idx) - 1)
                print(f"Removido: {wp_str(removed)}")

        elif op == "3":
            print("Clique no jogo / deixe o jogo focado. Lendo em 2s...")
            sleep_interruptible(2.0)
            pos = read_coords_reliable(samples=3, delay=0.06)
            if pos:
                waypoints.append([pos[0], pos[1], pos[2]])
                print(f"Adicionado: {wp_str(pos)}")
            else:
                print("Falha ao ler coordenadas.")

        elif op == "4":
            save_route(name, waypoints)
            print("Rota salva.")
            return

        elif op == "5":
            if input(f"Deletar '{name}'? (s/n): ").strip().lower() == "s":
                try:
                    os.remove(route_path(name))
                    print("Rota deletada.")
                except Exception as e:
                    print(f"Erro ao deletar: {e}")
                return

        elif op == "0":
            return


def rename_route():
    selected = select_route()
    if not selected:
        return
    _, old_name = selected

    new_name = input(f"Novo nome para '{old_name}': ").strip()
    if not new_name:
        return

    if os.path.exists(route_path(new_name)):
        print("Já existe uma rota com esse nome.")
        return

    os.rename(route_path(old_name), route_path(new_name))
    print("Rota renomeada com sucesso.")


# ============================================================
# REVIVE
# ============================================================
def hp_monitor_loop():
    cfg = require_config()
    hp_low_hist = deque(maxlen=max(3, int(cfg["hp_confirmacoes"])))
    mana_low_hist = deque(maxlen=max(3, int(cfg["hp_confirmacoes"])))
    last_revive = 0.0

    while not _stop_hp.is_set():
        frame = screenshot_bgr()
        status = build_revive_decision(frame, hp_low_hist, mana_low_hist, allow_update_mana_max=False)
        motivo = status["motivo"]

        if motivo and (time.time() - last_revive) > cfg["hp_cooldown"]:
            print(f"\n*** {motivo} - REVIVE ***")

            with _pyautogui_lock:
                soltar_todas_teclas()
                sleep_interruptible(0.06)
                send_revive_key()
                sleep_interruptible(0.22)

            last_revive = time.time()
            hp_low_hist.clear()
            mana_low_hist.clear()

        sleep_interruptible(0.12)


def start_revive_only():
    if not config_ok():
        print("Faça a calibração primeiro.")
        return

    cfg = require_config()
    print(f"\n=== MONITOR HP / MANA ===")
    print(f"Revive quando HP <= {cfg['hp_revive_percent']}% ou Mana <= {cfg['mana_revive_percent']}%")
    if cfg.get("mana_max_value"):
        print(f"Mana máxima aprendida: {cfg['mana_max_value']}")
    else:
        print("Mana máxima ainda não aprendida. Deixe a mana cheia uma vez ou configure manualmente em [I].")
    print("Pressione END para parar.\n")

    hp_low_hist = deque(maxlen=max(3, int(cfg["hp_confirmacoes"])))
    mana_low_hist = deque(maxlen=max(3, int(cfg["hp_confirmacoes"])))
    last_revive = 0.0

    while not stop_requested():
        frame = screenshot_bgr()
        status = build_revive_decision(frame, hp_low_hist, mana_low_hist, allow_update_mana_max=True)
        hp_pct = status["hp_pct"]
        mana_value = status["mana_value"]
        mana_pct = status["mana_pct"]
        mana_max = status["mana_max"]
        motivo = status["motivo"]

        hp_txt = "lendo..."
        mana_txt = format_mana_status(mana_pct, mana_value, mana_max)

        if hp_pct is not None:
            hp_txt = f"{hp_pct:5.1f}%"

        print(f"HP: {hp_txt} | Mana: {mana_txt}      ", end="\r")

        if motivo and (time.time() - last_revive) > cfg["hp_cooldown"]:
            print(f"\n*** {motivo} - REVIVE ***")
            with _pyautogui_lock:
                send_revive_key()
            last_revive = time.time()
            hp_low_hist.clear()
            mana_low_hist.clear()

        sleep_interruptible(0.12)

    print("\nMonitor parado.")


# ============================================================
# MOVIMENTO / CAVEBOT
# ============================================================
def move_to(tx, ty, stop_event):
    cfg = require_config()

    pos_ref = None
    tempo_ref = time.time()
    history = deque(maxlen=12)
    last_valid = None

    while not stop_event.is_set():
        if stop_requested() or keyboard.is_pressed("end"):
            soltar_todas_teclas()
            return "parado"

        pos = read_coords_filtered(last_valid=last_valid)
        if pos is None:
            sleep_interruptible(cfg["tick_movimento"], stop_event=stop_event)
            continue

        last_valid = pos
        cx, cy = pos[0], pos[1]
        dist = abs(cx - tx) + abs(cy - ty)

        if dist <= cfg["distancia_chegada"]:
            soltar_todas_teclas()
            return "chegou"

        if pos_ref is None:
            pos_ref = (cx, cy)
            tempo_ref = time.time()
        else:
            avanco = abs(cx - pos_ref[0]) + abs(cy - pos_ref[1])
            if avanco >= cfg["progresso_minimo"]:
                pos_ref = (cx, cy)
                tempo_ref = time.time()

        if time.time() - tempo_ref > cfg["timeout_waypoint"]:
            soltar_todas_teclas()
            print(f"  Timeout em ({tx},{ty}) - pulando")
            return "pulou"

        history.append((cx, cy))
        if len(history) >= 12:
            xs = [p[0] for p in history]
            ys = [p[1] for p in history]
            if max(xs) - min(xs) <= 1 and max(ys) - min(ys) <= 1:
                soltar_todas_teclas()
                print(f"  Travado em ({tx},{ty}) - pulando")
                return "pulou"

        keys = []
        if cx < tx:
            keys.append(cfg["teclas"]["right"])
        elif cx > tx:
            keys.append(cfg["teclas"]["left"])

        if cy < ty:
            keys.append(cfg["teclas"]["down"])
        elif cy > ty:
            keys.append(cfg["teclas"]["up"])

        with _pyautogui_lock:
            soltar_todas_teclas()
            for k in keys:
                pyautogui.keyDown(k)

        sleep_interruptible(cfg["tick_movimento"], stop_event=stop_event)

    soltar_todas_teclas()
    return "parado"


def start_cavebot(route_points, route_name):
    if not config_ok():
        print("Faça a calibração primeiro.")
        return

    clear_stop_request()

    print(f"\n=== CAVEBOT | {route_name} | {len(route_points)} waypoints ===")
    print("Pressione END para parar.")
    print("Iniciando em 5 segundos. Deixe o jogo focado.\n")

    for i in range(5, 0, -1):
        if stop_requested():
            print("Interrompido.")
            return
        print(f"{i}...")
        if not sleep_interruptible(1.0):
            print("Interrompido.")
            return

    pos0 = read_coords_reliable(samples=3, delay=0.06)
    if not pos0:
        print("Não consegui ler a posição inicial.")
        return

    idx_start = nearest_waypoint_index(route_points, pos0)
    print(f"Posição inicial: {wp_str(pos0)}")
    print(f"Waypoint inicial: #{idx_start + 1}\n")

    stop_event = threading.Event()
    round_n = 0

    while not stop_requested():
        round_n += 1
        print(f"--- Rodada {round_n} ---")

        start = idx_start if round_n == 1 else 0
        for i, wp in enumerate(route_points[start:], start=start):
            if stop_requested() or keyboard.is_pressed("end"):
                break

            print(f"  [{i+1}/{len(route_points)}] {wp_str(wp)}")
            result = move_to(wp[0], wp[1], stop_event)

            if result == "parado":
                print("Interrompido.")
                return

    soltar_todas_teclas()
    print("Cavebot parado.")


def start_cavebot_with_revive():
    clear_stop_request()
    selected = select_route()
    if not selected:
        return

    points, name = selected
    if not points:
        print("Rota vazia.")
        return

    # Depois de escolher a rota no console, devolvemos foco ao jogo.
    ensure_game_focus(delay_after_minimize=0.30)

    _stop_hp.clear()
    hp_thread = threading.Thread(target=hp_monitor_loop, daemon=True)
    hp_thread.start()

    try:
        start_cavebot(points, name)
    finally:
        _stop_hp.set()
        soltar_todas_teclas()
        restore_console()
        print("Monitor HP encerrado.")


# ============================================================
# TESTES
# ============================================================
def test_coords():
    clear_stop_request()
    if not config_ok():
        print("Faça a calibração primeiro.")
        return

    print("\n=== TESTE DE COORDENADAS ===")
    print("Pressione END para parar.\n")
    last = None

    while not stop_requested():
        frame = screenshot_bgr()
        raw = read_coords_raw_from_frame(frame)
        filt = raw

        if raw and last and manhattan(raw, last) > require_config()["coord_max_salto"]:
            filt = last

        if filt:
            last = filt
            print(f"Raw: {raw} | Usando: {filt}      ", end="\r")
        else:
            print("Lendo coordenadas...      ", end="\r")

        sleep_interruptible(0.12)

    print("\nTeste encerrado.")


def test_hp():
    clear_stop_request()
    if not config_ok():
        print("Faça a calibração primeiro.")
        return

    print("\n=== TESTE DE HP / MANA ===")
    print("Pressione END para parar.\n")
    while not stop_requested():
        frame = screenshot_bgr()
        hp = read_hp_percent_from_frame(frame)
        mana_value = read_mana_value_from_frame(frame)
        mana = read_mana_percent_from_frame(frame)

        cfg = require_config()
        mana_max = cfg.get("mana_max_value")

        hp_txt = "lendo..." if hp is None else f"{hp:5.1f}%"
        mana_txt = format_mana_status(mana, mana_value, mana_max)
        print(f"HP: {hp_txt} | Mana: {mana_txt}      ", end="\r")
        sleep_interruptible(0.12)
    print("\nTeste encerrado.")


# ============================================================
# CONFIGURAÇÕES RÁPIDAS
# ============================================================
def quick_settings():
    cfg = require_config()

    while True:
        print("\n=== CONFIGURAÇÕES ===")
        print(f"[1] HP revive % ............. {cfg['hp_revive_percent']}")
        print(f"[2] Mana revive % ........... {cfg['mana_revive_percent']}")
        print(f"[3] Confirmações HP/Mana .... {cfg['hp_confirmacoes']}")
        print(f"[4] Cooldown revive ......... {cfg['hp_cooldown']}")
        print(f"[5] Tecla revive ............ {cfg['tecla_revive']}")
        print(f"[6] Timeout waypoint ........ {cfg['timeout_waypoint']}")
        print(f"[7] Distância chegada ....... {cfg['distancia_chegada']}")
        print(f"[8] Máx salto coordenadas ... {cfg['coord_max_salto']}")
        print(f"[9] Mana máxima (OCR) ....... {cfg.get('mana_max_value')}")
        print("[0] Voltar")

        op = input("Escolha: ").strip()
        if op == "0":
            save_config()
            return

        elif op == "1":
            v = input("Novo HP revive (%): ").strip().replace(",", ".")
            try:
                cfg["hp_revive_percent"] = float(v)
            except Exception:
                print("Valor inválido.")

        elif op == "2":
            v = input("Novo Mana revive (%): ").strip().replace(",", ".")
            try:
                cfg["mana_revive_percent"] = float(v)
            except Exception:
                print("Valor inválido.")

        elif op == "3":
            v = input("Confirmações de HP/Mana baixo(a): ").strip()
            if v.isdigit():
                cfg["hp_confirmacoes"] = max(1, int(v))

        elif op == "4":
            v = input("Cooldown revive (s): ").strip().replace(",", ".")
            try:
                cfg["hp_cooldown"] = float(v)
            except Exception:
                print("Valor inválido.")

        elif op == "5":
            v = input("Tecla do revive: ").strip()
            if v:
                cfg["tecla_revive"] = v

        elif op == "6":
            v = input("Timeout do waypoint (s): ").strip().replace(",", ".")
            try:
                cfg["timeout_waypoint"] = float(v)
            except Exception:
                print("Valor inválido.")

        elif op == "7":
            v = input("Distância para considerar chegada: ").strip()
            if v.isdigit():
                cfg["distancia_chegada"] = max(0, int(v))

        elif op == "8":
            v = input("Máximo salto aceito nas coordenadas: ").strip()
            if v.isdigit():
                cfg["coord_max_salto"] = max(1, int(v))

        elif op == "9":
            v = input("Mana máxima (número inteiro, vazio para limpar): ").strip()
            if not v:
                cfg["mana_max_value"] = None
            elif v.isdigit():
                cfg["mana_max_value"] = int(v)
            else:
                print("Valor inválido.")

        save_config()


# ============================================================
# MENU
# ============================================================
def menu():
    load_config()
    ensure_hotkey()

    while True:
        clear_stop_request()
        print("\n╔════════════════════════════════════╗")
        print("║            PKMD BOT V11            ║")
        print("╠════════════════════════════════════╣")
        print("║  [A] Cavebot + Revive             ║")
        print("║  [B] Apenas Revive                ║")
        print("║  [C] Gravar Waypoints             ║")
        print("║  [D] Editar Waypoints             ║")
        print("║  [E] Renomear Rota                ║")
        print("║  [F] Calibrar / Recalibrar       ║")
        print("║  [G] Testar Coordenadas           ║")
        print("║  [H] Testar HP / Mana             ║")
        print("║  [I] Configurações                ║")
        print("║  [S] Sair                         ║")
        print("╚════════════════════════════════════╝")
        op = input("Escolha: ").strip().upper()

        if op == "A":
            start_cavebot_with_revive()
        elif op == "B":
            start_revive_only()
        elif op == "C":
            record_waypoints()
        elif op == "D":
            edit_waypoints()
        elif op == "E":
            rename_route()
        elif op == "F":
            calibrar()
        elif op == "G":
            test_coords()
        elif op == "H":
            test_hp()
        elif op == "I":
            quick_settings()
        elif op == "S":
            break
        else:
            print("Opção inválida.")


if __name__ == "__main__":
    try:
        pyautogui.FAILSAFE = False
        ensure_hotkey()
        menu()
    finally:
        soltar_todas_teclas()
        input("\nENTER para fechar...")
