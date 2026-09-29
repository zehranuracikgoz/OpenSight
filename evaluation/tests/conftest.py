import os
import sys

# evaluate.py, evaluation/ dizininde tests/'in bir üstünde - nereden çalıştırıldığına
# bakılmadan import edilebilsin diye sys.path'e ekliyor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
