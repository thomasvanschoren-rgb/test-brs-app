[app]
# Name of your app as shown on the phone
title = BRS Launcher

# Internal package name (unique identifier)
package.name = brslauncher
package.domain = org.example

# Main entry point
source.dir = .
source.main = main.py

# List of included files & folders
source.include_exts = py,png,jpg,jpeg,mp3,wav,ogg,ttf,kv
source.include_patterns = assets/*

# Version
version = 0.1

# Supported orientation
orientation = landscape

# Fullscreen
fullscreen = 1

# Required Python/Kivy modules
requirements = python3,kivy,plyer,jnius

# Permissions (vibrate is just for example)
android.permissions = VIBRATE

# Minimum and target Android API levels
android.api = 30
android.minapi = 21

# Architectures to build for
android.archs = arm64-v8a, armeabi-v7a

# Intent filter so Android sees it as a home launcher
android.manifest.intent_filters = <intent-filter>
    <action android:name="android.intent.action.MAIN" />
    <category android:name="android.intent.category.HOME" />
    <category android:name="android.intent.category.DEFAULT" />
</intent-filter>

# Keep the screen awake
android.wakelock = True

# Application icon (optional — replace with your image)
icon.filename = assets/icon.png


[buildozer]
# Buildozer settings
log_level = 2
warn_on_root = 1

# For GitHub Actions or cloud builds
# This prevents interactive prompts
requirement_rebuild = 1
