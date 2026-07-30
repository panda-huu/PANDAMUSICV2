# 𝗣𝗔𝗡𝗗𝗔 𝗠𝗨𝗦𝗜𝗖 𝗩2 🥰

Advanced Telegram VC Music Bot (based on AdityaPlayer structure).

## Folder Structure

- `PANDAMUSIC/` — main package (renamed from AdityaHalder)
- `main.py` — entry point
- `Config.env` — fill your variables here
- `requirements.txt`

## Quick Start (VPS)

```bash
apt update -y && apt install sudo -y && sudo apt install curl ffmpeg git nano python3-pip screen -y
cd && git clone https://github.com/panda-huu/PANDAMUSICV2 && cd PANDAMUSICV2
pip3 install -r requirements.txt --force-reinstall
nano Config.env   # fill your vars
screen -R PANDAMUSIC
python3 -m PANDAMUSIC
```

## Commands

- Music: /play /vplay /pause /resume /skip /end
- Welcome: /welcome on|off  /setwelcome  /resetwelcome
- Moderation, Chatbot, Abuse filter also included

Made with ❤️ for Panda
