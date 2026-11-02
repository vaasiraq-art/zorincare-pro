"""Bilingual English + Arabic (العربية) i18n and persistent user settings."""

from __future__ import annotations

import json
from typing import Any
from zorincare import get_config_dir

SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "language": "en",          # "en" or "ar"
    "theme": "cyber_dark",     # "cyber_dark" or "zorin_native"
    "revo_scan_mode": "moderate",  # "safe", "moderate", "advanced"
    "backup_before_uninstall": True,
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # App & Header
        "app_title": "ZorinCare Pro",
        "app_subtitle": "Zorin OS 18.1 Pro Ultimate System Suite",
        "lang_switch_btn": "العربية",
        "theme_cyber": "Cyber Neon",
        "theme_native": "Zorin Native",
        "theme_toggle_tip": "Switch UI Theme (IObit Cyber Dark / Zorin Native)",
        "lang_toggle_tip": "Switch Language (English / العربية)",
        "log_drawer_btn": "Activity Log",
        "status_ready": "Ready — System Protected",
        "status_working": "Working...",
        "refresh": "Refresh",
        "apply": "Apply",
        "cancel": "Cancel",
        "close": "Close",
        "yes": "Yes",
        "no": "No",
        "enabled": "Enabled",
        "disabled": "Disabled",
        "active": "Active",
        "inactive": "Inactive",
        "installed": "Installed",
        "not_installed": "Not Installed",
        "recommended": "Recommended",

        # Sidebar Navigation
        "nav_care": "Smart SystemCare",
        "nav_care_sub": "1-Click Scan & Junk Cleaner",
        "nav_booster": "Turbo Boost",
        "nav_booster_sub": "RAM, Power & Kernel Tuning",
        "nav_drivers": "Driver Booster",
        "nav_drivers_sub": "GPU, Wi-Fi, Firmware & Kernel",
        "nav_uninstaller": "Deep Uninstaller",
        "nav_uninstaller_sub": "Revo-Style App & Leftover Wipe",
        "nav_control": "PC Control Center",
        "nav_control_sub": "Monitor, Tasks, Startup & Disk",
        "nav_security": "Security & Privacy",
        "nav_security_sub": "UFW Firewall & Privacy Sweep",

        # Page 1: Smart SystemCare
        "care_headline": "AI Smart SystemCare",
        "care_desc": "Deep-scan junk caches, orphaned packages, old Snap/Flatpak runtimes, logs, and broken traces in one click.",
        "care_score_label": "HEALTH SCORE",
        "care_scan_now": "SCAN NOW",
        "care_scanning": "SCANNING...",
        "care_fix_now": "CLEAN & FIX NOW",
        "care_fixing": "CLEANING...",
        "care_reclaimable": "Reclaimable Space: {size}",
        "care_items_found": "{count} issues / junk groups detected",
        "care_all_clean": "Your Zorin OS system is clean and optimized!",
        "care_select_all": "Select All",
        "care_deselect_all": "Deselect All",
        "care_cleaned_toast": "Cleaned {size} across {count} categories!",
        "cat_apt_cache": "APT Package Cache",
        "cat_apt_cache_desc": "Downloaded .deb archives stored in /var/cache/apt/archives",
        "cat_apt_orphans": "Unused APT Dependencies",
        "cat_apt_orphans_desc": "Orphaned libraries no longer needed by any installed package",
        "cat_dpkg_rc": "Residual Package Configs (rc)",
        "cat_dpkg_rc_desc": "Leftover configuration records from previously removed .deb packages",
        "cat_flatpak_unused": "Unused Flatpak Runtimes",
        "cat_flatpak_unused_desc": "Orphaned Flatpak runtimes and temporary ostree caches",
        "cat_snap_disabled": "Old Disabled Snap Revisions",
        "cat_snap_disabled_desc": "Superseded Snap package revisions consuming disk space",
        "cat_journal_logs": "Systemd Journal Logs (>50 MB)",
        "cat_journal_logs_desc": "Old system diagnostic logs in /var/log/journal",
        "cat_rotated_logs": "Rotated & Compressed Logs",
        "cat_rotated_logs_desc": "Archived .gz and .old log files inside /var/log",
        "cat_thumbnails": "User Thumbnail Cache",
        "cat_thumbnails_desc": "Cached image/video previews in ~/.cache/thumbnails",
        "cat_user_cache": "Safe App & Shader Caches",
        "cat_user_cache_desc": "Pip, npm, Mesa shader, fontconfig, and build caches in ~/.cache",
        "cat_crash_dumps": "Crash Reports & Core Dumps",
        "cat_crash_dumps_desc": "Diagnostic crash dumps in /var/crash and systemd coredump",
        "cat_trash": "Recycle Bin / Trash",
        "cat_trash_desc": "Deleted files sitting in ~/.local/share/Trash",
        "cat_broken_links": "Broken Symbolic Links",
        "cat_broken_links_desc": "Dead shortcuts and dangling symlinks in your home folders",

        # Page 2: Turbo Boost
        "boost_headline": "Turbo Boost & Kernel Optimizer",
        "boost_desc": "Free cached RAM instantly, engage Gaming or Work Pro Mode, and apply safe Zorin OS 18.1 kernel performance tweaks.",
        "boost_ram_title": "Instant RAM Memory Booster",
        "boost_ram_sub": "Flush clean pagecache, dentries, and inodes safely without touching running apps.",
        "boost_ram_btn": "Free Up RAM Now",
        "boost_ram_freed": "RAM Boost complete — freed {size} of cached memory!",
        "boost_mode_title": "1-Click Turbo Boost Mode",
        "boost_mode_normal": "Balanced (Default)",
        "boost_mode_work": "Work Pro Boost",
        "boost_mode_game": "Gaming Turbo Boost",
        "boost_mode_saver": "Max Battery Saver",
        "boost_activate": "Engage Boost",
        "boost_restore": "Restore Defaults",
        "boost_power_title": "Hardware Power Profile",
        "boost_sysctl_title": "Zorin Kernel 6.17 Performance Tweaks (sysctl)",
        "boost_sysctl_sub": "Persist safe desktop & gaming kernel optimizations to /etc/sysctl.d/99-zorincare-pro.conf",
        "boost_apply_sysctl": "Apply Selected Kernel Tweaks",
        "boost_reset_sysctl": "Reset Kernel Defaults",
        "tweak_swappiness": "Low Swappiness (vm.swappiness = 10)",
        "tweak_swappiness_desc": "Prioritize fast physical RAM over swap/disk for snappier multitasking",
        "tweak_vfs": "Responsive Filesystem Cache (vm.vfs_cache_pressure = 50)",
        "tweak_vfs_desc": "Keep directory/inode metadata cached for instant file browsing",
        "tweak_dirty": "Smooth Disk Writeback (vm.dirty_ratio = 15)",
        "tweak_dirty_desc": "Prevent UI stutters during large USB or NVMe file transfers",
        "tweak_bbr": "Google BBR TCP Congestion Control",
        "tweak_bbr_desc": "Boost download throughput and reduce network latency on Kernel 6.17",
        "tweak_mapcount": "Gaming & Wine Max Map Count (2,147,483,642)",
        "tweak_mapcount_desc": "Prevent crashes in Steam Proton, Lutris, and Zorin Windows App Support",

        # Page 3: Driver Booster
        "drv_headline": "Driver & Firmware Booster",
        "drv_desc": "Scan PCI/USB hardware, install recommended NVIDIA/Wi-Fi drivers, update UEFI/NVMe firmware via LVFS, and verify DKMS & microcode.",
        "drv_scan_btn": "Scan Hardware & Drivers",
        "drv_auto_install_btn": "Install Recommended Drivers",
        "drv_fw_update_btn": "Update All Firmware (LVFS)",
        "drv_prop_group": "Proprietary & Hardware Drivers (ubuntu-drivers)",
        "drv_no_prop": "No additional proprietary drivers required — open-source kernel drivers are optimal for your hardware!",
        "drv_fw_group": "UEFI BIOS & Device Firmware Updates (fwupd)",
        "drv_no_fw": "All LVFS-supported firmware devices are up to date.",
        "drv_stack_group": "Zorin OS 18.1 Kernel, Microcode & Graphics Stack",
        "drv_hw_group": "Detected PCI & USB Hardware Controllers",
        "drv_install_pkg": "Install",
        "drv_codecs_title": "Zorin Restricted Multimedia Codecs & Fonts",
        "drv_codecs_desc": "H.264/HEVC codecs, Microsoft Core Fonts, and hardware video acceleration",

        # Page 4: Deep Uninstaller (Revo Style)
        "uninst_headline": "Revo-Style Deep Uninstaller",
        "uninst_desc": "Completely remove APT, Flatpak, Snap, AppImage, and Wine apps — then hunt down and shred every leftover config, cache, and folder.",
        "uninst_search_ph": "Search installed apps (APT, Flatpak, Snap, AppImage, Wine)...",
        "uninst_filter_all": "All Sources",
        "uninst_scan_mode": "Leftover Scan Depth",
        "uninst_mode_safe": "Safe",
        "uninst_mode_moderate": "Moderate",
        "uninst_mode_advanced": "Advanced",
        "uninst_backup_toggle": "Safety Backup Before Delete",
        "uninst_btn_remove": "Deep Uninstall",
        "uninst_btn_leftovers_only": "Scan Leftovers",
        "uninst_orphan_btn": "Hunt Ghost Leftovers",
        "uninst_orphan_tip": "Find leftover folders in ~/.config, ~/.cache, ~/.var/app from ALREADY uninstalled apps",
        "uninst_backups_btn": "Backups ({count})",
        "uninst_protected": "Protected Core OS",
        "uninst_confirm_title": "Deep Uninstall {name}?",
        "uninst_confirm_body": "ZorinCare Pro will purge {name} ({source}) and then scan your system for leftover folders, caches, and launcher entries.",
        "uninst_leftover_title": "Leftover Files Found ({count} items — {size})",
        "uninst_delete_selected": "Shred Selected Leftovers",
        "uninst_no_leftovers": "Zero leftovers found — completely clean!",
        "uninst_removed_done": "Removed {count} leftover paths ({size} reclaimed).",

        # Page 5: PC Control Center
        "ctrl_headline": "Full PC Control Center",
        "ctrl_desc": "Real-time hardware telemetry, live process killer, startup & systemd service manager, network DNS, Zorin desktop tweaks, and disk analyzer.",
        "ctrl_tab_monitor": "Live Monitor",
        "ctrl_tab_processes": "Task Manager",
        "ctrl_tab_services": "Startup & Services",
        "ctrl_tab_tools": "System & Power Controls",
        "ctrl_tab_disk": "Disk Space Analyzer",
        "ctrl_cpu": "CPU Load",
        "ctrl_ram": "RAM Usage",
        "ctrl_swap": "Swap / ZRAM",
        "ctrl_temp": "Temperature",
        "ctrl_net": "Network I/O",
        "ctrl_disk_root": "Root Disk (/)",
        "ctrl_kill_btn": "End Process",
        "ctrl_force_kill_btn": "Force Kill",
        "ctrl_proc_search": "Filter processes by name or PID...",
        "ctrl_autostart_group": "Startup Applications (~/.config/autostart)",
        "ctrl_systemd_group": "Systemd Background Services",
        "ctrl_dns_group": "1-Click Fast & Secure DNS Switcher",
        "ctrl_dns_auto": "Automatic (ISP / Router DHCP)",
        "ctrl_dns_cf": "Cloudflare 1.1.1.1 (Fastest)",
        "ctrl_dns_google": "Google 8.8.8.8",
        "ctrl_dns_quad9": "Quad9 9.9.9.9 (Malware Blocking)",
        "ctrl_flush_dns": "Flush DNS Cache",
        "ctrl_power_group": "Power & Scheduled Shutdown Timer",
        "ctrl_shutdown_15": "Shutdown in 15m",
        "ctrl_shutdown_30": "Shutdown in 30m",
        "ctrl_shutdown_60": "Shutdown in 1h",
        "ctrl_shutdown_120": "Shutdown in 2h",
        "ctrl_shutdown_cancel": "Cancel Timer",
        "ctrl_zorin_group": "Zorin OS / GNOME 46 Desktop Quick Tweaks",
        "ctrl_tweak_battery_pct": "Show Battery Percentage in Top Bar",
        "ctrl_tweak_night_light": "Night Light Eye Protection",
        "ctrl_tweak_animations": "Desktop Window Animations",
        "ctrl_tweak_center_win": "Center Newly Opened Windows",
        "ctrl_tweak_tap_click": "Touchpad Tap-to-Click",
        "ctrl_disk_scan_btn": "Scan Home Directory Space Hogs",

        # Page 6: Security & Privacy
        "sec_headline": "Security & Privacy Shield",
        "sec_desc": "Manage UFW Firewall, audit open listening ports, fix SSH permissions, and sweep browser & activity tracking history.",
        "sec_ufw_group": "UFW System Firewall Protection",
        "sec_ufw_enable": "Enable Firewall",
        "sec_ufw_disable": "Disable Firewall",
        "sec_ports_group": "Active Listening Network Ports (TCP/UDP)",
        "sec_privacy_group": "Privacy & Activity Trace Cleaner",
        "sec_clean_privacy_btn": "Sweep Selected Privacy Traces",
        "sec_audit_group": "System Security Hardening Audit",
        "priv_recent": "Recent Files & Documents History (recently-used.xbel)",
        "priv_browsers": "Web Browser Caches (Brave, Firefox, Chrome, Chromium, Edge)",
        "priv_thumbnails": "Viewed Picture & Video Thumbnails",
        "priv_shell_hist": "Terminal Command History (.bash_history / .zsh_history)",
        "priv_clipboard": "Clear Current Clipboard Contents",
    },
    "ar": {
        # App & Header
        "app_title": "زورين كير برو — ZorinCare Pro",
        "app_subtitle": "الحزمة الشاملة لتحسين وتسريع وحماية نظام Zorin OS 18.1 Pro",
        "lang_switch_btn": "English",
        "theme_cyber": "سايبر نيون",
        "theme_native": "زورين الأصلي",
        "theme_toggle_tip": "تبديل مظهر الواجهة (الوضع الليلي النيون / زورين الأصلي)",
        "lang_toggle_tip": "تبديل اللغة (العربية / English)",
        "log_drawer_btn": "سجل العمليات",
        "status_ready": "جاهز — النظام محمي ويعمل بكفاءة",
        "status_working": "جارٍ التنفيذ...",
        "refresh": "تحديث",
        "apply": "تطبيق",
        "cancel": "إلغاء",
        "close": "إغلاق",
        "yes": "نعم",
        "no": "لا",
        "enabled": "مفعّل",
        "disabled": "معطّل",
        "active": "نشط",
        "inactive": "متوقف",
        "installed": "مثبّت",
        "not_installed": "غير مثبّت",
        "recommended": "موصى به",

        # Sidebar Navigation
        "nav_care": "العناية الذكية",
        "nav_care_sub": "فحص وتنظيف شامل بنقرة واحدة",
        "nav_booster": "التسريع الفائق",
        "nav_booster_sub": "تحرير الرام وتسريع النواة والطاقة",
        "nav_drivers": "محدّث التعريفات",
        "nav_drivers_sub": "كرت الشاشة والواي فاي والعتاد",
        "nav_uninstaller": "الحذف الجذري",
        "nav_uninstaller_sub": "إزالة البرامج وبقاياها بأسلوب Revo",
        "nav_control": "مركز التحكم الكامل",
        "nav_control_sub": "مراقبة، مهام، بدء التشغيل والقرص",
        "nav_security": "الأمان والخصوصية",
        "nav_security_sub": "جدار الحماية ومسح آثار التصفح",

        # Page 1: Smart SystemCare
        "care_headline": "العناية الذكية الشاملة بالنظام",
        "care_desc": "افحص ملفات النظام المؤقتة، الحزم اليتيمة، بقايا Flatpak وSnap، السجلات القديمة والروابط التالفة ونظّفها بنقرة واحدة.",
        "care_score_label": "صحة النظام",
        "care_scan_now": "افحص الآن",
        "care_scanning": "جارٍ الفحص...",
        "care_fix_now": "تنظيف وإصلاح الكل",
        "care_fixing": "جارٍ التنظيف...",
        "care_reclaimable": "المساحة القابلة للاسترجاع: {size}",
        "care_items_found": "تم اكتشاف {count} فئات تحتاج إلى تنظيف",
        "care_all_clean": "نظام Zorin OS نظيف ومحسّن بالكامل!",
        "care_select_all": "تحديد الكل",
        "care_deselect_all": "إلغاء التحديد",
        "care_cleaned_toast": "تم تحرير {size} بنجاح عبر {count} فئات!",
        "cat_apt_cache": "ذاكرة تخزين حزم APT",
        "cat_apt_cache_desc": "ملفات التثبيت المؤقتة .deb المحفوظة في /var/cache/apt/archives",
        "cat_apt_orphans": "الحزم والمكتبات اليتيمة",
        "cat_apt_orphans_desc": "مكتبات لم يعد أي برنامج مثبّت بحاجة إليها",
        "cat_dpkg_rc": "بقايا إعدادات الحزم المحذوفة (rc)",
        "cat_dpkg_rc_desc": "ملفات إعداد متبقية من حزم .deb تم حذفها سابقاً",
        "cat_flatpak_unused": "بيئات تشغيل Flatpak غير المستخدمة",
        "cat_flatpak_unused_desc": "ملفات تشغيل Flatpak اليتيمة والملفات المؤقتة",
        "cat_snap_disabled": "إصدارات Snap القديمة المعطّلة",
        "cat_snap_disabled_desc": "نسخ قديمة من تطبيقات Snap تستهلك مساحة القرص دون فائدة",
        "cat_journal_logs": "سجلات النظام الطويلة (Journal > 50MB)",
        "cat_journal_logs_desc": "سجلات تشخيص النظام القديمة في /var/log/journal",
        "cat_rotated_logs": "السجلات المضغوطة والقديمة",
        "cat_rotated_logs_desc": "ملفات السجلات المؤرشفة .gz و.old داخل /var/log",
        "cat_thumbnails": "ذاكرة الصور المصغّرة (Thumbnails)",
        "cat_thumbnails_desc": "معاينات الصور والفيديو المخزّنة في ~/.cache/thumbnails",
        "cat_user_cache": "الملفات المؤقتة للتطبيقات والمظلّلات",
        "cat_user_cache_desc": "ملفات التخزين المؤقت الآمنة لـ pip وnpm وMesa في ~/.cache",
        "cat_crash_dumps": "تقارير الأعطال (Crash Dumps)",
        "cat_crash_dumps_desc": "ملفات انهيار البرامج في /var/crash وsystemd coredump",
        "cat_trash": "سلة المهملات",
        "cat_trash_desc": "الملفات المحذوفة الموجودة في سلة المهملات",
        "cat_broken_links": "الاختصارات والروابط التالفة",
        "cat_broken_links_desc": "الروابط الرمزية المعطّلة داخل مجلد المستخدم",

        # Page 2: Turbo Boost
        "boost_headline": "التسريع الفائق وضبط النواة (Turbo Boost)",
        "boost_desc": "حرّر ذاكرة الرام فوراً، فعّل وضع الألعاب أو العمل الاحترافي، وطبّق تحسينات نواة لينكس 6.17 بأمان.",
        "boost_ram_title": "محرّر ذاكرة الرام الفوري",
        "boost_ram_sub": "تفريغ الذاكرة المخبأة (PageCache & Inodes) بأمان دون إغلاق برامجك المفتوحة.",
        "boost_ram_btn": "تحرير الرام الآن",
        "boost_ram_freed": "اكتمل تسريع الرام — تم تحرير {size} من الذاكرة المخبأة!",
        "boost_mode_title": "أوضاع التسريع الفائق بنقرة واحدة",
        "boost_mode_normal": "متوازن (افتراضي)",
        "boost_mode_work": "وضع العمل الاحترافي",
        "boost_mode_game": "وضع تسريع الألعاب القصوى",
        "boost_mode_saver": "توفير البطارية الأقصى",
        "boost_activate": "تفعيل الوضع",
        "boost_restore": "استعادة الافتراضي",
        "boost_power_title": "ملف طاقة المعالج والعتاد",
        "boost_sysctl_title": "تحسينات نواة Zorin Kernel 6.17 (sysctl)",
        "boost_sysctl_sub": "حفظ تحسينات الأداء والألعاب والشبكة في /etc/sysctl.d/99-zorincare-pro.conf",
        "boost_apply_sysctl": "تطبيق تحسينات النواة المحددة",
        "boost_reset_sysctl": "إعادة ضبط النواة للافتراضي",
        "tweak_swappiness": "تقليل استخدام Swap (vm.swappiness = 10)",
        "tweak_swappiness_desc": "الاعتماد على ذاكرة RAM السريعة بدلاً من القرص لتنقل أسرع بين البرامج",
        "tweak_vfs": "تسريع تصفح الملفات (vm.vfs_cache_pressure = 50)",
        "tweak_vfs_desc": "الاحتفاظ بفهارس المجلدات في الذاكرة لفتح الملفات فوراً",
        "tweak_dirty": "سلاسة نقل الملفات الكبيرة (vm.dirty_ratio = 15)",
        "tweak_dirty_desc": "منع تجمّد الواجهة أثناء نسخ ملفات كبيرة إلى الفلاشة أو القرص",
        "tweak_bbr": "خوارزمية Google BBR لتسريع الإنترنت",
        "tweak_bbr_desc": "زيادة سرعة التحميل وتقليل زمن الاستجابة (Ping) على نواة 6.17",
        "tweak_mapcount": "دعم الألعاب وWine/Proton الأقصى (vm.max_map_count)",
        "tweak_mapcount_desc": "منع انهيار ألعاب Steam Proton وبرامج ويندوز على Zorin Pro",

        # Page 3: Driver Booster
        "drv_headline": "محدّث التعريفات والعتاد (Driver Booster)",
        "drv_desc": "افحص قطع الجهاز، ثبّت تعريفات NVIDIA والواي فاي الموصى بها، حدّث البايوس والـ Firmware عبر LVFS، وتحقّق من النواة.",
        "drv_scan_btn": "فحص العتاد والتعريفات",
        "drv_auto_install_btn": "تثبيت التعريفات الموصى بها تلقائياً",
        "drv_fw_update_btn": "تحديث جميع البرامج الثابتة (Firmware)",
        "drv_prop_group": "تعريفات كرت الشاشة والشبكة (ubuntu-drivers)",
        "drv_no_prop": "لا توجد تعريفات خارجية مطلوبة — تعريفات النواة المدمجة تعمل بأفضل أداء لجهازك!",
        "drv_fw_group": "تحديثات البايوس UEFI والعتاد (fwupd / LVFS)",
        "drv_no_fw": "جميع البرامج الثابتة (Firmware) لقطع جهازك محدّثة لآخر إصدار.",
        "drv_stack_group": "حالة النواة والمعالج (Microcode) والرسوميات",
        "drv_hw_group": "خريطة قطع العتاد المتصلة (PCI & USB)",
        "drv_install_pkg": "تثبيت",
        "drv_codecs_title": "حزمة ترميزات الوسائط والخطوط الشاملة (Restricted Extras)",
        "drv_codecs_desc": "تشغيل جميع صيغ الفيديو والصوت وخطوط مايكروسوفت وتسريع الفيديو العتادي",

        # Page 4: Deep Uninstaller (Revo Style)
        "uninst_headline": "الحذف الجذري للبرامج (بأسلوب Revo Uninstaller)",
        "uninst_desc": "احذف برامج APT وFlatpak وSnap وAppImage وWine بالكامل — ثم اصطد وامسح كل الملفات والمجلدات والإعدادات المتبقية.",
        "uninst_search_ph": "ابحث عن برنامج مثبّت (APT, Flatpak, Snap, AppImage, Wine)...",
        "uninst_filter_all": "جميع المصادر",
        "uninst_scan_mode": "عمق فحص البقايا",
        "uninst_mode_safe": "آمن",
        "uninst_mode_moderate": "متوسط",
        "uninst_mode_advanced": "متقدم عميق",
        "uninst_backup_toggle": "نسخة احتياطية قبل الحذف",
        "uninst_btn_remove": "حذف جذري",
        "uninst_btn_leftovers_only": "فحص البقايا",
        "uninst_orphan_btn": "صائد البقايا اليتيمة",
        "uninst_orphan_tip": "اكتشف مجلدات البقايا في ~/.config و~/.cache و~/.var/app لبرامج حذفتها سابقاً!",
        "uninst_backups_btn": "النسخ الاحتياطية ({count})",
        "uninst_protected": "حزمة نظام محمية",
        "uninst_confirm_title": "حذف جذري للبرنامج {name}؟",
        "uninst_confirm_body": "سيقوم ZorinCare Pro بإزالة {name} ({source}) بالكامل ثم فحص جميع المجلدات المخفية لحذف بقاياه.",
        "uninst_leftover_title": "تم العثور على بقايا ({count} عنصر — {size})",
        "uninst_delete_selected": "حذف البقايا المحددة نهائياً",
        "uninst_no_leftovers": "لا توجد أي ملفات متبقية — نظيف تماماً!",
        "uninst_removed_done": "تم حذف {count} من البقايا واسترجاع {size}.",

        # Page 5: PC Control Center
        "ctrl_headline": "مركز التحكم الكامل بالحاسوب",
        "ctrl_desc": "مراقبة فورية للحرارة والمعالج والرام، إدارة العمليات، التحكم ببرامج بدء التشغيل والخدمات، DNS، ومحلل مساحة القرص.",
        "ctrl_tab_monitor": "المراقب الحي",
        "ctrl_tab_processes": "إدارة المهام",
        "ctrl_tab_services": "بدء التشغيل والخدمات",
        "ctrl_tab_tools": "أدوات النظام والطاقة",
        "ctrl_tab_disk": "محلل مساحة القرص",
        "ctrl_cpu": "استهلاك المعالج",
        "ctrl_ram": "استهلاك الرام",
        "ctrl_swap": "ذاكرة التبديل Swap",
        "ctrl_temp": "درجة الحرارة",
        "ctrl_net": "سرعة الشبكة",
        "ctrl_disk_root": "قرص النظام (/)",
        "ctrl_kill_btn": "إنهاء المهمة",
        "ctrl_force_kill_btn": "إنهاء إجباري",
        "ctrl_proc_search": "ابحث باسم العملية أو رقم PID...",
        "ctrl_autostart_group": "برامج بدء التشغيل التلقائي (~/.config/autostart)",
        "ctrl_systemd_group": "خدمات النظام الخلفية (Systemd Services)",
        "ctrl_dns_group": "مبدّل DNS السريع والآمن بنقرة واحدة",
        "ctrl_dns_auto": "تلقائي (إعدادات الراوتر DHCP)",
        "ctrl_dns_cf": "Cloudflare 1.1.1.1 (الأسرع)",
        "ctrl_dns_google": "Google 8.8.8.8",
        "ctrl_dns_quad9": "Quad9 9.9.9.9 (حظر البرمجيات الخبيثة)",
        "ctrl_flush_dns": "تفريغ ذاكرة DNS",
        "ctrl_power_group": "مؤقت إيقاف التشغيل والطاقة",
        "ctrl_shutdown_15": "إيقاف بعد 15 د",
        "ctrl_shutdown_30": "إيقاف بعد 30 د",
        "ctrl_shutdown_60": "إيقاف بعد ساعة",
        "ctrl_shutdown_120": "إيقاف بعد ساعتين",
        "ctrl_shutdown_cancel": "إلغاء المؤقت",
        "ctrl_zorin_group": "تخصيصات سطح مكتب Zorin OS / GNOME 46 السريعة",
        "ctrl_tweak_battery_pct": "إظهار نسبة البطارية في الشريط العلوي",
        "ctrl_tweak_night_light": "الإضاءة الليلية لحماية العين",
        "ctrl_tweak_animations": "تأثيرات حركة النوافذ",
        "ctrl_tweak_center_win": "توسيط النوافذ الجديدة تلقائياً",
        "ctrl_tweak_tap_click": "النقر باللمس على لوحة اللمس (Touchpad)",
        "ctrl_disk_scan_btn": "فحص أكبر المجلدات والملفات حجماً",

        # Page 6: Security & Privacy
        "sec_headline": "درع الأمان والخصوصية",
        "sec_desc": "تحكم بجدار الحماية UFW، راقب المنافذ المفتوحة، تحقّق من صلاحيات SSH، وامسح آثار التصفح والملفات الأخيرة.",
        "sec_ufw_group": "جدار الحماية الناري (UFW Firewall)",
        "sec_ufw_enable": "تفعيل جدار الحماية",
        "sec_ufw_disable": "تعطيل جدار الحماية",
        "sec_ports_group": "منافذ الشبكة المفتوحة حالياً (TCP/UDP)",
        "sec_privacy_group": "ماسح آثار الخصوصية والتصفح",
        "sec_clean_privacy_btn": "مسح آثار الخصوصية المحددة",
        "sec_audit_group": "فحص أمان وصلاحيات النظام",
        "priv_recent": "سجل الملفات والمستندات المفتوحة مؤخراً",
        "priv_browsers": "ذاكرة المتصفحات المؤقتة (Brave, Firefox, Chrome, Edge)",
        "priv_thumbnails": "معاينات الصور والفيديوهات المستعرضة",
        "priv_shell_hist": "سجل أوامر الطرفية (.bash_history / .zsh_history)",
        "priv_clipboard": "تفريغ محتويات الحافظة الحالية (Clipboard)",
    },
}


class SettingsManager:
    """Loads/saves user preferences and handles EN/AR translations."""

    def __init__(self) -> None:
        self._path = get_config_dir() / SETTINGS_FILE
        self._data: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        if self._path.exists():
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data.update(loaded)
            except Exception:
                pass

    def save(self) -> None:
        try:
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, DEFAULT_SETTINGS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    @property
    def lang(self) -> str:
        val = self._data.get("language", "en")
        return val if val in ("en", "ar") else "en"

    @lang.setter
    def lang(self, value: str) -> None:
        self.set("language", "ar" if value == "ar" else "en")

    def toggle_lang(self) -> str:
        self.lang = "ar" if self.lang == "en" else "en"
        return self.lang

    @property
    def is_rtl(self) -> bool:
        return self.lang == "ar"


SETTINGS = SettingsManager()


def t(key: str, **kwargs: Any) -> str:
    """Translate key into active language ('en' or 'ar') with optional format args."""
    lang_map = TRANSLATIONS.get(SETTINGS.lang, TRANSLATIONS["en"])
    template = lang_map.get(key) or TRANSLATIONS["en"].get(key) or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template


def format_bytes(num_bytes: int | float) -> str:
    """Format byte count into human-readable KB/MB/GB."""
    val = float(max(0, num_bytes))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if val < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(val)} B"
            return f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} TB"
