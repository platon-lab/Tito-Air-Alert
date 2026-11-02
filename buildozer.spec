[app]
title = Tito Air Alert
package.name = airalert
package.domain = org.tito
source.dir = .
source.include_exts = py,png,jpg,json
source.exclude_dirs = .git,.github,data,bin,vendor,.buildozer
version = 1.0.0

requirements = python3,kivy==2.3.0,pyjnius,android

# Закрепляем python-for-android, чтобы собиралась совместимая версия Python (3.11)
p4a.branch = v2024.01.21

orientation = portrait
fullscreen = 0

services = alertmonitor:service.py:foreground

android.permissions = INTERNET,SYSTEM_ALERT_WINDOW,FOREGROUND_SERVICE,WAKE_LOCK,POST_NOTIFICATIONS,MODIFY_AUDIO_SETTINGS
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.logcat_filters = *:S python:D

[buildozer]
log_level = 2
warn_on_root = 1
