"""功能註冊表：新增功能時，在這裡 import 並加進 FEATURES 就會自動出現在側邊欄。"""
from features import bus_schedule, exam_reminder, home

FEATURES = [
    home.FEATURE,
    exam_reminder.FEATURE,
    bus_schedule.FEATURE,
    # my_new_feature.FEATURE,   # ← 新功能加在這一行
]
