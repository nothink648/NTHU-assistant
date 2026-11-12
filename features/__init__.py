"""功能註冊表：新增功能時，在這裡 import 並加進 FEATURES 就會自動出現在側邊欄。"""
from features import bus_schedule, campus_map, exam_reminder, home, restaurants, timetable

FEATURES = [
    home.FEATURE,
    timetable.FEATURE,
    exam_reminder.FEATURE,
    restaurants.FEATURE,
    bus_schedule.FEATURE,
    campus_map.FEATURE,
    # my_new_feature.FEATURE,   # ← 新功能加在這一行
]
