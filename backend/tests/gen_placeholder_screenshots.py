"""生成 AgentLens README 占位截图（差异化 SVG 转 PNG）。

不调 AI 生成，用 Pillow 绘制：
- 框架：侧栏 + 顶部 Header + 4 个 tab 导航
- 主体：每个视图差异化（列表/调用树/时间线/消息流/IO/会话）
- 数据：完全占位（lipsum + hash，不展示真实数据）

风格：浅色背景、靛蓝主调、橙色 highlight，模拟真实 UI。
"""
from pathlib import Path
import hashlib
from PIL import Image, ImageDraw, ImageFont


# ---- 字体 ----
def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for c in candidates:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except OSError:
                continue
    return ImageFont.load_default()


# ---- 配色（AgentLens 主题）----
COLORS = {
    "bg": (248, 250, 252),           # slate-50
    "sidebar": (15, 23, 42),         # slate-900
    "header": (255, 255, 255),
    "card": (255, 255, 255),
    "border": (226, 232, 240),       # slate-200
    "text": (15, 23, 42),
    "muted": (100, 116, 139),        # slate-500
    "subtle": (148, 163, 184),       # slate-400
    "primary": (79, 70, 229),        # indigo-600
    "primary_bg": (238, 242, 255),   # indigo-50
    "mw": (251, 146, 60),            # orange-400
    "mw_bg": (255, 237, 213),        # orange-100
    "mw_border": (253, 186, 116),    # orange-300
    "success": (16, 185, 129),       # emerald-500
    "error": (239, 68, 68),          # red-500
    "tool": (245, 158, 11),          # amber-500
    "tool_bg": (254, 243, 199),      # amber-100
    "ai_bg": (243, 232, 255),        # violet-100
    "user_bg": (219, 234, 254),      # blue-100
    "system_bg": (241, 245, 249),    # slate-100
    "summary": (168, 85, 247),       # purple-500
    "summary_bg": (243, 232, 255),   # purple-100
}

W, H = 1280, 800


# ---- 通用框架 ----
def draw_frame(draw: ImageDraw.ImageDraw, title: str = "AgentLens"):
    """画侧栏 + 顶部 header + tab nav。"""
    # 侧栏
    draw.rectangle((0, 0, 240, H), fill=COLORS["sidebar"])
    draw.rectangle((12, 18, 44, 50), fill=COLORS["primary"])  # logo
    draw.text((54, 18), title, font=get_font(15, True), fill=(255, 255, 255))
    draw.text((54, 38), "Agent Observability", font=get_font(10), fill=(100, 116, 139))
    # 导航
    draw.rectangle((12, 80, 228, 110), fill=(30, 41, 59))
    draw.text((28, 88), "Traces", font=get_font(13), fill=(255, 255, 255))
    # footer
    draw.text((28, H - 30), "v0.5.0", font=get_font(10), fill=(71, 85, 105))

    # 顶部 header
    draw.rectangle((240, 0, W, 60), fill=COLORS["header"], outline=COLORS["border"])
    draw.text((260, 18), "weather-agent", font=get_font(18, True), fill=COLORS["text"])
    draw.text((260, 42), "session-001 · 3 calls · 1.2s", font=get_font(11), fill=COLORS["muted"])

    # 4 个 tab
    tabs = ["调用树", "时间线", "消息流", "IO"]
    x = 240
    for i, tab in enumerate(tabs):
        tw = 80
        if i == 0:  # 当前 tab
            draw.rectangle((x, 60, x + tw, 100), fill=COLORS["bg"])
            draw.text((x + 16, 73), tab, font=get_font(13, True), fill=COLORS["primary"])
            draw.line((x, 100, x + tw, 100), fill=COLORS["primary"], width=2)
        else:
            draw.text((x + 16, 73), tab, font=get_font(13), fill=COLORS["muted"])
        x += tw


# ---- 列表页 ----
def draw_list(draw: ImageDraw.ImageDraw):
    draw_frame(draw)
    # trace 卡片
    y = 120
    traces = [
        ("weather-agent", "session-001", "1.2s", "3 calls", "2 min ago", "success"),
        ("doc-qa-agent", "session-002", "0.8s", "1 call", "5 min ago", "success"),
        ("middleware-e2e-test", "—", "0.3s", "1 call", "8 min ago", "success"),
        ("summarization-effect-test", "session-003", "2.1s", "2 calls", "10 min ago", "success"),
    ]
    for name, thread, dur, calls, ago, status in traces:
        draw.rounded_rectangle((260, y, W - 20, y + 56), radius=8, fill=COLORS["card"], outline=COLORS["border"])
        # icon
        draw.rounded_rectangle((276, y + 12, 308, y + 44), radius=6, fill=COLORS["primary_bg"])
        draw.text((286, y + 19), "AI", font=get_font(11, True), fill=COLORS["primary"])
        # name
        draw.text((324, y + 12), name, font=get_font(13, True), fill=COLORS["text"])
        # thread 徽章
        if thread != "—":
            draw.rounded_rectangle((324, y + 30, 408, y + 46), radius=3, fill=COLORS["primary_bg"])
            draw.text((330, y + 33), thread, font=get_font(10), fill=COLORS["primary"])
        # 右侧
        draw.text((W - 240, y + 12), dur, font=get_font(12, True), fill=COLORS["text"])
        draw.text((W - 240, y + 32), calls, font=get_font(10), fill=COLORS["muted"])
        draw.text((W - 120, y + 12), ago, font=get_font(10), fill=COLORS["muted"])
        # 状态点
        draw.ellipse((W - 36, y + 24, W - 28, y + 32), fill=COLORS["success"])
        y += 68


# ---- 调用树 ----
def draw_call_tree(draw: ImageDraw.ImageDraw):
    draw_frame(draw)
    nodes = [
        (0, "agent", "ReactAgent", "1.2s", "chain", False),
        (1, "PIIMiddleware", "PIIMiddleware[custom].before_model", "0.05s", "chain", True),
        (1, "model", "qwen-flash", "0.8s", "llm", False),
        (1, "SummarizationMiddleware", "SummarizationMiddleware.after_model", "0.2s", "chain", True),
    ]
    y = 120
    for depth, kind, name, dur, type_badge, is_mw in nodes:
        x = 260 + depth * 24
        # 缩进线
        if depth > 0:
            draw.line((x - 12, y + 18, x, y + 18), fill=COLORS["border"])
        # icon
        icon_color = COLORS["mw"] if is_mw else (
            COLORS["primary"] if type_badge == "chain" else COLORS["tool"]
        )
        icon_bg = COLORS["mw_bg"] if is_mw else (
            COLORS["primary_bg"] if type_badge == "chain" else COLORS["tool_bg"]
        )
        draw.rounded_rectangle((x, y, x + 24, y + 24), radius=4, fill=icon_bg)
        draw.text((x + 6, y + 5), "⚙" if is_mw else "📦", font=get_font(11), fill=icon_color)
        # 卡片
        cw, ch = 720, 40
        border = COLORS["mw_border"] if is_mw else COLORS["border"]
        draw.rounded_rectangle((x + 32, y, x + 32 + cw, y + ch), radius=6,
                               fill=COLORS["card"], outline=border, width=2 if is_mw else 1)
        # name
        draw.text((x + 44, y + 6), name, font=get_font(12, True), fill=COLORS["text"])
        # type badge
        if is_mw:
            draw.rounded_rectangle((x + 44, y + 22, x + 134, y + 35), radius=3, fill=COLORS["mw_bg"])
            draw.text((x + 50, y + 23), "Middleware", font=get_font(9), fill=COLORS["mw"])
        else:
            draw.rounded_rectangle((x + 44, y + 22, x + 100, y + 35), radius=3, fill=COLORS["primary_bg"])
            draw.text((x + 50, y + 23), type_badge, font=get_font(9), fill=COLORS["primary"])
        # 右侧
        draw.text((x + 32 + cw - 60, y + 14), dur, font=get_font(11, True), fill=COLORS["text"])
        y += 52


# ---- 时间线 ----
def draw_timeline(draw: ImageDraw.ImageDraw):
    draw_frame(draw)
    events = [
        (1, "chain_start", "agent", "10:00:00.001", False),
        (2, "chain_start", "PIIMiddleware[custom].before_model", "10:00:00.005", True),
        (3, "chain_end", "PIIMiddleware", "10:00:00.055", True),
        (2, "chat_model_start", "qwen-flash", "10:00:00.060", False),
        (3, "llm_end", "qwen-flash", "10:00:00.860", False),
        (2, "chain_start", "SummarizationMiddleware.after_model", "10:00:00.870", True),
        (3, "chain_end", "SummarizationMiddleware", "10:00:01.070", True),
        (1, "chain_end", "agent", "10:00:01.200", False),
    ]
    # 时间轴
    draw.line((290, 120, 290, H - 60), fill=COLORS["border"], width=1)
    y = 120
    for idx, etype, name, ts, is_mw in events:
        x = 260 + idx * 20
        # 圆点
        dot_color = COLORS["mw"] if is_mw else COLORS["primary"]
        draw.ellipse((x - 4, y + 14, x + 4, y + 22), fill=dot_color)
        # 卡片
        draw.rounded_rectangle((x + 16, y, x + 16 + 760, y + 36), radius=6,
                               fill=COLORS["card"], outline=COLORS["border"])
        # 序号
        draw.rounded_rectangle((x + 22, y + 8, x + 50, y + 22), radius=3, fill=COLORS["bg"])
        draw.text((x + 30, y + 9), f"#{idx}", font=get_font(9), fill=COLORS["subtle"])
        # type badge
        draw.text((x + 56, y + 8), etype, font=get_font(10, True), fill=COLORS["text"])
        # name
        if is_mw:
            draw.rounded_rectangle((x + 130, y + 6, x + 250, y + 22), radius=3, fill=COLORS["mw_bg"])
            draw.text((x + 136, y + 9), "⚙ " + name, font=get_font(9), fill=COLORS["mw"])
        else:
            draw.text((x + 130, y + 9), name, font=get_font(10), fill=COLORS["text"])
        # 时间
        draw.text((x + 660, y + 10), ts, font=get_font(10), fill=COLORS["muted"])
        y += 44


# ---- 消息流 ----
def draw_message_flow(draw: ImageDraw.ImageDraw):
    draw_frame(draw)
    msgs = [
        ("user", "广州今天天气如何？", False, None),
        ("ai", "正在查询广州天气...", True, None),
        ("mw_banner", None, None, "PIIMiddleware · 检测到 手机×1"),
        ("ai", "[REDACTED_PHONE] 今天晴朗 25°C", False, None),
        ("mw_banner", None, None, "SummarizationMiddleware · 历史 12 条 → 压缩后 5 条"),
        ("summary", "Here is a summary of the conversation:\n- User asked about weather", False, None),
    ]
    y = 120
    for kind, content, _thinking, banner in msgs:
        if kind == "mw_banner":
            draw.rounded_rectangle((280, y, W - 20, y + 32), radius=4, fill=COLORS["mw_bg"], outline=COLORS["mw_border"])
            draw.text((300, y + 8), "⚙ " + banner, font=get_font(11), fill=COLORS["mw"])
            y += 40
            continue
        if kind == "summary":
            draw.rounded_rectangle((320, y, W - 20, y + 64), radius=10, fill=COLORS["summary_bg"], outline=COLORS["summary"])
            draw.text((336, y + 8), "📄 Summary (压缩)", font=get_font(11, True), fill=COLORS["summary"])
            draw.text((336, y + 24), "by SummarizationMiddleware", font=get_font(9), fill=COLORS["summary"])
            draw.text((336, y + 42), content, font=get_font(11), fill=COLORS["text"])
            y += 76
            continue
        # 普通消息
        if kind == "user":
            x = 600
            bg = COLORS["user_bg"]
        else:
            x = 280
            bg = COLORS["ai_bg"] if not _thinking else COLORS["card"]
        draw.rounded_rectangle((x, y, x + 380, y + 56), radius=10, fill=bg, outline=COLORS["border"])
        draw.text((x + 16, y + 8), "用户" if kind == "user" else "AI", font=get_font(10, True), fill=COLORS["muted"])
        # content
        text = content or ""
        # 简单截断
        if len(text) > 38:
            text = text[:38] + "..."
        draw.text((x + 16, y + 24), text, font=get_font(11), fill=COLORS["text"])
        y += 68


# ---- IO 详情 ----
def draw_io(draw: ImageDraw.ImageDraw):
    draw_frame(draw)
    # 顶部事件列表
    events = ["chain_start", "PIIMiddleware", "model", "llm_end", "SummarizationMiddleware", "chain_end"]
    y = 120
    for ev in events:
        is_mw = "Middleware" in ev
        draw.rounded_rectangle((260, y, 520, y + 32), radius=4, fill=COLORS["card"], outline=COLORS["border"])
        if is_mw:
            draw.rounded_rectangle((268, y + 6, 286, y + 24), radius=3, fill=COLORS["mw"])
            draw.text((272, y + 8), "⚙", font=get_font(10), fill=(255, 255, 255))
        draw.text((296, y + 8), ev, font=get_font(11, True), fill=COLORS["text"])
        y += 40
    # 右侧 JSON viewer
    draw.rounded_rectangle((540, 120, W - 20, H - 40), radius=8, fill=COLORS["card"], outline=COLORS["border"])
    draw.text((556, 132), "事件详情 · PIIMiddleware[custom].before_model", font=get_font(12, True), fill=COLORS["text"])
    # JSON
    json_lines = [
        ('{', COLORS["text"]),
        ('  "inputs": {', COLORS["text"]),
        ('    "messages": [', COLORS["text"]),
        ('      {', COLORS["text"]),
        ('        "role": "user",', COLORS["primary"]),
        ('        "content": "我的手机是 13800138000",', COLORS["success"]),
        ('      }', COLORS["text"]),
        ('    ]', COLORS["text"]),
        ('  },', COLORS["text"]),
        ('  "outputs": {', COLORS["text"]),
        ('    "messages": [', COLORS["text"]),
        ('      {', COLORS["text"]),
        ('        "content": "[REDACTED_PHONE] 今天晴",', COLORS["tool"]),
        ('      }', COLORS["text"]),
        ('    ]', COLORS["text"]),
        ('  }', COLORS["text"]),
        ('}', COLORS["text"]),
    ]
    yy = 168
    for line, color in json_lines:
        draw.text((556, yy), line, font=get_font(11), fill=color)
        yy += 18


# ---- 会话详情 ----
def draw_thread(draw: ImageDraw.ImageDraw):
    draw_frame(draw)
    # header 区域增强
    draw.text((260, 90), "Thread: session-001", font=get_font(14, True), fill=COLORS["text"])
    # trace 切分条
    traces = [
        ("调用 #1 · 10:00:00 · 0.4s", COLORS["primary_bg"]),
        ("调用 #2 · 10:00:30 · 0.5s", COLORS["tool_bg"]),
        ("调用 #3 · 10:01:00 · 0.3s", COLORS["mw_bg"]),
    ]
    y = 120
    for label, color in traces:
        draw.rounded_rectangle((260, y, W - 20, y + 28), radius=4, fill=color, outline=COLORS["border"])
        draw.text((276, y + 7), label, font=get_font(11, True), fill=COLORS["text"])
        y += 36
    # 模拟合并事件时间线
    events = [
        (True, "#1", "chain_start", "agent"),
        (True, "#1", "chain_end", "agent"),
        (False, "#2", "chain_start", "agent"),
        (False, "#2", "PIIMiddleware", "before_model"),
        (False, "#2", "chain_end", "PIIMiddleware"),
        (True, "#3", "chain_start", "agent"),
        (True, "#3", "chain_end", "agent"),
    ]
    y += 4
    for is_first, source, etype, name in events:
        draw.rounded_rectangle((260, y, W - 20, y + 28), radius=4, fill=COLORS["card"], outline=COLORS["border"])
        draw.rounded_rectangle((268, y + 6, 308, y + 22), radius=3, fill=COLORS["primary_bg"])
        draw.text((276, y + 8), source, font=get_font(9), fill=COLORS["primary"])
        draw.text((316, y + 8), f"{etype} · {name}", font=get_font(10), fill=COLORS["text"])
        y += 32


# ---- 入口 ----
SCREENS = [
    ("01-trace-list.png", draw_list, "Trace List"),
    ("02-call-tree.png", draw_call_tree, "Call Tree"),
    ("03-timeline.png", draw_timeline, "Timeline"),
    ("04-message-flow.png", draw_message_flow, "Message Flow"),
    ("05-io-detail.png", draw_io, "IO Detail"),
    ("06-thread-detail.png", draw_thread, "Thread Detail"),
]

OUT_DIR = Path(r"C:\Workspace\Development\Study\study_langchain\docs\screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    for name, drawer, label in SCREENS:
        img = Image.new("RGB", (W, H), COLORS["bg"])
        d = ImageDraw.Draw(img)
        drawer(d)
        path = OUT_DIR / name
        img.save(path, optimize=True)
        print(f"OK {label:20s} -> {path.name}  ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
