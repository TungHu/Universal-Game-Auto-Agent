# 🎮 Universal Game Auto Agent

**AI tự động chơi game.** Chỉ cần screenshot + prompt, agent có thể chơi bất kỳ game nào.

## 🏗️ Kiến trúc

```
Smart_AI_Agent/
│
├── core/                          ← KHONG BAO GIO SUA
│   ├── capture.py                 ← Chup man hinh (mss)
│   ├── vision.py                  ← OCR / Template / Color detection
│   ├── brain.py                   ← AI Agent bridge (7 providers)
│   ├── controller.py              ← Chuot & phim (pyautogui)
│   └── region_selector.py         ← GUI chon vung game (tkinter)
│
├── games/                         ← Moi game 1 thu muc
│   ├── game_2048/
│   │   ├── config.json            ← API keys + cau hinh (da bi gitignore)
│   │   ├── config.template.json   ← File mau (dung de commit)
│   │   ├── prompt.txt             ← Huong dan AI cach choi
│   │   └── region.json            ← Toa do vung game (tu dong sinh)
│
├── .gitignore
├── requirements.txt
├── README.md
└── play.py                        ← Launcher DUY NHAT
```

## 🔄 Luồng xử lý

```
1. play.py doc games/game_xxx/config.json
2. capture.py chup man hinh (vung game da chon)
3. vision.py nhan dien board (OCR / template / color)
4. brain.py:
   a. Doc prompt.txt
   b. Thay {board} bang du lieu that
   c. Gui cho AI (1 trong 7 providers)
   d. AI tra ve: "down", "up", ...
5. controller.py thuc thi hanh dong (nhan phim/click chuot)
6. Lap lai
```

## ✅ Trạng thái hiện tại

| Module | Trạng thái | Chức năng |
|--------|-----------|-----------|
| `capture.py` | ✅ Hoàn thành | Chụp màn hình bằng mss |
| `vision.py` | ✅ Hoàn thành | OCR (Tesseract), template matching (OpenCV), color detection |
| `brain.py` | ✅ Hoàn thành | Kết nối 7 AI providers |
| `controller.py` | ⚠️ Đang debug | Điều khiển chuột/phím (pyautogui) |
| `region_selector.py` | ✅ Hoàn thành | GUI tkinter chọn vùng game |
| `play.py` | ✅ Hoàn thành | Launcher chính, CLI arguments |

### brain.py - 7 AI Providers ho tro

| Provider | Flag | API Key Env | Default Model |
|----------|------|-------------|---------------|
| **Gemini** | `--provider gemini` | `GEMINI_API_KEY` | gemini-2.0-flash |
| **OpenAI** | `--provider openai` | `OPENAI_API_KEY` | gpt-4o-mini |
| **Claude** | `--provider claude` | `ANTHROPIC_API_KEY` | claude-3-haiku |
| **Groq** | `--provider groq` | `GROQ_API_KEY` | llama-3.3-70b |
| **DeepSeek** | `--provider deepseek` | `DEEPSEEK_API_KEY` | deepseek-chat |
| **OpenRouter** | `--provider openrouter` | `OPENROUTER_API_KEY` | openai/gpt-4o-mini |
| **Ollama** | `--provider ollama` | (local, free) | llama3.2 |

## 📦 Cài đặt

```bash
# 1. Clone repo
git clone https://github.com/TungHu/Universal-Game-Auto-Agent.git
cd Universal-Game-Auto-Agent

# 2. Cai dependencies
pip install -r requirements.txt

# 3. Cai Tesseract OCR (neu dung OCR)
# Download: https://github.com/UB-Mannheim/tesseract/wiki

# 4. Cau hinh API keys
cp games/game_2048/config.template.json games/game_2048/config.json
# Sau do mo config.json va dien API key vao providers tuong ung
```

## 🚀 Cách dùng

### Chay game 2048

```bash
# Lan dau: chon vung game thu cong
python play.py 2048

# Lan sau: tu dong dung region da luu
python play.py 2048
```

### CLI Options

```bash
python play.py <game> [options]

Options:
  --select-region              Chon lai vung game
  --provider {gemini,openai,claude,groq,deepseek,openrouter,ollama}
                               AI provider
  --interval INTERVAL          Toc do loop (giay)
  --model MODEL                Model AI
```

### Vi du

```bash
# Dung Groq (free, nhanh)
python play.py 2048 --provider groq

# Dung OpenAI GPT-4o
python play.py 2048 --provider openai --model gpt-4o

# Override model
python play.py 2048 --provider groq --model llama-3.3-70b-versatile

# Chon lai vung game
python play.py 2048 --select-region

# Toc do cham hon (0.5s giua cac nuoc di)
python play.py 2048 --interval 0.5
```

### Dung API key tu environment variable

```bash
set GEMINI_API_KEY=AIza...
set OPENAI_API_KEY=sk-...
set GROQ_API_KEY=gsk_...
set ANTHROPIC_API_KEY=sk-ant-...
set DEEPSEEK_API_KEY=sk-...
set OPENROUTER_API_KEY=sk-or-...

python play.py 2048 --provider groq
```

## 🎮 Cách thêm game mới

Chi can 2 thu:

### Buoc 1: Tao thu muc game

```bash
mkdir games/game_flappy_bird
```

### Buoc 2: Tao config + prompt

**config.json:**
```json
{
  "name": "flappy_bird",
  "vision": {
    "type": "ocr",
    "board_size": [1, 1]
  },
  "control": {
    "type": "keyboard",
    "keys": ["space"]
  },
  "ai_provider": "openai",
  "loop_interval": 0.1,
  "providers": { ... }
}
```

**prompt.txt:**
```
Ban la AI choi game Flappy Bird.
Trang thai hien tai: {board}

Luat: Nhan SPACE de bay qua ong.
Chi tra loi 1 tu: space
```

### Buoc 3: Chay

```bash
python play.py flappy_bird
```

## 🔑 API Keys

Lay API key mien phi tu cac dich vu sau:

| Provider | Link | Free Tier |
|----------|------|-----------|
| Groq | https://console.groq.com/keys | ✅ 30 req/min |
| Gemini | https://aistudio.google.com/apikey | ✅ 60 req/min |
| DeepSeek | https://platform.deepseek.com/ | ✅ $5 free credit |
| OpenRouter | https://openrouter.ai/keys | ✅ Nhieu model free |
| OpenAI | https://platform.openai.com/api-keys | ❌ Can nap tien |
| Anthropic | https://console.anthropic.com/ | ❌ Can nap tien |

## 📝 Ghi chu

- `config.json` chua API keys -> **da them vao .gitignore**
- `config.template.json` la file mau -> **commit len GitHub**
- De them game moi, chi can tao thu muc `games/game_xxx/` + `config.json` + `prompt.txt`
- `controller.py` da ho tro click toa do / phim / hotkey / scroll / type (pynput)

## Workflows

Workflow mode cho phep tu dong hoa cac tac vu phuc tap (CapCut, browser, ...).

### Cau truc workflow

```
workflows/
  workflow_capcut/
    steps.json        <- Danh sach buoc
    config.json       <- API keys (gitignore)
    config.template.json <- Mau config (commit)
    region.json       <- Vung man hinh (tu workflow selector)
```

### Chay workflow

```bash
# Liet ke workflows
python play.py --list

# Chay CapCut workflow (tu dong chon vung man hinh o buoc dau)
python play.py --workflow capcut

# Dry run (khong click, chi in hanh dong)
python play.py --workflow capcut --dry-run

# Lap 3 lan
python play.py --workflow capcut --repeat 3

# Debug AI (luu anh + replies)
python play.py --workflow capcut --debug-ai

# Khong hoi chon vung, dung region.json cu
python play.py --workflow capcut --no-region-prompt

# Chon lai vung
python play.py --workflow capcut --select-region

# Dung toan man hinh lam vung (khong hien GUI chon)
python play.py --workflow capcut --region fullscreen

# Dung region tu 1 file json bat ki
python play.py --workflow capcut --region workflows/workflow_capcut/region.json

# TEST khong can API key: AI gia + khong click that
python play.py --workflow capcut --mock-ai --dry-run --repeat 1
```

### Anh mau (reference images)

Workflow doc anh mau trong `input_picture/` (cau hinh bang `image_dir` trong `steps.json`).
Vi du: `input_picture/1.jpg` .. `input_picture/7.jpg` tuong ung 7 man hinh CapCut.
Anh mau la anh chup man hinh dien thoai 720x1600, nen hay chon vung game /
cua so scrcpy co ti le tuong ung de toa do AI tra ve chinh xac.

### Test khong can API key

| Flag | Tac dung |
|---|---|
| `--mock-ai` | Khong goi API, AI tra ve JSON gia (found=true, same=true, count=2) |
| `--dry-run` | Khong click / khong nhan phim that, chi in ra man hinh |
| `--repeat N` | Chay dung N chu ky roi thoat (0 = vo han) |

### Buoc dau tien: chon vung man hinh

Khi chay workflow, buoc dau tien la chon vung man hinh:
- Keo chuot chon vung emulator/app
- **R** = dung lai vung da luu lan truoc
- **Enter** = xac nhan
- **Esc** = huy

Vung duoc luu vao `workflows/workflow_capcut/region.json`.

### Cac loai action trong steps.json

| action.type | Mo ta |
|---|---|
| `ai` (mac dinh) | AI vision tim & click theo mo ta |
| `random_pick` | Chon ngau nhien N item trong grid, tu cuon, chong trung |
| `back_until` | Nhan Back lap cho den khi thay lai anh mau |
| `key` / `hotkey` / `type` | Nhan phim / to hop / go ch |
| `scroll` | Cuon chuot |
| `wait` | Cho N giay |
| `check` | Chi xac nhan khong click |

#### random_pick

```json
{
  "action": {
    "type": "random_pick",
    "count": 2,
    "cols": 3, "rows": 3,
    "grid": [0.01, 0.20, 0.99, 0.68],
    "avoid_repeat": true,
    "verify_count": true,
    "scroll": { "enabled": true, "times": [1, 3], "amount": [300, 800] }
  }
}
```

| Key | Y nghia |
|---|---|
| `count` | So item can chon |
| `cols` / `rows` | Chia vung luoi anh thanh bao nhieu cot / dong |
| `grid` | Vung luoi theo ti le vung game `[left, top, right, bottom]` (0.0 - 1.0) |
| `avoid_repeat` | Bo qua o da chon o lan truoc (luu trong `used_photos.json`) |
| `verify_count` | Nho AI dem lai so item da chon (chi canh bao, khong fail) |
| `scroll` | Khi het o trong thi cuon them de load anh moi |

`used_photos.json` luu fingerprint (MD5) cua tung o da click. Khi het anh moi,
workflow se cuon toi da 3 lan, sau do cho phep dung lai anh cu de khong bi ket.

### Providers ho tro AI Vision

Chi nhung provider nao ho tro multimodal (xem anh):
- **Gemini** (`gemini-2.0-flash`)
- **OpenAI** (`gpt-4o-mini`, `gpt-4o`)
- **Claude** (`claude-3-haiku-20240307`)
- **Ollama** (`llama3.2-vision`)

Groq, DeepSeek, OpenRouter chi ho tro text -> khong dung duoc voi workflow.
