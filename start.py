import subprocess
import sys
import os

bot = subprocess.Popen([sys.executable, "bot.py"])
painel = subprocess.Popen([sys.executable, "-m", "painel.app"])

try:
    bot.wait()
except KeyboardInterrupt:
    bot.terminate()
    painel.terminate()
