# BO THAO TAC (input sets)

Moi **bo** la 1 thu muc rieng, chua **mo ta buoc** va **anh cua bo do**.
Muc dich: chuyen doi qua lai giua bo cu va bo moi ma khong sua file chung.

```
input/
├── capcut_cu/          ← bo cu (dang chay tot)
│   ├── steps.json      ← mo ta cac buoc
│   └── images/         ← anh cua bo nay
│       ├── 1.jpg       ← anh man hinh day du
│       ├── 1x.png      ← template nho, tim vi tri dong
│       └── ...
└── capcut_moi/         ← bo moi
    ├── steps.json
    └── images/
```

## Quy tac dat ten anh

| Ten trong `steps.json` | File trong `images/` | Dung khi |
|---|---|---|
| `"image": "1"` | `1.jpg` | Buoc dung AI, khong co template |
| `"template": "1x"` | `1x.png` | Buoc tim vi tri dong, khong goi API |

Dat dung ten la chay, khong can khai bao duong dan.
Ho tro: `.png`, `.jpg`, `.jpeg`, `.webp`.

## Cac lenh

```bash
# Xem cac bo dang co
python play.py --list-sets

# Tao bo moi (copy steps.json tu bo cu)
python play.py --workflow capcut --new-set capcut_moi --from-set capcut_cu

# Kiem tra bo: thieu anh, anh thua, steps sai cu phap
python play.py --workflow capcut --set capcut_moi --check

# Chay bo
python play.py --workflow capcut --set capcut_moi

# Quay lai bo cu
python play.py --workflow capcut --set capcut_cu
```

## Tim anh theo thu tu uu tien

```
1. images/ cua bo dang chay
2. images/ cua cac bo khac
3. input_picture/ (anh goc cua project)
```

Vay bo moi chi can put anh **cac buoc khac biet** vao, phan con lai
tu len lay tu bo cu. Muon bo nao doc lap hon 100%, bo het
`input_picture/` vao `.gitignore` cua rieng bo do.

## Cac truong dac biet cua action `back_until`

| Truong | Y nghia |
|---|---|
| `until_template` | Dieu kien dung: bam Back cho toi khi thay template nay |
| `wait_for` | **Cho man hinh nay xuat hien truoc**, roi moi bat dau bam Back |
| `wait_for_timeout` | Cho toi da bao lau (giay) |
| `settle` | Nghi them sau khi man hinh da xuat hien (giay) |
| `max_presses` | Toi da bam Back toi da |
| `wait_after_each` | Nghi giua cac lan bam (giay) |
| `back.point` | Toa do phan tram de bam nut Back |

Vi du: cho man hinh "Saved to phone album" hien len, roi bam Back toi khi
ve man hinh chinh:

```json
{
  "until_template": "1x",
  "action": {
    "type": "back_until",
    "wait_for": "7x",
    "wait_for_timeout": 40.0,
    "settle": 1.5,
    "max_presses": 4,
    "wait_after_each": 2.0,
    "back": { "type": "click_pct", "point": [0.771, 0.972] }
  }
}
```

## Luu y

- `steps.json` cua bo **la ban sao rieng**, sua tu do, khong sua bo khac.
- `region.json` nam o `workflows/workflow_capcut/`, dung chung cho moi bo
  (vi tri cua so game).
- `used_photos.json` va `debug/` sinh ra khi chay, khong can copy.
