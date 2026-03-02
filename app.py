# -*- coding: utf-8 -*-
# 导入所需的库
import os
import json
import time
import yaml
import requests
import re
import threading
import asyncio
import shutil
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, unquote
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any
import uuid
from functools import reduce
import operator
import traceback
import xml.etree.ElementTree as ET

# 全局变量和缓存
POSTER_CACHE = {}  # 用于缓存海报URL，键为TMDB ID，值为包含URL和时间戳的字典
CACHE_DIR = '/config/cache'  # 缓存目录
POSTER_CACHE_PATH = os.path.join(CACHE_DIR, 'poster_cache.json')  # 海报缓存文件路径
CONFIG_PATH = '/config/config.yaml'  # 配置文件路径
CONFIG = {}  # 全局配置字典
DEFAULT_SETTINGS = {}  # 默认设置字典
TOGGLE_INDEX_TO_KEY = {}  # 设置菜单索引到键的映射
TOGGLE_KEY_TO_INFO = {}  # 设置菜单键到信息的映射
LANG_MAP = {}  # 语言代码到语言名称的映射
LANG_MAP_PATH = os.path.join(CACHE_DIR, 'languages.json')  # 语言文件路径
ADMIN_CACHE = {}  # 管理员权限缓存
GROUP_MEMBER_CACHE = {}  # 群组成员权限缓存
SEARCH_RESULTS_CACHE = {}  # 搜索结果缓存
DELETION_TASK_CACHE: Dict[str, Any] = {}  # 删除任务缓存
recent_playback_notifications = {}  # 最近播放通知的去重缓存
user_context = {}  # 用户会话上下文（例如，等待用户回复）
user_search_state = {}  # 用户搜索状态缓存
UPDATE_PATH_CACHE = {}  # 用于在回调中传递更新路径的缓存
EMBY_USERS_CACHE = {}   # 用于缓存Emby用户列

# 设置菜单结构定义
SETTINGS_MENU_STRUCTURE = {
    'root': {'label': '⚙️ 主菜单', 'children': ['content_settings', 'notification_management', 'auto_delete_settings', 'system_settings']},
    'content_settings': {'label': '推送内容设置', 'parent': 'root', 'children': ['status_feedback', 'playback_action', 'library_deleted_content', 'new_library_content_settings', 'search_display']},
    'new_library_content_settings': {'label': '新增节目通知内容设置', 'parent': 'content_settings', 'children': ['new_library_show_poster', 'new_library_show_media_detail', 'new_library_media_detail_has_tmdb_link', 'new_library_show_overview', 'new_library_show_media_type', 'new_library_show_video_spec', 'new_library_show_audio_spec', 'new_library_show_subtitle_spec', 'new_library_show_progress_status', 'new_library_show_timestamp', 'new_library_show_view_on_server_button']},
    'new_library_show_progress_status': {'label': '展示更新进度/缺集', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_progress_status', 'default': True},
    'new_library_show_poster': {'label': '展示海报', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_poster', 'default': True},
    'new_library_show_media_detail': {'label': '展示节目详情', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_media_detail', 'default': True},
    'new_library_media_detail_has_tmdb_link': {'label': '节目详情添加TMDB链接', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.media_detail_has_tmdb_link', 'default': True},
    'new_library_show_overview': {'label': '展示剧情', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_overview', 'default': True},
    'new_library_show_media_type': {'label': '展示节目类型', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_media_type', 'default': True},
    'new_library_show_video_spec': {'label': '展示视频规格', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_video_spec', 'default': False},
    'new_library_show_audio_spec': {'label': '展示音频规格', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_audio_spec', 'default': False},
    'new_library_show_subtitle_spec': {'label': '展示字幕规格', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_subtitle_spec', 'default': False},
    'new_library_show_timestamp': {'label': '展示更新时间', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_timestamp', 'default': True},
    'new_library_show_view_on_server_button': {'label': '展示“在服务器中查看按钮”', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_view_on_server_button', 'default': True},
    'status_feedback': {'label': '观看状态反馈内容设置', 'parent': 'content_settings', 'children': ['status_show_poster', 'status_show_player', 'status_show_device', 'status_show_location', 'status_show_media_detail', 'status_media_detail_has_tmdb_link', 'status_show_media_type', 'status_show_overview', 'status_show_timestamp', 'status_show_view_on_server_button', 'status_show_terminate_session_button', 'status_show_send_message_button', 'status_show_broadcast_button', 'status_show_terminate_all_button']},
    'status_show_poster': {'label': '展示海报', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_poster', 'default': True},
    'status_show_player': {'label': '展示播放器', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_player', 'default': True},
    'status_show_device': {'label': '展示设备', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_device', 'default': True},
    'status_show_location': {'label': '展示位置信息', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_location', 'default': True},
    'status_show_media_detail': {'label': '展示节目详情', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_media_detail', 'default': True},
    'status_media_detail_has_tmdb_link': {'label': '节目详情添加TMDB链接', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.media_detail_has_tmdb_link', 'default': True},
    'status_show_media_type': {'label': '展示节目类型', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_media_type', 'default': True},
    'status_show_overview': {'label': '展示剧情', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_overview', 'default': False},
    'status_show_timestamp': {'label': '展示时间', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_timestamp', 'default': True},
    'status_show_view_on_server_button': {'label': '展示“在服务器中查看按钮”', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_view_on_server_button', 'default': True},
    'status_show_terminate_session_button': {'label': '展示“停止播放”按钮', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_terminate_session_button', 'default': True},
    'status_show_send_message_button': {'label': '展示“发送消息”按钮', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_send_message_button', 'default': True},
    'status_show_broadcast_button': {'label': '展示“群发消息”按钮', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_broadcast_button', 'default': True},
    'status_show_terminate_all_button': {'label': '展示“停止所有”按钮', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_terminate_all_button', 'default': True},
    'playback_action': {'label': '播放行为推送内容设置', 'parent': 'content_settings', 'children': ['playback_show_poster', 'playback_show_media_detail', 'playback_media_detail_has_tmdb_link', 'playback_show_user', 'playback_show_player', 'playback_show_device', 'playback_show_location', 'playback_show_progress', 'playback_show_video_spec', 'playback_show_audio_spec', 'playback_show_subtitle_spec', 'playback_show_media_type', 'playback_show_overview', 'playback_show_timestamp', 'playback_show_view_on_server_button']},
    'playback_show_poster': {'label': '展示海报', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_poster', 'default': True},
    'playback_show_media_detail': {'label': '展示节目详情', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_media_detail', 'default': True},
    'playback_media_detail_has_tmdb_link': {'label': '节目详情添加TMDB链接', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.media_detail_has_tmdb_link', 'default': True},
    'playback_show_user': {'label': '展示用户名', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_user', 'default': True},
    'playback_show_player': {'label': '展示播放器', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_player', 'default': True},
    'playback_show_device': {'label': '展示设备', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_device', 'default': True},
    'playback_show_location': {'label': '展示位置信息', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_location', 'default': True},
    'playback_show_progress': {'label': '展示播放进度', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_progress', 'default': True},
    'playback_show_video_spec': {'label': '展示视频规格', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_video_spec', 'default': False},
    'playback_show_audio_spec': {'label': '展示音频规格', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_audio_spec', 'default': False},
    'playback_show_subtitle_spec': {'label': '展示字幕规格', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_subtitle_spec', 'default': False},
    'playback_show_media_type': {'label': '展示节目类型', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_media_type', 'default': True},
    'playback_show_overview': {'label': '展示剧情', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_overview', 'default': True},
    'playback_show_timestamp': {'label': '展示时间', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_timestamp', 'default': True},
    'playback_show_view_on_server_button': {'label': '展示“在服务器中查看按钮”', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_view_on_server_button', 'default': True},
    'library_deleted_content': {'label': '删除节目通知内容设置', 'parent': 'content_settings', 'children': ['deleted_show_poster', 'deleted_show_media_detail', 'deleted_media_detail_has_tmdb_link', 'deleted_show_overview', 'deleted_show_media_type', 'deleted_show_timestamp']},
    'deleted_show_poster': {'label': '展示海报', 'parent': 'library_deleted_content', 'config_path': 'settings.content_settings.library_deleted_notification.show_poster', 'default': True},
    'deleted_show_media_detail': {'label': '展示节目详情', 'parent': 'library_deleted_content', 'config_path': 'settings.content_settings.library_deleted_notification.show_media_detail', 'default': True},
    'deleted_media_detail_has_tmdb_link': {'label': '节目详情添加TMDB链接', 'parent': 'library_deleted_content', 'config_path': 'settings.content_settings.library_deleted_notification.media_detail_has_tmdb_link', 'default': True},
    'deleted_show_overview': {'label': '展示剧情', 'parent': 'library_deleted_content', 'config_path': 'settings.content_settings.library_deleted_notification.show_overview', 'default': True},
    'deleted_show_media_type': {'label': '展示节目类型', 'parent': 'library_deleted_content', 'config_path': 'settings.content_settings.library_deleted_notification.show_media_type', 'default': True},
    'deleted_show_timestamp': {'label': '展示删除时间', 'parent': 'library_deleted_content', 'config_path': 'settings.content_settings.library_deleted_notification.show_timestamp', 'default': True},
    'search_display': {'label': '搜索结果展示内容设置', 'parent': 'content_settings', 'children': ['search_show_media_type_in_list', 'search_movie', 'search_series']},
    'search_show_media_type_in_list': {'label': '搜索结果列表展示节目分类', 'parent': 'search_display', 'config_path': 'settings.content_settings.search_display.show_media_type_in_list', 'default': True},
    'search_movie': {'label': '电影展示设置', 'parent': 'search_display', 'children': ['movie_show_poster', 'movie_title_has_tmdb_link', 'movie_show_type', 'movie_show_category', 'movie_show_overview', 'movie_show_video_spec', 'movie_show_audio_spec', 'movie_show_subtitle_spec', 'movie_show_added_time', 'movie_show_view_on_server_button']},
    'search_series': {'label': '剧集展示设置', 'parent': 'search_display', 'children': ['series_show_poster', 'series_title_has_tmdb_link', 'series_show_type', 'series_show_category', 'series_show_overview', 'series_season_specs', 'series_update_progress', 'series_show_view_on_server_button']},
    'movie_show_poster': {'label': '展示海报', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_poster', 'default': True},
    'movie_title_has_tmdb_link': {'label': '电影名称添加TMDB链接', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.title_has_tmdb_link', 'default': True},
    'movie_show_type': {'label': '展示类型', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_type', 'default': True},
    'movie_show_category': {'label': '展示分类', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_category', 'default': True},
    'movie_show_overview': {'label': '展示剧情', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_overview', 'default': True},
    'movie_show_video_spec': {'label': '展示视频规格', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_video_spec', 'default': True},
    'movie_show_audio_spec': {'label': '展示音频规格', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_audio_spec', 'default': True},
    'movie_show_subtitle_spec': {'label': '展示字幕规格', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_subtitle_spec', 'default': True},
    'movie_show_added_time': {'label': '展示入库时间', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_added_time', 'default': True},
    'movie_show_view_on_server_button': {'label': '展示“在服务器中查看按钮”', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_view_on_server_button', 'default': True},
    'series_show_poster': {'label': '展示海报', 'parent': 'search_series', 'config_path': 'settings.content_settings.search_display.series.show_poster', 'default': True},
    'series_title_has_tmdb_link': {'label': '剧目名称添加TMDB链接', 'parent': 'search_series', 'config_path': 'settings.content_settings.search_display.series.title_has_tmdb_link', 'default': True},
    'series_show_type': {'label': '展示类型', 'parent': 'search_series', 'config_path': 'settings.content_settings.search_display.series.show_type', 'default': True},
    'series_show_category': {'label': '展示分类', 'parent': 'search_series', 'config_path': 'settings.content_settings.search_display.series.show_category', 'default': True},
    'series_show_overview': {'label': '展示剧情', 'parent': 'search_series', 'config_path': 'settings.content_settings.search_display.series.show_overview', 'default': True},
    'series_show_view_on_server_button': {'label': '展示“在服务器中查看按钮”', 'parent': 'search_series', 'config_path': 'settings.content_settings.search_display.series.show_view_on_server_button', 'default': True},
    'series_season_specs': {'label': '各季规格', 'parent': 'search_series', 'children': ['series_season_show_video_spec', 'series_season_show_audio_spec', 'series_season_show_subtitle_spec']},
    'series_season_show_video_spec': {'label': '展示各季视频规格', 'parent': 'series_season_specs', 'config_path': 'settings.content_settings.search_display.series.season_specs.show_video_spec', 'default': True},
    'series_season_show_audio_spec': {'label': '展示各季音频规格', 'parent': 'series_season_specs', 'config_path': 'settings.content_settings.search_display.series.season_specs.show_audio_spec', 'default': True},
    'series_season_show_subtitle_spec': {'label': '展示各季字幕规格', 'parent': 'series_season_specs', 'config_path': 'settings.content_settings.search_display.series.season_specs.show_subtitle_spec', 'default': True},
    'series_update_progress': {'label': '更新进度', 'parent': 'search_series', 'children': ['series_progress_show_latest_episode', 'series_progress_latest_episode_has_tmdb_link', 'series_progress_show_overview', 'series_progress_show_added_time', 'series_progress_show_progress_status']},
    'series_progress_show_latest_episode': {'label': '展示已更新至', 'parent': 'series_update_progress', 'config_path': 'settings.content_settings.search_display.series.update_progress.show_latest_episode', 'default': True},
    'series_progress_latest_episode_has_tmdb_link': {'label': '已更新至添加TMDB链接', 'parent': 'series_update_progress', 'config_path': 'settings.content_settings.search_display.series.update_progress.latest_episode_has_tmdb_link', 'default': True},
    'series_progress_show_overview': {'label': '展示剧情', 'parent': 'series_update_progress', 'config_path': 'settings.content_settings.search_display.series.update_progress.show_overview', 'default': False},
    'series_progress_show_added_time': {'label': '展示入库时间', 'parent': 'series_update_progress', 'config_path': 'settings.content_settings.search_display.series.update_progress.show_added_time', 'default': True},
    'series_progress_show_progress_status': {'label': '展示更新进度', 'parent': 'series_update_progress', 'config_path': 'settings.content_settings.search_display.series.update_progress.show_progress_status', 'default': True},
    'notification_management': {'label': '通知消息管理', 'parent': 'root', 'children': ['notify_library_events', 'notify_playback_events', 'notification_management_advanced']},
    'notify_library_events': {'label': '新增/删除节目通知消息', 'parent': 'notification_management', 'children': ['notify_library_new', 'notify_library_deleted']},
    'notify_library_new': {'label': '新增节目通知消息', 'parent': 'notify_library_events', 'children': ['new_to_group', 'new_to_channel', 'new_to_private']},
    'notify_library_deleted': {'label': '删除节目通知消息', 'parent': 'notify_library_events', 'config_path': 'settings.notification_management.library_deleted', 'default': True},
    'notify_playback_events': {'label': '播放行为通知消息', 'parent': 'notification_management', 'children': ['notify_playback_start', 'notify_playback_pause', 'notify_playback_stop']},
    'notify_playback_start': {'label': '开始/继续播放通知消息', 'parent': 'notify_playback_events', 'config_path': 'settings.notification_management.playback_start', 'default': True},
    'notify_playback_pause': {'label': '暂停播放通知消息', 'parent': 'notify_playback_events', 'config_path': 'settings.notification_management.playback_pause', 'default': False},
    'notify_playback_stop': {'label': '停止播放通知消息', 'parent': 'notify_playback_events', 'config_path': 'settings.notification_management.playback_stop', 'default': True},
    'new_to_group': {'label': '发送到群组', 'parent': 'notify_library_new', 'config_path': 'settings.notification_management.library_new.to_group', 'default': True},
    'new_to_channel': {'label': '发送到频道', 'parent': 'notify_library_new', 'config_path': 'settings.notification_management.library_new.to_channel', 'default': True},
    'new_to_private': {'label': '发送给管理员', 'parent': 'notify_library_new', 'config_path': 'settings.notification_management.library_new.to_private', 'default': False},
    'notification_management_advanced': {'label': '高级通知管理', 'parent': 'notification_management', 'children': ['notify_user_login_success', 'notify_user_login_failure', 'notify_user_creation_deletion', 'notify_user_updates', 'notify_server_restart_required']},
    'notify_user_login_success': {'label': '用户登录成功', 'parent': 'notification_management_advanced', 'config_path': 'settings.notification_management.advanced.user_login_success', 'default': True},
    'notify_user_login_failure': {'label': '用户登录失败', 'parent': 'notification_management_advanced', 'config_path': 'settings.notification_management.advanced.user_login_failure', 'default': True},
    'notify_user_creation_deletion': {'label': '用户创建/删除', 'parent': 'notification_management_advanced', 'config_path': 'settings.notification_management.advanced.user_creation_deletion', 'default': True},
    'notify_user_updates': {'label': '用户策略/密码更新', 'parent': 'notification_management_advanced', 'config_path': 'settings.notification_management.advanced.user_updates', 'default': True},
    'notify_server_restart_required': {'label': '服务器需要重启', 'parent': 'notification_management_advanced', 'config_path': 'settings.notification_management.advanced.server_restart_required', 'default': True},
    'auto_delete_settings': {'label': '自动删除消息设置', 'parent': 'root', 'children': ['delete_library_events', 'delete_playback_status', 'delete_advanced_notifications']},    
    'delete_library_events': {'label': '新增/删除节目通知消息', 'parent': 'auto_delete_settings', 'children': ['delete_new_library', 'delete_library_deleted']},
    'delete_new_library': {'label': '新增节目通知消息', 'parent': 'delete_library_events', 'children': ['delete_new_library_group', 'delete_new_library_channel', 'delete_new_library_private']},
    'delete_library_deleted': {'label': '删除节目通知消息', 'parent': 'delete_library_events', 'config_path': 'settings.auto_delete_settings.library_deleted', 'default': True},
    'delete_new_library_group': {'label': '自动删除发送到群组的消息', 'parent': 'delete_new_library', 'config_path': 'settings.auto_delete_settings.new_library.to_group', 'default': False},
    'delete_new_library_channel': {'label': '自动删除发送到频道的消息', 'parent': 'delete_new_library', 'config_path': 'settings.auto_delete_settings.new_library.to_channel', 'default': False},
    'delete_new_library_private': {'label': '自动删除发送给管理员的消息', 'parent': 'delete_new_library', 'config_path': 'settings.auto_delete_settings.new_library.to_private', 'default': True},
    'delete_playback_status': {'label': '播放行为通知消息', 'parent': 'auto_delete_settings', 'children': ['delete_playback_start', 'delete_playback_pause', 'delete_playback_stop']},
    'delete_playback_start': {'label': '开始/继续播放通知消息', 'parent': 'delete_playback_status', 'config_path': 'settings.auto_delete_settings.playback_start', 'default': True},
    'delete_playback_pause': {'label': '暂停播放通知消息', 'parent': 'delete_playback_status', 'config_path': 'settings.auto_delete_settings.playback_pause', 'default': True},
    'delete_playback_stop': {'label': '停止播放通知消息', 'parent': 'delete_playback_status', 'config_path': 'settings.auto_delete_settings.playback_stop', 'default': True},
    'delete_advanced_notifications': {'label': '高级通知消息', 'parent': 'auto_delete_settings', 'children': ['delete_user_login', 'delete_user_management', 'delete_server_events']}, 
    'delete_user_login': {'label': '用户登录成功/失败', 'parent': 'delete_advanced_notifications', 'config_path': 'settings.auto_delete_settings.advanced.user_login', 'default': True}, 
    'delete_user_management': {'label': '用户创建/删除/更新', 'parent': 'delete_advanced_notifications', 'config_path': 'settings.auto_delete_settings.advanced.user_management', 'default': True},
    'delete_server_events': {'label': '服务器事件', 'parent': 'delete_advanced_notifications', 'config_path': 'settings.auto_delete_settings.advanced.server_events', 'default': True},
    'system_settings': {'label': '系统设置', 'parent': 'root', 'children': ['ip_api_selection']},
    'ip_api_selection': {'label': 'IP地理位置API设置', 'parent': 'system_settings', 'children': ['api_baidu', 'api_ip138', 'api_pconline', 'api_vore', 'api_ipapi']},
    'api_baidu': {'label': '百度 API', 'parent': 'ip_api_selection', 'config_value': 'baidu'},
    'api_ip138': {'label': 'IP138 API (需配置Token)', 'parent': 'ip_api_selection', 'config_value': 'ip138'},
    'api_pconline': {'label': '太平洋电脑 API', 'parent': 'ip_api_selection', 'config_value': 'pconline'},
    'api_vore': {'label': 'Vore API', 'parent': 'ip_api_selection', 'config_value': 'vore'},
    'api_ipapi': {'label': 'IP-API.com', 'parent': 'ip_api_selection', 'config_value': 'ipapi'}
}

def build_toggle_maps():
    """根据SETTINGS_MENU_STRUCTURE构建索引到配置键的映射和配置键到信息的映射。"""
    index = 0
    for key, node in SETTINGS_MENU_STRUCTURE.items():
        if 'config_path' in node:
            TOGGLE_INDEX_TO_KEY[index] = key
            TOGGLE_KEY_TO_INFO[key] = {
                'config_path': node['config_path'],
                'parent': node['parent']
            }
            SETTINGS_MENU_STRUCTURE[key]['index'] = index
            index += 1
    print("⚙️ 设置菜单键值映射已构建。")

def _build_default_settings():
    """根据SETTINGS_MENU_STRUCTURE构建默认设置字典。"""
    defaults = {}
    for node in SETTINGS_MENU_STRUCTURE.values():
        if 'config_path' in node:
            path = node['config_path']
            value = node['default']
            keys = path.split('.')
            d = defaults
            for k in keys[:-1]:
                d = d.setdefault(k, {})
            d[keys[-1]] = value
    return defaults

def get_setting(path_str):
    """根据点分隔的路径字符串从CONFIG或DEFAULT_SETTINGS中获取设置。"""
    try:
        return reduce(operator.getitem, path_str.split('.'), CONFIG)
    except (KeyError, TypeError):
        try:
            return reduce(operator.getitem, path_str.split('.'), DEFAULT_SETTINGS)
        except (KeyError, TypeError):
            print(f"⚠️ 警告: 在用户配置和默认配置中都找不到键: {path_str}")
            return None

def set_setting(path_str, value):
    """根据点分隔的路径字符串在CONFIG中设置一个值。"""
    keys = path_str.split('.')
    d = CONFIG
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value

def merge_configs(user_config, default_config):
    """递归合并用户配置和默认配置。"""
    if isinstance(user_config, dict) and isinstance(default_config, dict):
        merged = default_config.copy()
        for key, value in user_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = merge_configs(value, merged[key])
            else:
                merged[key] = value
        return merged
    return user_config

def load_config():
    """加载配置文件，如果不存在则使用默认设置。"""
    global CONFIG
    print(f"📝 尝试加载配置文件：{CONFIG_PATH}")
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            user_config = yaml.safe_load(f) or {}
        CONFIG = merge_configs(user_config, DEFAULT_SETTINGS)
        print("✅ 配置文件加载成功。")
    except FileNotFoundError:
        print(f"⚠️ 警告：配置文件 {CONFIG_PATH} 未找到。将使用内置的默认设置。")
        CONFIG = DEFAULT_SETTINGS
    except Exception as e:
        print(f"❌ 错误：读取或解析配置文件失败: {e}")
        exit(1)

def save_config():
    """保存当前配置到文件。"""
    print(f"💾 尝试保存配置文件：{CONFIG_PATH}")
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(CONFIG, f, allow_unicode=True, sort_keys=False)
        print("✅ 配置文件保存成功。")
    except Exception as e:
        print(f"❌ 保存配置失败: {e}")

def load_language_map():
    """加载语言映射文件，如果不存在则使用备用映射。"""
    global LANG_MAP
    fallback_map = {
        'eng': {'en': 'English', 'zh': '英语'}, 'jpn': {'en': 'Japanese', 'zh': '日语'},
        'chi': {'en': 'Chinese', 'zh': '中文'}, 'zho': {'en': 'Chinese', 'zh': '中文'},
        'kor': {'en': 'Korean', 'zh': '韩语'}, 'und': {'en': 'Undetermined', 'zh': '未知'},
        'mis': {'en': 'Multiple languages', 'zh': '多语言'}
    }
    print(f"🌍 尝试加载语言配置文件：{LANG_MAP_PATH}")
    if not os.path.exists(LANG_MAP_PATH):
        print(f"⚠️ 警告：语言配置文件 {LANG_MAP_PATH} 未找到，将使用内置的精简版语言列表。")
        LANG_MAP = fallback_map
        return
    try:
        with open(LANG_MAP_PATH, 'r', encoding='utf-8') as f:
            LANG_MAP = json.load(f)
        print("✅ 语言配置文件加载成功。")
    except Exception as e:
        print(f"❌ 加载语言配置文件失败: {e}，将使用内置的精简版语言列表。")
        LANG_MAP = fallback_map

def load_poster_cache():
    """加载海报缓存文件。"""
    global POSTER_CACHE
    print(f"🖼️ 尝试加载海报缓存：{POSTER_CACHE_PATH}")
    if not os.path.exists(POSTER_CACHE_PATH):
        POSTER_CACHE = {}
        print("⚠️ 海报缓存文件不存在，使用空缓存。")
        return
    try:
        with open(POSTER_CACHE_PATH, 'r', encoding='utf-8') as f:
            POSTER_CACHE = json.load(f)
        print("✅ 海报缓存加载成功。")
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"❌ 加载海报缓存失败: {e}，将使用空缓存。")
        POSTER_CACHE = {}

def save_poster_cache():
    """保存海报缓存到文件。"""
    print(f"💾 尝试保存海报缓存：{POSTER_CACHE_PATH}")
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(POSTER_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(POSTER_CACHE, f, indent=4)
        print("✅ 海报缓存保存成功。")
    except Exception as e:
        print(f"❌ 保存海报缓存失败: {e}")

# 初始化：构建默认设置、菜单映射，加载配置、语言和缓存
DEFAULT_SETTINGS = _build_default_settings()
build_toggle_maps()
load_config()
load_language_map()
load_poster_cache()

# 从配置中获取关键信息
TELEGRAM_TOKEN = CONFIG.get('telegram', {}).get('token')
ADMIN_USER_ID = CONFIG.get('telegram', {}).get('admin_user_id')
GROUP_ID = CONFIG.get('telegram', {}).get('group_id')
CHANNEL_ID = CONFIG.get('telegram', {}).get('channel_id')

TMDB_API_TOKEN = CONFIG.get('tmdb', {}).get('api_token')
HTTP_PROXY = CONFIG.get('proxy', {}).get('http_proxy')

TIMEZONE = ZoneInfo(get_setting('settings.timezone') or 'UTC')
PLAYBACK_DEBOUNCE_SECONDS = get_setting('settings.debounce_seconds') or 10
MEDIA_BASE_PATH = get_setting('settings.media_base_path')
MEDIA_CLOUD_PATH = get_setting('settings.media_cloud_path')
POSTER_CACHE_TTL_DAYS = get_setting('settings.poster_cache_ttl_days') or 30

EMBY_SERVER_URL = CONFIG.get('emby', {}).get('server_url')
EMBY_API_KEY = CONFIG.get('emby', {}).get('api_key')
EMBY_USER_ID = CONFIG.get('emby', {}).get('user_id')
EMBY_USERNAME = CONFIG.get('emby', {}).get('username')
EMBY_PASSWORD = CONFIG.get('emby', {}).get('password')
EMBY_REMOTE_URL = CONFIG.get('emby', {}).get('remote_url')
APP_SCHEME = CONFIG.get('emby', {}).get('app_scheme')
ALLOWED_GROUP_ID = GROUP_ID
EMBY_TEMPLATE_USER_ID = CONFIG.get('emby', {}).get('template_user_id')

# 检查必要配置
if not TELEGRAM_TOKEN or not ADMIN_USER_ID:
    print("❌ 错误：TELEGRAM_TOKEN 或 ADMIN_USER_ID 未在 config.yaml 中正确设置")
    exit(1)
if not EMBY_TEMPLATE_USER_ID:
    print("⚠️ 警告: 'template_user_id' 未在 config.yaml 中配置，用户创建功能将不可用。")
print("🚀 初始化完成。")

def make_request_with_retry(method, url, max_retries=3, retry_delay=1, **kwargs):
    """
    带重试机制的HTTP请求函数（改进版）：
    - 仅对 edit/delete/answerCallbackQuery 放行“无事可做”类错误
    - 不再吞掉 Telegram 的 button_data_invalid 错误
    - 对 Telegram 调用前本地校验 callback_data 长度（<= 64 字节）
    """
    import json as _json

    def _extract_payload_for_check(_kwargs):
        if 'json' in _kwargs and isinstance(_kwargs['json'], dict):
            return _kwargs['json']
        if 'data' in _kwargs and isinstance(_kwargs['data'], dict):
            return _kwargs['data']
        return None

    def _check_callback_data_len(_payload):
        try:
            if not _payload:
                return
            rm = _payload.get('reply_markup')
            if not rm:
                return
            if isinstance(rm, str):
                rm_obj = _json.loads(rm)
            elif isinstance(rm, dict):
                rm_obj = rm
            else:
                return
            kb = rm_obj.get('inline_keyboard') or []
            for row in kb:
                for btn in row:
                    cd = btn.get('callback_data')
                    if cd:
                        byte_len = len(cd.encode('utf-8'))
                        if byte_len > 64:
                            print(f"❌ Telegram 按钮 callback_data 超过 64 字节限制：{cd} （{byte_len} bytes）")
        except Exception as _e:
            print(f"⚠️ 本地检查 reply_markup 时发生异常：{_e}")

    api_name = "Unknown API"
    timeout = 15
    if "api.telegram.org" in url:
        api_name = "Telegram"
        timeout = 30
    elif "api.themoviedb.org" in url:
        api_name = "TMDB"
    elif "opendata.baidu.com" in url:
        api_name = "IP Geolocation"
        timeout = 5
    elif EMBY_SERVER_URL and EMBY_SERVER_URL in url:
        api_name = "Emby"

    timeout = kwargs.pop('timeout', timeout)

    attempts = 0
    while attempts < max_retries:
        try:
            if api_name == "Telegram":
                payload_for_check = _extract_payload_for_check(kwargs)
                _check_callback_data_len(payload_for_check)
            
            display_url = url.split('?')[0]
            if TELEGRAM_TOKEN and TELEGRAM_TOKEN in display_url:
                display_url = display_url.replace(TELEGRAM_TOKEN, "[REDACTED_TOKEN]")

            print(f"🌐 正在进行 {api_name} API 请求 (第 {attempts + 1} 次), URL: {display_url}, 超时: {timeout}s")
            response = requests.request(method, url, timeout=timeout, **kwargs)

            if 200 <= response.status_code < 300:
                print(f"✅ {api_name} API 请求成功，状态码: {response.status_code}")
                return response

            try:
                response.encoding = 'utf-8'
                error_text = response.text or ""
            except Exception:
                error_text = str(response)

            lowered = (error_text or "").lower()

            is_edit_or_delete = any(p in url for p in ("/editMessage", "/deleteMessage", "/answerCallbackQuery"))

            if api_name == "Telegram":
                harmless_errors = [
                    "message to delete not found",
                    "message can't be deleted",
                    "message to edit not found",
                    "message not found",
                    "message is not modified",
                    "query is too old and response timeout expired or query id is invalid",
                ]
                if is_edit_or_delete and any(h in lowered for h in harmless_errors):
                    print("ℹ️ Telegram 返回可忽略的编辑/删除类错误，已忽略。")
                    return None

                if response.status_code == 429:
                    try:
                        ra = int(response.headers.get('Retry-After', '1'))
                    except ValueError:
                        ra = 1
                    print(f"⏳ Telegram 限流 (429)，{ra}s 后重试。错误: {error_text}")
                    time.sleep(max(ra, retry_delay))
                    attempts += 1
                    continue

            if 500 <= response.status_code < 600:
                print(f"❌ {api_name} 服务端错误 {response.status_code}，将重试。错误: {error_text}")
            else:
                print(f"❌ {api_name} API 请求失败 (第 {attempts + 1} 次)，状态码: {response.status_code}, 响应: {error_text}")
                return None

        except requests.exceptions.RequestException as e:
            error_message = str(e)
            if TELEGRAM_TOKEN:
                error_message = error_message.replace(TELEGRAM_TOKEN, "[REDACTED_TOKEN]")
            print(f"❌ {api_name} API 请求发生网络错误 (第 {attempts + 1} 次)，URL: {display_url}, 错误: {error_message}")

        attempts += 1
        if attempts < max_retries:
            time.sleep(retry_delay)

    print(f"❌ {api_name} API 请求失败，已达到最大重试次数 ({max_retries} 次)，URL: {display_url}")
    return None

def _library_item_ready(item: dict) -> bool:
    """判定：是否已经刮削/解析到足够信息。MetaTube 刮不到也不致命，超时后照样发。"""
    if not isinstance(item, dict):
        return False

    # 1) 有简介（MetaTube 写入/本地 NFO/手工编辑都可能）
    overview = (item.get("Overview") or "").strip()
    if overview:
        return True

    # 2) 有媒体流（清晰度/编码/音轨等通常来自 Emby 媒体分析，稍后才会出现）
    streams = item.get("MediaStreams") or []
    if isinstance(streams, list) and len(streams) > 0:
        return True

    return False


def fetch_library_item_with_poll(item_id: str) -> dict:
    """按配置等待并轮询 Emby item，直到 ready 或超时。"""
    wait_first = int(get_setting("settings.library_new_wait_first_seconds") or 20)
    interval = int(get_setting("settings.library_new_poll_interval_seconds") or 15)
    max_polls = int(get_setting("settings.library_new_max_polls") or 8)

    # 复用你原来那条 full_item_url + params 的逻辑
    full_item_url = f"{EMBY_SERVER_URL}/Users/{EMBY_USER_ID}/Items/{item_id}"
    params = {
        "api_key": EMBY_API_KEY,
        "Fields": "ProviderIds,Path,Overview,ProductionYear,ServerId,DateCreated,SeriesProviderIds,ParentIndexNumber,SeriesId,MediaStreams"
    }

    if wait_first > 0:
        time.sleep(wait_first)

    last_item = None
    for i in range(max_polls):
        resp = make_request_with_retry("GET", full_item_url, params=params, timeout=10)
        if resp:
            last_item = resp.json()
            if _library_item_ready(last_item):
                print(f"✅ 条目已就绪（第 {i+1} 次轮询命中），将发送更完整通知。")
                return last_item

        print(f"⏳ 条目未就绪（第 {i+1}/{max_polls} 次），{interval}s 后重试…")
        time.sleep(interval)

    print("⚠️ 等待超时，仍未就绪：可能 MetaTube 刮不到或 Emby 分析较慢，将按现有信息发送。")
    return last_item or {}
    
def parse_episode_ranges_from_description(description: str):
    """
    从 Webhook 的 Description 中解析多集范围。
    返回 (summary_str, expanded_list)，例如：
    输入: "S01 E01, E03-E04"
    输出: ("S01E01, S01E03–E04", ["S01E01","S01E03","S01E04"])
    """
    if not description:
        return None, []
    first_line = description.strip().splitlines()[0]
    if not first_line:
        return None, []

    tokens = re.split(r'[，,]\s*|/\s*', first_line)
    
    season_ctx = None
    summary_parts, expanded = [], []

    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        m = re.match(r'(?:(?:S|s)\s*(\d{1,2}))?\s*E?\s*(\d{1,3})(?:\s*-\s*(?:(?:S|s)\s*(\d{1,2}))?\s*E?\s*(\d{1,3}))?$', tok)
        if not m:
            continue
        s1, e1, s2, e2 = m.groups()
        if s1:
            season_ctx = int(s1)
        season = season_ctx if season_ctx is not None else 1
        start_ep = int(e1)

        if e2:
            end_season = int(s2) if s2 else season
            end_ep = int(e2)
            if end_season != season:
                summary_parts.append(f"S{season:02d}E{start_ep:02d}–S{end_season:02d}E{end_ep:02d}")
            else:
                summary_parts.append(f"S{season:02d}E{start_ep:02d}–E{end_ep:02d}")
                for ep in range(start_ep, end_ep + 1):
                    expanded.append(f"S{season:02d}E{ep:02d}")
        else:
            summary_parts.append(f"S{season:02d}E{start_ep:02d}")
            expanded.append(f"S{season:02d}E{start_ep:02d}")

    summary = ", ".join(summary_parts) if summary_parts else None
    return summary, expanded


def escape_markdown(text: str) -> str:
    """转义MarkdownV2中的特殊字符。"""
    if not text:
        return ""
    text = str(text)
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def format_date(date_in):
    """
    将 Emby/TMDB/Telegram 常见时间转换为本地时区字符串 'YYYY-MM-DD HH:MM:SS'。
    支持输入：
      - ISO8601 字符串（可带 'Z'，可带任意位小数）
      - datetime.datetime 对象（naive 或 aware）
    若解析失败，返回 '未知'。
    """
    try:
        try:
            target_tz = TIMEZONE
        except NameError:
            try:
                from zoneinfo import ZoneInfo
                target_tz = ZoneInfo(get_setting('settings.timezone') or 'UTC')
            except Exception:
                from zoneinfo import ZoneInfo
                target_tz = ZoneInfo('UTC')

        from datetime import datetime
        from zoneinfo import ZoneInfo

        if isinstance(date_in, datetime):
            dt = date_in
        else:
            s = (str(date_in) or "").strip()
            if not s:
                return "未知"

            has_z = s.endswith(('Z', 'z'))
            if has_z:
                s = s[:-1]

            if '.' in s:
                main, frac = s.split('.', 1)
                frac_digits = ''.join(ch for ch in frac if ch.isdigit())
                frac6 = (frac_digits + '000000')[:6]
                s = f"{main}.{frac6}"

            dt = datetime.fromisoformat(s)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo('UTC'))

        return dt.astimezone(target_tz).strftime('%Y-%m-%d %H:%M:%S')

    except Exception:
        return "未知"

try:
    globals()['format_date'] = format_date
except Exception:
    pass

def get_event_time_str(payload: dict) -> str:
    """
    从 Emby Webhook payload 中提取时间并格式化为本地时区的 'YYYY-MM-DD HH:MM:SS'。
    规则：
      1) 优先使用 payload['Date']（UTC ISO8601），交给 format_date() 做时区转换；
      2) 若没有 'Date'，再尝试解析 Description 第一行里的中文/英文时间；
      3) 全部失败返回 '未知'。
    """
    try:
        s = (payload or {}).get("Date")
        if s:
            return format_date(s)
    except Exception:
        pass

    try:
        import re
        from datetime import datetime

        desc = ((payload or {}).get("Description") or "").splitlines()[0].strip()
        if desc:
            m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日.*?(上午|下午)?\s*(\d{1,2}):(\d{2})', desc)
            if m:
                y, mo, d, ampm, hh, mm = m.groups()
                hh = int(hh); mm = int(mm)
                if ampm in ('下午', 'PM', 'pm') and hh < 12:
                    hh += 12
                if ampm in ('上午', 'AM', 'am') and hh == 12:
                    hh = 0
                dt = datetime(int(y), int(mo), int(d), hh, mm, tzinfo=TIMEZONE)
                return dt.strftime('%Y-%m-%d %H:%M:%S')

            cleaned = re.sub(r'^[A-Za-z]+,\s*', '', desc)
            for fmt in ("%B %d, %Y %I:%M %p", "%b %d, %Y %I:%M %p", "%B %d %Y %I:%M %p"):
                try:
                    dt = datetime.strptime(cleaned, fmt).replace(tzinfo=TIMEZONE)
                    return dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass
    except Exception:
        pass

    return "未知"

def format_ticks_to_hms(ticks):
    """将Emby的ticks时间格式化为HH:MM:SS。"""
    if not isinstance(ticks, (int, float)) or ticks <= 0:
        return "00:00:00"
    seconds = ticks / 10_000_000
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

def get_program_type_from_path(path):
    """从文件路径中提取节目类型（例如：电影、剧集）。"""
    if not MEDIA_BASE_PATH or not path or not path.startswith(MEDIA_BASE_PATH):
        return None
    relative_path = path[len(MEDIA_BASE_PATH):].lstrip('/')
    parts = relative_path.split('/')
    if parts and parts[0]:
        return parts[0]
    return None

def extract_year_from_path(path):
    """从文件路径中提取年份。"""
    if not path:
        return None
    match = re.search(r'\((\d{4})\)', path)
    if match:
        year = match.group(1)
        return year
    return None

def find_nfo_file_in_dir(directory):
    """在指定目录的根层级查找第一个.nfo文件。"""
    try:
        for filename in os.listdir(directory):
            if filename.lower().endswith('.nfo'):
                return os.path.join(directory, filename)
    except OSError as e:
        print(f"❌ 读取目录 {directory} 时出错: {e}")
    return None

def parse_tmdbid_from_nfo(nfo_path):
    """
    从 .nfo 文件中解析出 TMDB ID。
    此函数会按优先级尝试多种常见格式。
    """
    if not nfo_path:
        return None
    try:
        with open(nfo_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        try:
            content_no_decl = re.sub(r'<\?xml[^>]*\?>', '', content).strip()
            if content_no_decl:
                root = ET.fromstring(content_no_decl)
                for uniqueid in root.findall('.//uniqueid[@type="tmdb"]'):
                    if uniqueid.get('default') == 'true' and uniqueid.text and uniqueid.text.isdigit():
                        print(f"✅ NFO 解析：找到默认的 <uniqueid type='tmdb'> -> {uniqueid.text.strip()}")
                        return uniqueid.text.strip()
                for uniqueid in root.findall('.//uniqueid[@type="tmdb"]'):
                    if uniqueid.text and uniqueid.text.isdigit():
                        print(f"✅ NFO 解析：找到 <uniqueid type='tmdb'> -> {uniqueid.text.strip()}")
                        return uniqueid.text.strip()
                
                tmdbid_tag = root.find('.//tmdbid')
                if tmdbid_tag is not None and tmdbid_tag.text and tmdbid_tag.text.isdigit():
                    print(f"✅ NFO 解析：找到 <tmdbid> -> {tmdbid_tag.text.strip()}")
                    return tmdbid_tag.text.strip()
        except ET.ParseError:
            print(f"⚠️ NFO 文件 '{os.path.basename(nfo_path)}' 不是有效的 XML，将使用正则表达式进行最终尝试。")

        match = re.search(r'themoviedb.org/(?:movie|tv)/(\d+)', content)
        if match:
            print(f"✅ NFO 解析 (正则)：从 URL 中找到 -> {match.group(1)}")
            return match.group(1)
        
        match = re.search(r'<tmdbid>(\d+)</tmdbid>', content, re.IGNORECASE)
        if match:
            print(f"✅ NFO 解析 (正则)：从标签中找到 -> {match.group(1)}")
            return match.group(1)
            
    except Exception as e:
        print(f"❌ 解析 NFO 文件 {nfo_path} 时出错: {e}")
    
    print(f"❌ 未能从 NFO 文件 '{os.path.basename(nfo_path)}' 中找到 TMDB ID。")
    return None

def get_emby_access_token():
    """使用用户名/密码向 Emby 认证以获取临时的 Access Token。"""
    print("🔑 正在使用用户名/密码获取 Emby Access Token...")
    if not all([EMBY_SERVER_URL, EMBY_USERNAME, EMBY_PASSWORD]):
        print("❌ 缺少获取 Token 所需的 Emby 用户名或密码配置。")
        return None

    url = f"{EMBY_SERVER_URL}/Users/AuthenticateByName"
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Authorization': 'MediaBrowser Client="Telegram Bot", Device="Script", DeviceId="emby-telegram-bot-backend", Version="1.0.0"'
    }
    payload = {'Username': EMBY_USERNAME, 'Pw': EMBY_PASSWORD}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            token = response.json().get('AccessToken')
            print("✅ 成功获取 Access Token。")
            return token
        else:
            print(f"❌ 获取 Access Token 失败。状态码: {response.status_code}, 响应: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ 获取 Access Token 时发生网络错误: {e}")
        return None

def scan_emby_item(item_id, item_name):
    """向Emby发送请求，扫描指定项目的文件夹以发现新内容。"""
    print(f"🔎 请求扫描 Emby 项目 ID: {item_id}, 名称: {item_name}")
    if not all([EMBY_SERVER_URL, EMBY_API_KEY]):
        return "❌ 扫描失败：Emby服务器配置不完整。"

    url = f"{EMBY_SERVER_URL}/Items/{item_id}/Refresh"
    params = {'api_key': EMBY_API_KEY, 'Recursive': 'true'}
    
    response = make_request_with_retry('POST', url, params=params, timeout=30)
    
    if response and response.status_code == 204:
        success_msg = f"✅ 已向 Emby 发送扫描请求： “{item_name}”。扫描过程将在后台进行，请稍后在 Emby 中查看结果。"
        print(success_msg)
        return success_msg
    else:
        status_code = response.status_code if response else 'N/A'
        response_text = response.text if response else 'No Response'
        error_msg = f'❌ 发送扫描请求 “{item_name}” (ID: {item_id}) 失败。状态码: {status_code}, 服务器响应: {response_text}'
        print(error_msg)
        return error_msg

def scan_all_emby_libraries():
    """向Emby发送请求，扫描所有媒体库以发现新内容。"""
    print("🔎 请求扫描所有Emby媒体库...")
    if not all([EMBY_SERVER_URL, EMBY_API_KEY]):
        return "❌ 扫描失败：Emby服务器配置不完整。"

    url = f"{EMBY_SERVER_URL}/Library/Refresh"
    params = {'api_key': EMBY_API_KEY}
    
    response = make_request_with_retry('POST', url, params=params, timeout=30)
    
    if response and response.status_code == 204:
        success_msg = "✅ 已向 Emby 发送扫描所有媒体库的请求。任务将在后台执行。"
        print(success_msg)
        return success_msg
    else:
        status_code = response.status_code if response else 'N/A'
        response_text = response.text if response else 'No Response'
        error_msg = f'❌ 发送“扫描全部”请求失败。状态码: {status_code}, 响应: {response_text}'
        print(error_msg)
        return error_msg

def refresh_emby_item(item_id, item_name):
    """向Emby发送请求，刷新指定项目的元数据。"""
    print(f"🔄 请求刷新 Emby 项目 ID: {item_id}, 名称: {item_name}")
    if not all([EMBY_SERVER_URL, EMBY_API_KEY]):
        return "❌ 刷新失败：Emby服务器配置不完整。"

    url = f"{EMBY_SERVER_URL}/Items/{item_id}/Refresh"
    params = {
        'api_key': EMBY_API_KEY,
        'Recursive': 'true',
        'MetadataRefreshMode': 'FullRefresh',
        'ReplaceAllMetadata': 'true'
    }
    
    response = make_request_with_retry('POST', url, params=params, timeout=30)
    
    if response and response.status_code == 204:
        success_msg = f"✅ 已向 Emby 发送刷新请求： “{item_name}”。刷新过程将在后台进行，请稍后在 Emby 中查看结果。"
        print(success_msg)
        return success_msg
    else:
        status_code = response.status_code if response else 'N/A'
        response_text = response.text if response else 'No Response'
        error_msg = f'❌ 发送刷新请求 “{item_name}” (ID: {item_id}) 失败。状态码: {status_code}, 服务器响应: {response_text}'
        print(error_msg)
        return error_msg

def delete_emby_item(item_id, item_name):
    """先获取 Access Token，然后使用 X-Emby-Authorization 头删除项目。"""
    print(f"🗑️ 请求从 Emby 删除项目 ID: {item_id}, 名称: {item_name}")

    access_token = get_emby_access_token()
    if not access_token:
        return f"❌ 删除 “{item_name}” 失败：无法从 Emby 服务器获取有效的用户访问令牌 (Access Token)。请检查 config.yaml 中的用户名和密码。"

    url = f"{EMBY_SERVER_URL}/Items/{item_id}"
    
    auth_header_value = (
        f'MediaBrowser Client="MyBot", Device="MyServer", '
        f'DeviceId="emby-telegram-bot-abc123", Version="1.0.0", Token="{access_token}"'
    )
    headers = {
        'X-Emby-Authorization': auth_header_value
    }
    
    response = make_request_with_retry('DELETE', url, headers=headers, timeout=15)
    
    if response and response.status_code == 204:
        success_msg = f'✅ Emby 媒体库中的节目 “{item_name}” 已成功删除。'
        print(success_msg)
        return success_msg
    else:
        status_code = response.status_code if response else 'N/A'
        response_text = response.text if response else 'No Response'
        error_msg = f'❌ 删除 Emby 项目 “{item_name}” (ID: {item_id}) 失败。状态码: {status_code}, 服务器响应: {response_text}'
        print(error_msg)
        return error_msg

def delete_media_files(item_path, delete_local=False, delete_cloud=False):
    """根据 Emby 中的项目路径，选择性地删除本地和/或云端的媒体文件夹，并返回详细日志。"""
    print(f"🗑️ 请求删除文件，Emby 路径: {item_path}, ℹ️ 本地: {delete_local}, ℹ️ 云端: {delete_cloud}")
    media_base_path = get_setting('settings.media_base_path')
    media_cloud_path = get_setting('settings.media_cloud_path')
    
    if item_path and os.path.splitext(item_path)[1]:
        item_path = os.path.dirname(item_path)

    if not media_base_path or not item_path or not item_path.startswith(media_base_path):
        error_msg = f"错误：项目路径 '{item_path}' 与基础路径 '{media_base_path}' 不匹配或无效。"
        print(f"❌ {error_msg}")
        return error_msg

    relative_path = os.path.relpath(item_path, media_base_path)
    log = []

    if delete_local:
        base_target_dir = os.path.join(media_base_path, relative_path)
        if os.path.isdir(base_target_dir):
            try:
                shutil.rmtree(base_target_dir)
                log.append(f"✅ 成功删除本地目录: {base_target_dir}")
                print(f"✅ 成功删除本地目录: {base_target_dir}")
            except Exception as e:
                log.append(f"❌ 删除本地目录失败: {e}")
                print(f"❌ 删除本地目录 '{base_target_dir}' 时出错: {e}")
        else:
            log.append(f"🟡 本地目录未找到: {base_target_dir}")
    
    if delete_cloud:
        if not media_cloud_path:
            return "❌ 操作失败：网盘目录 (media_cloud_path) 未在配置中设置。"
            
        cloud_target_dir = os.path.join(media_cloud_path, relative_path)
        if os.path.isdir(cloud_target_dir):
            try:
                shutil.rmtree(cloud_target_dir)
                log.append(f"✅ 成功删除网盘目录: {cloud_target_dir}")
                print(f"✅ 成功删除网盘目录: {cloud_target_dir}")
            except Exception as e:
                log.append(f"❌ 删除网盘目录失败: {e}")
                print(f"⚠️ 警告：删除网盘路径 '{cloud_target_dir}' 失败: {e}")
        else:
            log.append(f"🟡 网盘目录未找到: {cloud_target_dir}")

    if not log:
        return "🤷 未执行任何删除操作。"

    return f"✅ 删除操作完成：\n" + "\n".join(log)


def update_media_files(item_path):
    """根据 update_media.txt 的逻辑，从网盘路径更新文件到主媒体库路径。"""
    print(f"🔄 请求更新媒体，Emby 路径: {item_path}")
    media_base_path = get_setting('settings.media_base_path')
    media_cloud_path = get_setting('settings.media_cloud_path')

    if not media_base_path or not media_cloud_path:
        error_msg = "错误：`media_base_path` 或 `media_cloud_path` 未在配置中设置。"
        print(f"❌ {error_msg}")
        return error_msg

    if not item_path.startswith(media_base_path):
        error_msg = f"错误：项目路径 '{item_path}' 与基础路径 '{media_base_path}' 不匹配。"
        print(f"❌ {error_msg}")
        return error_msg

    relative_path = item_path.replace(media_base_path, "").lstrip('/')
    source_dir = os.path.join(media_cloud_path, relative_path)
    target_dir = os.path.join(media_base_path, relative_path)

    if not os.path.isdir(source_dir):
        error_msg = f"错误：在网盘找不到源目录 '{source_dir}'。"
        print(f"❌ {error_msg}")
        return error_msg

    os.makedirs(target_dir, exist_ok=True)
    
    metadata_extensions = {".nfo", ".jpg", ".jpeg", ".png", ".svg", ".ass", ".srt", ".sup", ".mp3", ".flac", ".aac", ".ssa", ".lrc"}
    update_log = []

    for root, _, files in os.walk(source_dir):
        for filename in files:
            source_file_path = os.path.join(root, filename)
            relative_subdir = os.path.relpath(root, source_dir)
            target_subdir = os.path.join(target_dir, relative_subdir) if relative_subdir != '.' else target_dir
            os.makedirs(target_subdir, exist_ok=True)

            file_ext = os.path.splitext(filename)[1].lower()

            if file_ext in metadata_extensions:
                target_file_path = os.path.join(target_subdir, filename)
                if not os.path.exists(target_file_path) or os.path.getmtime(source_file_path) > os.path.getmtime(target_file_path):
                    shutil.copy2(source_file_path, target_file_path)
                    update_log.append(f"• 复制元数据: {filename}")
            else:
                strm_filename = os.path.splitext(filename)[0] + ".strm"
                strm_file_path = os.path.join(target_subdir, strm_filename)
                
                source_mtime = os.path.getmtime(source_file_path)

                if not os.path.exists(strm_file_path) or source_mtime > os.path.getmtime(strm_file_path):
                    action = "创建" if not os.path.exists(strm_file_path) else "更新"
                    
                    with open(strm_file_path, 'w', encoding='utf-8') as f:
                        f.write(source_file_path)
                    
                    try:
                        os.utime(strm_file_path, (os.path.getatime(strm_file_path), source_mtime))
                    except Exception as e:
                        print(f"⚠️ 警告：设置文件时间戳失败: {e}")

                    update_log.append(f"• {action}链接: {strm_filename}")

    if not update_log:
        return f"✅ `/{relative_path}` 无需更新，文件已是最新。"
        
    print(f"✅ `/{relative_path}` 更新完成。")
    
    details = "\n".join(update_log)
    return f"✅ `/{relative_path}` 已更新完成！\n\n变更详情：\n{details}"

def get_tmdb_details_by_id(tmdb_id):
    """通过TMDB ID获取媒体详情，自动尝试电影和剧集。"""
    print(f"🔍 正在通过 TMDB ID: {tmdb_id} 查询详情")
    if not TMDB_API_TOKEN: return None
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    
    for media_type in ['tv', 'movie']:
        url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
        params = {'api_key': TMDB_API_TOKEN, 'language': 'zh-CN'}
        response = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies)
        if response:
            details = response.json()
            title = details.get('title') or details.get('name')
            if title:
                print(f"✅ 在 TMDB 找到匹配项: {title} (类型: {media_type})")
                return details
    
    print(f"❌ 未在 TMDB 中找到 ID 为 {tmdb_id} 的任何内容。")
    return None

def _get_geo_baidu(ip):
    """使用百度API获取地理位置。"""
    url = f"https://opendata.baidu.com/api.php?co=&resource_id=6006&oe=utf8&query={ip}"
    response = make_request_with_retry('GET', url, timeout=5)
    if not response:
        return "未知位置"
    try:
        data = response.json()
        if data.get('status') == '0' and data.get('data'):
            location_info = data['data'][0].get('location')
            if location_info:
                print(f"✅ 成功从百度 API 获取到 IP ({ip}) 的地理位置: {location_info}")
                return location_info
    except (json.JSONDecodeError, IndexError, KeyError) as e:
        print(f"❌ 解析百度 API 响应时发生错误。IP: {ip}, 错误: {e}")
    return "未知位置"

def _get_geo_ip138(ip):
    """使用 IP138 API 获取地理位置。"""
    token = CONFIG.get('settings', {}).get('ip_api_token_ip138')
    if not token:
        print("❌ IP138 API 错误: 未在 config.yaml 中配置 'ip_api_token_ip138'。")
        return "未知位置 (缺少Token)"
    
    url = f"https://api.ip138.com/ipdata/?ip={ip}&datatype=jsonp&token={token}"
    response = make_request_with_retry('GET', url, timeout=5)
    if not response:
        return "未知位置"
    try:
        content = response.text
        if content.startswith('jsonp_'):
            content = content[content.find('{') : content.rfind('}')+1]
        
        data = json.loads(content)
        
        if data.get('ret') == 'ok':
            geo_data = data.get('data', [])
            country = geo_data[0]
            province = geo_data[1]
            city = geo_data[2]
            district = geo_data[3]
            isp = geo_data[4]
            
            location = ""
            if country == "中国":
                loc_parts = []
                if province:
                    loc_parts.append(province)
                if city and city != province:
                    loc_parts.append(city)
                if district:
                    loc_parts.append(district)
                
                location = ''.join(p for p in loc_parts if p)
            else:
                loc_parts = [p for p in [country, province, city] if p]
                location = ''.join(loc_parts)

            return f"{location} {isp}".strip()

    except (json.JSONDecodeError, IndexError, KeyError) as e:
        print(f"❌ 解析 IP138 API 响应时发生错误。IP: {ip}, 错误: {e}")
    return "未知位置"

def _get_geo_pconline(ip):
    """使用太平洋电脑API获取地理位置。"""
    url = f"https://whois.pconline.com.cn/ipJson.jsp?ip={ip}&json=true"
    response = make_request_with_retry('GET', url, timeout=5)
    if not response:
        return "未知位置"
    try:
        data = response.json()
        addr = data.get('addr')
        if addr:
            return addr.replace(ip, '').strip()
    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ 解析太平洋电脑 API 响应时发生错误。IP: {ip}, 错误: {e}")
    return "未知位置"

def _get_geo_vore(ip):
    """使用Vore API获取地理位置。"""
    url = f"https://api.vore.top/api/IPdata?ip={ip}"
    response = make_request_with_retry('GET', url, timeout=5)
    if not response:
        return "未知位置"
    try:
        data = response.json()
        if data.get('code') == 200 and data.get('adcode', {}).get('o'):
            return data['adcode']['o'].replace(' - ', ' ')
    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ 解析 Vore API 响应时发生错误。IP: {ip}, 错误: {e}")
    return "未知位置"

def _get_geo_ipapi(ip):
    """使用 IP-API.com 获取地理位置。"""
    url = f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,isp&lang=zh-CN"
    response = make_request_with_retry('GET', url, timeout=5)
    if not response:
        return "未知位置"
    try:
        data = response.json()
        if data.get('status') == 'success':
            isp_map = {
                'Chinanet': '电信', 'China Telecom': '电信',
                'China Unicom': '联通', 'CHINA169': '联通',
                'CNC Group': '联通', 'China Netcom': '联通',
                'China Mobile': '移动', 'China Broadcasting': '广电'
            }
            isp_en = data.get('isp', '')
            isp = isp_en
            for keyword, name in isp_map.items():
                if keyword.lower() in isp_en.lower():
                    isp = name
                    break
            
            region = data.get('regionName', '')
            city = data.get('city', '')
            
            if region and city and region in city:
                city = ''
            
            geo_parts = [p for p in [region, city] if p]
            location_part = ''.join(geo_parts)
            
            full_location = f"{location_part} {isp}".strip()
            return full_location if full_location else "未知位置"

    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ 解析 IP-API.com 响应时发生错误。IP: {ip}, 错误: {e}")
    return "未知位置"

def get_ip_geolocation(ip):
    """通过IP地址获取地理位置信息（根据配置选择API）。"""
    if not ip or ip.startswith('192.168.') or ip.startswith('10.') or ip.startswith('172.'):
        return "局域网"

    provider = get_setting('settings.ip_api_provider') or 'baidu'
    print(f"🌍 正在使用 {provider.upper()} API 查询 IP: {ip}")
    
    location = "未知位置"
    if provider == 'ip138':
        location = _get_geo_ip138(ip)
    elif provider == 'pconline':
        location = _get_geo_pconline(ip)
    elif provider == 'vore':
        location = _get_geo_vore(ip)
    elif provider == 'ipapi':
        location = _get_geo_ipapi(ip)
    else:
        location = _get_geo_baidu(ip)

    return location

def get_emby_user_by_name(username):
    """通过用户名获取完整的Emby用户对象。"""
    print(f"👤 正在通过用户名 '{username}' 查询Emby用户...")
    if not all([EMBY_SERVER_URL, EMBY_API_KEY]):
        return None, "Emby服务器配置不完整。"
    
    url = f"{EMBY_SERVER_URL}/Users"
    params = {'api_key': EMBY_API_KEY}
    response = make_request_with_retry('GET', url, params=params, timeout=10)
    
    if response:
        users_data = response.json()
        for user in users_data:
            if user.get('Name', '').lower() == username.lower():
                print(f"✅ 找到用户 '{username}'，ID: {user.get('Id')}")
                return user, None
        return None, f"找不到用户名为 '{username}' 的用户。"
    else:
        return None, "从Emby API获取用户列表失败。"

def get_emby_user_policy(user_id):
    """获取指定用户的策略(Policy)对象。"""
    print(f"📜 正在获取用户ID {user_id} 的完整信息以提取策略...")
    
    url = f"{EMBY_SERVER_URL}/Users/{user_id}"
    params = {'api_key': EMBY_API_KEY}
    response = make_request_with_retry('GET', url, params=params, timeout=10)
    
    if response:
        try:
            user_data = response.json()
            policy = user_data.get('Policy')
            if policy:
                return policy, None
            else:
                return None, "获取用户策略失败：在返回的用户数据中未找到Policy对象。"
        except json.JSONDecodeError:
            return None, "获取用户策略失败：无法解析Emby服务器返回的用户信息。"
    
    return None, "获取用户策略失败：无法从Emby API获取该用户信息（请检查template_user_id是否正确）。"

def set_emby_user_password(user_id, password):
    """设置或修改用户的密码。"""
    print(f"🔑 正在为用户ID {user_id} 设置新密码...")
    url = f"{EMBY_SERVER_URL}/Users/{user_id}/Password"
    headers = {'X-Emby-Token': EMBY_API_KEY}
    payload = {"Id": user_id, "NewPw": password}
    response = make_request_with_retry('POST', url, headers=headers, json=payload, timeout=10)
    return response is not None

def delete_emby_user_by_id(user_id):
    """通过ID删除一个Emby用户。"""
    print(f"🗑️ 正在删除用户ID: {user_id}")
    url = f"{EMBY_SERVER_URL}/Users/{user_id}"
    params = {'api_key': EMBY_API_KEY}
    response = make_request_with_retry('DELETE', url, params=params, timeout=10)
    return response is not None

def rename_emby_user(user_id, new_username):
    """修改指定Emby用户的用户名。"""
    print(f"✏️ 正在为用户ID {user_id} 修改用户名为 '{new_username}'...")
    
    existing_user, _ = get_emby_user_by_name(new_username)
    if existing_user:
        return f"❌ 修改失败：用户名 '{new_username}' 已被其他用户占用。"

    get_url = f"{EMBY_SERVER_URL}/Users/{user_id}"
    params = {'api_key': EMBY_API_KEY}
    get_response = make_request_with_retry('GET', get_url, params=params, timeout=10)
    if not get_response:
        return "❌ 修改失败：无法获取当前用户的详细信息。"
    
    user_data = get_response.json()
    
    user_data['Name'] = new_username
    post_url = f"{EMBY_SERVER_URL}/Users/{user_id}"
    headers = {'X-Emby-Token': EMBY_API_KEY, 'Content-Type': 'application/json'}
    post_response = make_request_with_retry('POST', post_url, headers=headers, json=user_data, timeout=10)

    if post_response:
        return f"✅ 用户名已成功修改为 '{new_username}'。"
    else:
        return f"❌ 修改用户名失败，服务器未成功响应。"

def send_manage_main_menu(chat_id, user_id, message_id=None):
    """发送或编辑/manage命令的主菜单。"""
    prompt_message = "请选择管理类别："
    buttons = [
        [{'text': '🎦 Emby节目管理', 'callback_data': f'm_filesmain_{user_id}'}],
        [{'text': '👤 Emby用户管理', 'callback_data': f'm_usermain_{user_id}'}],
        [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{user_id}'}]
    ]
    if message_id:
        edit_telegram_message(chat_id, message_id, escape_markdown(prompt_message), inline_buttons=buttons)
    else:
        send_deletable_telegram_notification(escape_markdown(prompt_message), chat_id=chat_id, inline_buttons=buttons, delay_seconds=180)

def create_emby_user(username, password):
    """创建一个新Emby用户，并从模板用户克隆配置。"""
    if not EMBY_TEMPLATE_USER_ID:
        return "❌ 创建失败：未在配置文件中设置 `template_user_id`。"

    existing_user, _ = get_emby_user_by_name(username)
    if existing_user:
        return f"❌ 创建失败：用户名 '{username}' 已存在。"

    template_policy, error = get_emby_user_policy(EMBY_TEMPLATE_USER_ID)
    if error:
        return f"❌ 创建失败：无法获取模板用户(ID: {EMBY_TEMPLATE_USER_ID})的配置。错误: {error}"
    print(f"✅ 已成功获取模板用户 {EMBY_TEMPLATE_USER_ID} 的策略。")

    print(f"➕ 正在创建新用户: {username}...")
    create_url = f"{EMBY_SERVER_URL}/Users/New"
    params = {'api_key': EMBY_API_KEY}
    create_payload = {'Name': username}
    response = make_request_with_retry('POST', create_url, params=params, json=create_payload, timeout=10)
    
    if not response:
        return "❌ 创建失败：调用Emby API创建用户时出错。"
    
    new_user = response.json()
    new_user_id = new_user.get('Id')
    print(f"✅ 用户 '{username}' 已创建，新ID: {new_user_id}。")

    print(f"📜 正在为新用户 {new_user_id} 应用模板策略...")
    policy_url = f"{EMBY_SERVER_URL}/Users/{new_user_id}/Policy"
    policy_resp = make_request_with_retry('POST', policy_url, params=params, json=template_policy, timeout=10)
    if not policy_resp:
        delete_emby_user_by_id(new_user_id)
        return "❌ 创建失败：为新用户应用策略时出错，已回滚操作。"
    print("✅ 策略应用成功。")

    print(f"🔑 正在为新用户 {new_user_id} 设置密码...")
    if not set_emby_user_password(new_user_id, password):
        delete_emby_user_by_id(new_user_id)
        return "❌ 创建失败：为新用户设置密码时出错，已回滚操作。"
    print("✅ 密码设置成功。")
    
    return f"✅ 成功创建用户 '{username}'，配置已从模板用户克隆。"

def get_all_emby_users():
    """从Emby获取所有用户列表，并使用1分钟缓存。"""
    now = time.time()
    
    if 'users' in EMBY_USERS_CACHE and (now - EMBY_USERS_CACHE.get('timestamp', 0) < 60):
        print("ℹ️ 从缓存中获取Emby用户列表。")
        return EMBY_USERS_CACHE['users']

    print("🔑 正在从Emby API获取完整用户列表...")
    if not all([EMBY_SERVER_URL, EMBY_API_KEY]):
        print("❌ 缺少获取用户列表所需的Emby服务器配置。")
        return set()

    url = f"{EMBY_SERVER_URL}/Users"
    params = {'api_key': EMBY_API_KEY}
    response = make_request_with_retry('GET', url, params=params, timeout=10)
    
    if response:
        users_data = response.json()
        user_names = {user['Name'] for user in users_data if 'Name' in user}
        
        EMBY_USERS_CACHE['users'] = user_names
        EMBY_USERS_CACHE['timestamp'] = now
        print(f"✅ 成功获取并缓存了 {len(user_names)} 个用户名。")
        return user_names
    else:
        print("❌ 获取Emby用户列表失败。")
        return set()

def search_tmdb_multi(title, year=None):
    """
    在TMDB上同时搜索电影和剧集，并返回一个包含标题和年份的结果列表。
    :param title: 搜索关键词
    :param year: 年份 (可选)
    :return: 包含{'title': str, 'year': str}字典的列表
    """
    print(f"🔍 正在 TMDB 综合搜索: {title} ({year or '任意年份'})")
    if not TMDB_API_TOKEN: return []
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    
    all_results = []
    
    for media_type in ['movie', 'tv']:
        params = {'api_key': TMDB_API_TOKEN, 'query': title, 'language': 'zh-CN'}
        if year:
            if media_type == 'tv':
                params['first_air_date_year'] = year
            else:
                params['year'] = year
        
        url = f"https://api.themoviedb.org/3/search/{media_type}"
        response = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies)
        
        if response:
            results = response.json().get('results', [])
            for item in results:
                item_title = item.get('title') or item.get('name')
                release_date = item.get('release_date') or item.get('first_air_date')
                item_year = release_date.split('-')[0] if release_date else None
                if item_title:
                   all_results.append({'title': item_title.strip(), 'year': item_year})

    unique_results = []
    seen = set()
    for res in all_results:
        identifier = (res['title'], res['year'])
        if identifier not in seen:
            unique_results.append(res)
            seen.add(identifier)

    print(f"✅ TMDB 综合搜索找到 {len(unique_results)} 个唯一结果。")
    return unique_results

def search_tmdb_by_title(title, year=None, media_type='tv'):
    """通过标题和年份在TMDB上搜索媒体。"""
    print(f"🔍 正在 TMDB 搜索: {title} ({year})")
    if not TMDB_API_TOKEN: return None
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    params = {'api_key': TMDB_API_TOKEN, 'query': title, 'language': 'zh-CN'}
    if year:
        params['first_air_date_year' if media_type == 'tv' else 'year'] = year
    url = f"https://api.themoviedb.org/3/search/{media_type}"
    response = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies)
    if response:
        results = response.json().get('results', [])
        if not results:
            print(f"❌ TMDB 未找到匹配结果。")
            return None
        exact_match = next((item for item in results if (item.get('name') or item.get('title')) == title), None)
        if exact_match:
            print(f"✅ 找到精确匹配: {exact_match.get('name') or exact_match.get('title')}, ID: {exact_match.get('id')}")
            return exact_match.get('id')
        else:
            results.sort(key=lambda x: (x.get('popularity', 0)), reverse=True)
            popular_match = results[0]
            print(f"⚠️ 未找到精确匹配，返回最热门结果: {popular_match.get('name') or popular_match.get('title')}, ID: {popular_match.get('id')}")
            return popular_match.get('id')
    print(f"❌ TMDB 搜索失败")
    return None

def get_media_details(item, user_id):
    """
    获取媒体的详细信息，包括海报和TMDB链接。
    :param item: Emby项目字典
    :param user_id: Emby用户ID
    :return: 包含海报URL、TMDB链接、年份和TMDB ID的字典
    """
    details = {'poster_url': None, 'tmdb_link': None, 'year': None, 'tmdb_id': None}
    if not TMDB_API_TOKEN:
        print("⚠️ 未配置 TMDB_API_TOKEN，使用 Emby 海报作为封面。")
        item_id = item.get("Id")
        if item_id and EMBY_SERVER_URL and EMBY_API_KEY:
            details["poster_url"] = f"{EMBY_SERVER_URL}/Items/{item_id}/Images/Primary?api_key={EMBY_API_KEY}"
        details["year"] = item.get("ProductionYear") or extract_year_from_path(item.get("Path"))
        return details
    item_type = item.get('Type')
    tmdb_id, api_type = None, None
    details['year'] = item.get('ProductionYear') or extract_year_from_path(item.get('Path'))
    print(f"ℹ️ 正在获取项目 {item.get('Name')} ({item.get('Id')}) 的媒体详情。类型: {item_type}")

    if item_type == 'Movie':
        api_type = 'movie'
        tmdb_id = item.get('ProviderIds', {}).get('Tmdb')
        if tmdb_id:
            details['tmdb_link'] = f"https://www.themoviedb.org/movie/{tmdb_id}"
    elif item_type == 'Series':
        api_type = 'tv'
        tmdb_id = item.get('ProviderIds', {}).get('Tmdb')
        if tmdb_id:
            details['tmdb_link'] = f"https://www.themoviedb.org/tv/{tmdb_id}"
    elif item_type == 'Episode':
        api_type = 'tv'
        series_provider_ids = item.get('SeriesProviderIds', {}) or item.get('Series', {}).get('ProviderIds', {})
        tmdb_id = series_provider_ids.get('Tmdb')
        if not tmdb_id and item.get('SeriesId'):
            print(f"⚠️ 无法从 Episode 获取 TMDB ID，尝试从 SeriesId ({item.get('SeriesId')}) 获取。")
            series_id = item.get('SeriesId')
            request_user_id = user_id or EMBY_USER_ID
            url_part = f"/Users/{request_user_id}/Items/{series_id}" if request_user_id else f"/Items/{series_id}"
            url = f"{EMBY_SERVER_URL}{url_part}"
            response = make_request_with_retry('GET', url, params={'api_key': EMBY_API_KEY}, timeout=10)
            if response:
                tmdb_id = response.json().get('ProviderIds', {}).get('Tmdb')
        if not tmdb_id:
            print(f"⚠️ 仍然没有 TMDB ID，尝试通过标题搜索 TMDB。")
            tmdb_id = search_tmdb_by_title(item.get('SeriesName'), details.get('year'), media_type='tv')
        if tmdb_id:
            season_num, episode_num = item.get('ParentIndexNumber'), item.get('IndexNumber')
            if season_num is not None and episode_num is not None:
                details['tmdb_link'] = f"https://www.themoviedb.org/tv/{tmdb_id}/season/{season_num}/episode/{episode_num}"
            else:
                details['tmdb_link'] = f"https://www.themoviedb.org/tv/{tmdb_id}"
    if tmdb_id:
        details['tmdb_id'] = tmdb_id
        if tmdb_id in POSTER_CACHE:
            cached_item = POSTER_CACHE[tmdb_id]
            cached_time = datetime.fromisoformat(cached_item['timestamp'])
            if datetime.now() - cached_time < timedelta(days=POSTER_CACHE_TTL_DAYS):
                details['poster_url'] = cached_item['url']
                print(f"✅ 从缓存获取到 TMDB ID {tmdb_id} 的海报链接。")
                return details
        url = f"https://api.themoviedb.org/3/{api_type}/{tmdb_id}?api_key={TMDB_API_TOKEN}&language=zh-CN"
        proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
        response = make_request_with_retry('GET', url, timeout=10, proxies=proxies)
        if response:
            poster_path = response.json().get('poster_path')
            if poster_path:
                details['poster_url'] = f"https://image.tmdb.org/t/p/w500{poster_path}"
                POSTER_CACHE[tmdb_id] = {'url': details['poster_url'], 'timestamp': datetime.now().isoformat()}
                save_poster_cache()
                print(f"✅ 成功从 TMDB 获取并缓存海报。")
    return details

def safe_edit_or_send_message(chat_id, message_id, text, buttons=None, disable_preview=True, delete_after=None):
    """
    先尝试 editMessageText；失败（包含“消息不存在/未修改”等）时，改为新发一条消息。
    delete_after=None -> 发“常驻”消息；否则发可自动删除的消息（秒）
    """
    resp = None
    try:
        if message_id:
            resp = edit_telegram_message(chat_id, message_id, text, inline_buttons=buttons, disable_preview=disable_preview)
    except Exception:
        resp = None
    
    if not resp:
        if delete_after is None:
            send_telegram_notification(text=text, chat_id=chat_id, inline_buttons=buttons, disable_preview=disable_preview)
        else:
            send_deletable_telegram_notification(text=text, chat_id=chat_id, inline_buttons=buttons, disable_preview=disable_preview, delay_seconds=delete_after)

def send_telegram_notification(text, photo_url=None, chat_id=None, inline_buttons=None, disable_preview=False):
    """
    发送一个Telegram通知：
    - 如果有 photo_url：先由本机下载图片 bytes，再以 multipart 上传给 Telegram（避免 Telegram 抓 URL 失败 & 避免暴露 api_key）
    - 如果下载/上传失败：自动降级为 sendMessage（保证不丢通知）
    """
    if not chat_id:
        print("❌ 错误：未指定 chat_id。")
        return

    print(f"💬 正在向 Chat ID {chat_id} 发送 Telegram 通知...")
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    api_base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"

    # 统一准备按钮
    reply_markup = None
    if inline_buttons:
        keyboard_layout = inline_buttons if isinstance(inline_buttons[0], list) else [[button] for button in inline_buttons]
        reply_markup = json.dumps({'inline_keyboard': keyboard_layout})

    # 1) 有封面：先下载后上传
    if photo_url:
        try:
            # 下载图片（由我们服务器访问 Emby，避免 Telegram 去抓 URL）
            img_resp = make_request_with_retry('GET', photo_url, timeout=15, proxies=proxies)
            if img_resp and img_resp.status_code == 200:
                ct = (img_resp.headers.get('Content-Type') or '').lower()
                if ct.startswith('image/'):
                    files = {'photo': ('poster.jpg', img_resp.content)}
                    data = {
                        'chat_id': chat_id,
                        'caption': text,
                        'parse_mode': 'MarkdownV2',
                        'disable_web_page_preview': disable_preview
                    }
                    if reply_markup:
                        data['reply_markup'] = reply_markup

                    resp = make_request_with_retry('POST', api_base + 'sendPhoto', data=data, files=files, timeout=20, proxies=proxies)
                    if resp:
                        return
                    print("⚠️ sendPhoto(upload) 失败，将降级为纯文字。")
                else:
                    print(f"⚠️ 海报下载成功但不是图片 content-type={ct}，将降级为纯文字。")
            else:
                sc = img_resp.status_code if img_resp else None
                print(f"⚠️ 海报下载失败 status={sc}，将降级为纯文字。")
        except Exception as e:
            print(f"⚠️ 海报下载/上传异常：{e}，将降级为纯文字。")

    # 2) 降级：发纯文本
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'MarkdownV2',
        'disable_web_page_preview': disable_preview
    }
    if reply_markup:
        payload['reply_markup'] = reply_markup

    make_request_with_retry('POST', api_base + 'sendMessage', data=payload, timeout=20, proxies=proxies)

def send_deletable_telegram_notification(text, photo_url=None, chat_id=None, inline_buttons=None, delay_seconds=60, disable_preview=False):
    """
    发送一个可自动删除的Telegram通知。
    :param text: 消息文本
    :param photo_url: 图片URL
    :param chat_id: 聊天ID
    :param inline_buttons: 内联按钮列表
    :param delay_seconds: 自动删除的延迟时间
    :param disable_preview: 是否禁用URL预览
    """
    async def send_and_delete():
        proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
        if not chat_id:
            return

        api_url_base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
        payload = {
            'chat_id': chat_id,
            'parse_mode': 'MarkdownV2',
            'disable_web_page_preview': disable_preview
        }

        if inline_buttons:
            keyboard_layout = inline_buttons if isinstance(inline_buttons[0], list) else [[button] for button in inline_buttons]
            payload['reply_markup'] = json.dumps({'inline_keyboard': keyboard_layout})

        api_url = api_url_base + ('sendPhoto' if photo_url else 'sendMessage')
        if photo_url:
            payload['photo'], payload['caption'] = photo_url, text
        else:
            payload['text'] = text

        print(f"💬 正在向 Chat ID {chat_id} 发送可删除的通知，{delay_seconds}秒后删除。")
        response = make_request_with_retry('POST', api_url, data=payload, timeout=20, proxies=proxies)
        if not response:
            return

        sent_message = response.json().get('result', {})
        message_id = sent_message.get('message_id')
        if not message_id or delay_seconds <= 0:
            return

        await asyncio.sleep(delay_seconds)
        print(f"⏳ 正在删除消息 ID: {message_id}。")
        delete_url = api_url_base + 'deleteMessage'
        delete_payload = {'chat_id': chat_id, 'message_id': message_id}

        del_response = make_request_with_retry('POST', delete_url, data=delete_payload, timeout=10, proxies=proxies, max_retries=5, retry_delay=5)
        if del_response is None:
            print(f"ℹ️ 删除消息 {message_id}：可能已不存在或无权限，已忽略。")

    threading.Thread(target=lambda: asyncio.run(send_and_delete())).start()
    
def send_simple_telegram_message(text, chat_id=None, delay_seconds=60):
    """发送一个简单的可自动删除的文本消息。"""
    target_chat_id = chat_id if chat_id else ADMIN_USER_ID
    if not target_chat_id: return
    send_deletable_telegram_notification(text, chat_id=target_chat_id, delay_seconds=delay_seconds)

def answer_callback_query(callback_query_id, text=None, show_alert=False):
    """响应一个内联按钮回调查询。"""
    print(f"📞 回答回调查询: {callback_query_id}")
    params = {'callback_query_id': callback_query_id, 'show_alert': show_alert}
    if text: params['text'] = text
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
    make_request_with_retry('POST', url, params=params, timeout=5, proxies=proxies)

def edit_telegram_message(chat_id, message_id, text, inline_buttons=None, disable_preview=False):
    """编辑一个已发送的Telegram消息；返回请求响应对象（成功/失败均返回None）。"""
    print(f"✏️ 正在编辑 Chat ID {chat_id}, Message ID {message_id} 的消息。")
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText"
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
        'parse_mode': 'MarkdownV2',
        'disable_web_page_preview': disable_preview
    }
    if inline_buttons is not None:
        payload['reply_markup'] = json.dumps({'inline_keyboard': inline_buttons})

    try:
        resp = make_request_with_retry('POST', url, json=payload, timeout=10, proxies=proxies)
        return resp
    except Exception as e:
        print(f"❌ edit_telegram_message 调用异常：{e}")
        return None

def delete_telegram_message(chat_id, message_id):
    """删除一个Telegram消息。"""
    print(f"🗑️ 正在删除 Chat ID {chat_id}, Message ID {message_id} 的消息。")
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
    payload = {'chat_id': chat_id, 'message_id': message_id}
    make_request_with_retry('POST', url, data=payload, timeout=10, proxies=proxies)

def delete_user_message_later(chat_id, message_id, delay_seconds=60):
    """在指定延迟后删除用户消息。"""
    async def delete_later():
        await asyncio.sleep(delay_seconds)
        delete_telegram_message(chat_id, message_id)
    threading.Thread(target=lambda: asyncio.run(delete_later())).start()
    
def is_super_admin(user_id):
    """检查用户ID是否是超级管理员。"""
    if not ADMIN_USER_ID:
        print("⚠️ 未配置 ADMIN_USER_ID，所有用户都将无法执行管理员操作。")
        return False
    is_admin = str(user_id) == str(ADMIN_USER_ID)
    return is_admin

def is_user_authorized(user_id):
    """检查用户是否获得授权（超级管理员或群组成员）。"""
    if is_super_admin(user_id):
        return True
    if not GROUP_ID:
        return False
    now = time.time()
    if user_id in GROUP_MEMBER_CACHE and (now - GROUP_MEMBER_CACHE[user_id]['timestamp'] < 60):
        print(f"👥 用户 {user_id} 授权状态从缓存获取：{GROUP_MEMBER_CACHE[user_id]['is_member']}")
        return GROUP_MEMBER_CACHE[user_id]['is_member']
    print(f"👥 正在查询用户 {user_id} 在群组 {GROUP_ID} 中的成员身份。")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChatMember"
    params = {'chat_id': GROUP_ID, 'user_id': user_id}
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    response = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies)
    if response:
        result = response.json().get('result', {})
        status = result.get('status')
        if status in ['creator', 'administrator', 'member', 'restricted']:
            GROUP_MEMBER_CACHE[user_id] = {'is_member': True, 'timestamp': now}
            print(f"✅ 用户 {user_id} 验证通过。")
            return True
        else:
            GROUP_MEMBER_CACHE[user_id] = {'is_member': False, 'timestamp': now}
            print(f"❌ 用户 {user_id} 验证失败，状态: {status}。")
            return False
    else:
        print(f"❌ 授权失败：查询用户 {user_id} 的群成员身份失败，已拒绝访问。")
        return False

def is_bot_admin(chat_id, user_id):
    """检查用户是否是某个聊天（群组/频道）的管理员。"""
    if is_super_admin(user_id):
        return True
    if chat_id > 0:
        return False
    now = time.time()
    if chat_id in ADMIN_CACHE and (now - ADMIN_CACHE[chat_id]['timestamp'] < 300):
        return user_id in ADMIN_CACHE[chat_id]['admins']
    admin_ids = []
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChatAdministrators"
    params = {'chat_id': chat_id}
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    response = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies)
    if response:
        admins = response.json().get('result', [])
        admin_ids = [admin['user']['id'] for admin in admins]
        ADMIN_CACHE[chat_id] = {'admins': admin_ids, 'timestamp': now}
        return user_id in admin_ids
    else:
        if chat_id in ADMIN_CACHE:
            return user_id in ADMIN_CACHE[chat_id]['admins']
        return False

def get_active_sessions():
    """从Emby服务器获取活跃的播放会话。"""
    print("🎬 正在查询 Emby 活跃会话。")
    if not EMBY_SERVER_URL or not EMBY_API_KEY:
        print("❌ 缺少 Emby 服务器配置，无法查询会话。")
        return []
    url = f"{EMBY_SERVER_URL}/Sessions"
    params = {'api_key': EMBY_API_KEY, 'activeWithinSeconds': 360}
    response = make_request_with_retry('GET', url, params=params, timeout=15)
    sessions = response.json() if response else []
    print(f"✅ 查询到 {len(sessions)} 个活跃会话。")
    return sessions

def get_active_sessions_info(user_id):
    """
    获取所有正在播放的会话的详细信息，并格式化为消息文本。
    该函数首先查询所有活跃的Emby会话，然后为每个会话生成一个格式化的消息和内联按钮。
    
    Args:
        user_id (str or int): 发起查询的用户ID。用于权限检查和回调数据。

    Returns:
        str or list: 如果没有活跃会话，返回一个字符串消息；否则返回一个包含
                     每个会话详细信息的字典列表。每个字典包含'message', 'buttons'和'poster_url'。
    """
    sessions = [s for s in get_active_sessions() if s.get('NowPlayingItem')]
    
    if not sessions:
        print("ℹ️ 当前没有正在播放的会话。")
        return "✅ 当前无人观看 Emby。"
    
    sessions_data = []
    
    print(f"ℹ️ 发现了 {len(sessions)} 个会话。")
    
    for session in sessions:
        try:
            item = session.get('NowPlayingItem', {})
            session_user_id, session_id = session.get('UserId'), session.get('Id')
            
            if not item or not session_id:
                print(f"⚠️ 警告: 跳过会话，因为它缺少 NowPlayingItem 或 ID。会话数据: {session}")
                continue

            print(f"ℹ️ 正在处理会话: {session_id}, 用户: {session.get('UserName')}")
            
            media_details = get_media_details(item, session_user_id)
            tmdb_link, year = media_details.get('tmdb_link'), media_details.get('year')
            
            raw_user_name = session.get('UserName', '未知用户')
            raw_player = session.get('Client', '未知播放器')
            raw_device = session.get('DeviceName', '未知设备')
            
            ip_address = session.get('RemoteEndPoint', '').split(':')[0]
            location = get_ip_geolocation(ip_address)
            
            raw_title = item.get('SeriesName') if item.get('Type') == 'Episode' else item.get('Name', '未知标题')
            year_str = f" ({year})" if year else ""
            
            raw_episode_info = ""
            if item.get('Type') == 'Episode':
                s_num, e_num, e_name_raw = item.get('ParentIndexNumber'), item.get('IndexNumber'), item.get('Name')
                if s_num is not None and e_num is not None:
                    raw_episode_info = f" S{s_num:02d}E{e_num:02d} {e_name_raw or ''}"
                else:
                    raw_episode_info = f" {e_name_raw or ''}"
            
            program_full_title_raw = f"{raw_title}{year_str}{raw_episode_info}"
            
            session_lines = [
                f"\n",
                f"👤 *用户*: {escape_markdown(raw_user_name)}",
                f"*{escape_markdown('─' * 20)}*"
            ]
            if get_setting('settings.content_settings.status_feedback.show_player'):
                session_lines.append(f"播放器：{escape_markdown(raw_player)}")
            if get_setting('settings.content_settings.status_feedback.show_device'):
                session_lines.append(f"设备：{escape_markdown(raw_device)}")
            
            if get_setting('settings.content_settings.status_feedback.show_location'):
                if location == "局域网":
                    location_line = "位置：" + escape_markdown("局域网")
                else:
                    location_line = f"位置：`{escape_markdown(ip_address)}` {escape_markdown(location)}"
                session_lines.append(location_line)

            if get_setting('settings.content_settings.status_feedback.show_media_detail'):
                program_line = f"[{escape_markdown(program_full_title_raw)}]({tmdb_link})" if tmdb_link and get_setting('settings.content_settings.status_feedback.media_detail_has_tmdb_link') else escape_markdown(program_full_title_raw)
                session_lines.append(f"节目：{program_line}")
                
            pos_ticks, run_ticks = session.get('PlayState', {}).get('PositionTicks', 0), item.get('RunTimeTicks')
            if run_ticks and run_ticks > 0:
                percent = (pos_ticks / run_ticks) * 100
                raw_progress_text = f"{percent:.1f}% ({format_ticks_to_hms(pos_ticks)} / {format_ticks_to_hms(run_ticks)})"
                session_lines.append(f"进度：{escape_markdown(raw_progress_text)}")
                
            raw_program_type = get_program_type_from_path(item.get('Path'))
            if raw_program_type and get_setting('settings.content_settings.status_feedback.show_media_type'):
                session_lines.append(f"节目类型：{escape_markdown(raw_program_type)}")
            if get_setting('settings.content_settings.status_feedback.show_overview'):
                overview = item.get('Overview', '')
                if overview: session_lines.append(f"剧情: {escape_markdown(overview[:100] + '...')}")
            if get_setting('settings.content_settings.status_feedback.show_timestamp'):
                session_lines.append(f"时间：{escape_markdown(datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'))}")
            
            buttons = []
            view_button_row = []
            if EMBY_REMOTE_URL and get_setting('settings.content_settings.status_feedback.show_view_on_server_button'):
                item_id, server_id = item.get('Id'), item.get('ServerId')
                if item_id and server_id:
                    item_url = f"{EMBY_REMOTE_URL}/web/index.html#!/item?id={item_id}&serverId={server_id}"
                    view_button_row.append({'text': '➡️ 在服务器中查看', 'url': item_url})
            if view_button_row: buttons.append(view_button_row)
            
            action_button_row = []
            if session_id:
                if get_setting('settings.content_settings.status_feedback.show_terminate_session_button'):
                    action_button_row.append({'text': '⏹️ 停止播放', 'callback_data': f'session_terminate_{session_id}_{user_id}'})
                if get_setting('settings.content_settings.status_feedback.show_send_message_button'):
                    action_button_row.append({'text': '✉️ 发送消息', 'callback_data': f'session_message_{session_id}_{user_id}'})
            if action_button_row: buttons.append(action_button_row)
            
            sessions_data.append({
                'message': "\n".join(session_lines),
                'buttons': buttons if buttons else None,
                'poster_url': media_details.get('poster_url') if get_setting('settings.content_settings.status_feedback.show_poster') else None
            })

        except Exception as e:
            print(f"❌ 处理会话 {session.get('Id')} 时发生错误: {e}")
            traceback.print_exc()
            continue

    print(f"最终返回了 {len(sessions_data)} 条数据。")

    return sessions_data

def terminate_emby_session(session_id, chat_id):
    """停止指定的Emby播放会话。"""
    print(f"🛑 正在尝试停止播放会话: {session_id}")
    if not all([EMBY_SERVER_URL, EMBY_API_KEY, session_id]):
        if chat_id: send_simple_telegram_message("错误：缺少停止播放所需的服务器配置。", chat_id)
        return False
    url = f"{EMBY_SERVER_URL}/Sessions/{session_id}/Playing/Stop"
    params = {'api_key': EMBY_API_KEY}
    response = make_request_with_retry('POST', url, params=params, timeout=10)
    if response:
        print(f"✅ 播放 {session_id} 已成功停止。")
        return True
    else:
        if chat_id: send_simple_telegram_message(f"停止播放会话 {escape_markdown(session_id)} 失败。", chat_id)
        print(f"❌ 停止播放会话 {session_id} 失败。")
        return False

def send_message_to_emby_session(session_id, message, chat_id):
    """向指定的Emby会话发送消息。"""
    print(f"✉️ 正在向会话 {session_id} 发送消息。")
    if not all([EMBY_SERVER_URL, EMBY_API_KEY, session_id]):
        if chat_id: send_simple_telegram_message("错误：缺少发送消息所需的服务器配置。", chat_id)
        return
    url = f"{EMBY_SERVER_URL}/Sessions/{session_id}/Message"
    params = {'api_key': EMBY_API_KEY}
    payload = { "Text": message, "Header": "来自管理员的消息", "TimeoutMs": 15000 }
    response = make_request_with_retry('POST', url, params=params, json=payload, timeout=10)
    if response:
        if chat_id: send_simple_telegram_message("✅ 消息已成功发送。", chat_id)
        print(f"✅ 消息已成功发送给会话 {session_id}。")
    else:
        if chat_id: send_simple_telegram_message(f"向会话 {escape_markdown(session_id)} 发送消息失败。", chat_id)
        print(f"❌ 向会话 {session_id} 发送消息失败。")

def get_resolution_for_item(item_id, user_id=None):
    """获取指定项目的视频分辨率。"""
    print(f"ℹ️ 正在获取项目 {item_id} 的分辨率。")
    request_user_id = user_id or EMBY_USER_ID
    if not request_user_id:
        url = f"{EMBY_SERVER_URL}/Items/{item_id}"
    else:
        url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items/{item_id}"
    params = {'api_key': EMBY_API_KEY, 'Fields': 'MediaSources'}
    response = make_request_with_retry('GET', url, params=params, timeout=10)
    if not response:
        print(f"❌ 获取项目 {item_id} 的媒体源信息失败。")
        return "未知分辨率"
    media_sources = response.json().get('MediaSources', [])
    if not media_sources:
        print(f"❌ 项目 {item_id} 媒体源为空。")
        return "未知分辨率"
    for stream in media_sources[0].get('MediaStreams', []):
        if stream.get('Type') == 'Video':
            width, height = stream.get('Width', 0), stream.get('Height', 0)
            if width and height:
                print(f"✅ 获取到项目 {item_id} 的分辨率: {width}x{height}")
                return f"{width}x{height}"
    print(f"⚠️ 项目 {item_id} 中未找到视频流。")
    return "未知分辨率"

def get_series_season_media_info(series_id):
    """获取剧集各季度的媒体信息（视频/音频规格）。"""
    print(f"ℹ️ 正在获取剧集 {series_id} 的季规格。")
    request_user_id = EMBY_USER_ID
    if not request_user_id: return ["错误：此功能需要配置 Emby User ID"]
    seasons_url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
    seasons_params = {'api_key': EMBY_API_KEY, 'ParentId': series_id, 'IncludeItemTypes': 'Season'}
    seasons_response = make_request_with_retry('GET', seasons_url, params=seasons_params, timeout=10)
    if not seasons_response: return ["查询季度列表失败"]
    seasons = seasons_response.json().get('Items', [])
    if not seasons: return ["未找到任何季度"]
    season_info_lines = []
    for season in sorted(seasons, key=lambda s: s.get('IndexNumber', 0)):
        season_num, season_id = season.get('IndexNumber'), season.get('Id')
        if season_num is None or season_id is None: continue
        print(f"ℹ️ 正在查询第 {season_num} 季 ({season_id}) 的剧集。")
        episodes_url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
        episodes_params = {'api_key': EMBY_API_KEY, 'ParentId': season_id, 'IncludeItemTypes': 'Episode', 'Limit': 1, 'Fields': 'Id'}
        episodes_response = make_request_with_retry('GET', episodes_url, params=episodes_params, timeout=10)
        season_line = f"S{season_num:02d}：\n    规格未知"
        if episodes_response and episodes_response.json().get('Items'):
            first_episode_id = episodes_response.json()['Items'][0].get('Id')
            stream_details = get_media_stream_details(first_episode_id, request_user_id)
            if stream_details:
                formatted_parts = format_stream_details_message(stream_details, is_season_info=True, prefix='series')
                if formatted_parts:
                    escaped_parts = [escape_markdown(part) for part in formatted_parts]
                    season_line = f"S{season_num:02d}：\n" + "\n".join(escaped_parts)
        season_info_lines.append(season_line)
    return season_info_lines if season_info_lines else ["未找到剧集规格信息"]

def get_episode_item_by_number(series_id, season_number, episode_number):
    """根据季号和集号获取剧集项目的Emby Item对象。"""
    print(f"ℹ️ 正在精确查询剧集 {series_id} 的 S{season_number:02d}E{episode_number:02d} 的项目信息。")
    request_user_id = EMBY_USER_ID
    if not all([EMBY_SERVER_URL, EMBY_API_KEY, series_id, request_user_id]):
        return None

    api_endpoint = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
    params = {
        'api_key': EMBY_API_KEY,
        'ParentId': series_id,
        'IncludeItemTypes': 'Episode',
        'Recursive': 'true',
        'Fields': 'Id,ParentIndexNumber,IndexNumber',
        'ParentIndexNumber': season_number,
        'IndexNumber': episode_number
    }
    response = make_request_with_retry('GET', api_endpoint, params=params, timeout=15)
    
    if response and response.json().get('Items'):
        episode_item = response.json()['Items'][0]
        print(f"✅ 精确匹配成功，项目 ID: {episode_item.get('Id')}")
        return episode_item
    else:
        print(f"❌ Emby API 未能找到 S{season_number:02d}E{episode_number:02d}。")
        return None

def get_any_episode_from_season(series_id, season_number):
    """获取指定季中任意一集的信息，用于规格参考。"""
    print(f"ℹ️ 正在查找第 {season_number} 季中的任意一集作为规格参考...")
    request_user_id = EMBY_USER_ID
    if not all([EMBY_SERVER_URL, EMBY_API_KEY, series_id, request_user_id]): return None

    api_endpoint = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
    params = {
        'api_key': EMBY_API_KEY,
        'ParentId': series_id,
        'IncludeItemTypes': 'Episode',
        'Recursive': 'true',
        'Fields': 'Id,ParentIndexNumber',
        'ParentIndexNumber': season_number,
        'Limit': 1
    }
    response = make_request_with_retry('GET', api_endpoint, params=params, timeout=15)
    
    if response and response.json().get('Items'):
        episode_item = response.json()['Items'][0]
        print(f"✅ 找到第 {season_number} 季的参考集，ID: {episode_item.get('Id')}")
        return episode_item
    else:
        print(f"❌ 未能在第 {season_number} 季中找到任何剧集。")
        return None

def _get_latest_episode_info(series_id):
    """获取指定剧集系列的最新一集信息。"""
    print(f"ℹ️ 正在获取剧集 {series_id} 的最新剧集信息。")
    request_user_id = EMBY_USER_ID
    if not all([EMBY_SERVER_URL, EMBY_API_KEY, series_id, request_user_id]): return {}
    api_endpoint = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
    params = {
        'api_key': EMBY_API_KEY, 'ParentId': series_id, 'IncludeItemTypes': 'Episode', 'Recursive': 'true',
        'SortBy': 'ParentIndexNumber,IndexNumber', 'SortOrder': 'Descending', 'Limit': 1,
        'Fields': 'ProviderIds,Path,ServerId,DateCreated,ParentIndexNumber,IndexNumber,SeriesName,SeriesProviderIds,Overview'
    }
    response = make_request_with_retry('GET', api_endpoint, params=params, timeout=15)
    latest_episode = response.json()['Items'][0] if response and response.json().get('Items') else {}
    if latest_episode:
        print(f"✅ 获取到最新剧集: S{latest_episode.get('ParentIndexNumber')}E{latest_episode.get('IndexNumber')}")
    return latest_episode

def send_search_emby_and_format(query, chat_id, user_id, is_group_chat, mention):
    """
    执行Emby搜索并格式化结果。如果Emby直接搜索无果，则尝试通过TMDB进行后备搜索。
    :param query: 搜索关键词
    :param chat_id: 聊天ID
    :param user_id: 用户ID
    :param is_group_chat: 是否为群组聊天
    :param mention: @用户名字符串
    """
    print(f"🔍 用户 {user_id} 发起了 Emby 搜索，查询: {query}")
    original_query = query.strip()
    search_term = original_query
    
    match = re.search(r'(\d{4})$', search_term)
    year_for_filter = match.group(1) if match else None
    if match: 
        search_term = search_term[:match.start()].strip()

    if not search_term:
        send_deletable_telegram_notification("关键词无效！", chat_id=chat_id)
        return

    request_user_id = EMBY_USER_ID
    if not request_user_id:
        send_deletable_telegram_notification("错误：机器人管理员尚未在配置文件中设置 Emby `user_id`。", chat_id=chat_id)
        return

    url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
    params = {
        'api_key': EMBY_API_KEY, 
        'SearchTerm': search_term, 
        'IncludeItemTypes': 'Movie,Series',
        'Recursive': 'true', 
        'Fields': 'ProviderIds,Path,ProductionYear,Name'
    }
    if year_for_filter: 
        params['Years'] = year_for_filter
        
    response = make_request_with_retry('GET', url, params=params, timeout=20)
    results = response.json().get('Items', []) if response else []

    intro_override = None

    if not results:
        print(f"ℹ️ Emby 中未直接找到 '{original_query}'，尝试 TMDB 后备搜索。")
        tmdb_alternatives = search_tmdb_multi(search_term, year_for_filter)
        
        alternative_results = []
        found_emby_ids = set()

        if tmdb_alternatives:
            for alt in tmdb_alternatives:
                alt_title = alt['title']
                alt_params = {
                    'api_key': EMBY_API_KEY, 
                    'SearchTerm': alt_title, 
                    'IncludeItemTypes': 'Movie,Series',
                    'Recursive': 'true', 
                    'Fields': 'ProviderIds,Path,ProductionYear,Name'
                }
                if year_for_filter:
                    alt_params['Years'] = year_for_filter

                alt_response = make_request_with_retry('GET', url, params=alt_params, timeout=10)
                
                if alt_response:
                    emby_items = alt_response.json().get('Items', [])
                    for item in emby_items:
                        if item.get('Name').lower() == alt_title.lower() and item.get('Id') not in found_emby_ids:
                            alternative_results.append(item)
                            found_emby_ids.add(item.get('Id'))
        
        if not alternative_results:
            send_deletable_telegram_notification(f"在 Emby 中找不到与“{escape_markdown(original_query)}”相关的任何内容。", chat_id=chat_id)
            return
        else:
            results = alternative_results
            intro_override = f"未在Emby服务器中找到同名的节目，但为您找到了以“{escape_markdown(search_term)}”为别名的节目："
    
    if not results:
        return

    search_id = str(uuid.uuid4())
    SEARCH_RESULTS_CACHE[search_id] = results
    print(f"✅ 搜索成功，找到 {len(results)} 个结果，缓存 ID: {search_id}")
    
    send_search_results_page(chat_id, search_id, user_id, page=1, intro_message_override=intro_override)

def send_search_results_page(chat_id, search_id, user_id, page=1, message_id=None, intro_message_override=None):
    """
    发送搜索结果的某一页。
    :param chat_id: 聊天ID
    :param search_id: 搜索结果缓存ID
    :param user_id: 用户ID
    :param page: 页码
    :param message_id: 要编辑的消息ID
    :param intro_message_override: 用于覆盖默认介绍语的自定义字符串
    """
    print(f"📄 正在发送搜索结果第 {page} 页，缓存 ID: {search_id}")
    if search_id not in SEARCH_RESULTS_CACHE:
        error_msg = "抱歉，此搜索结果已过期，请重新发起搜索。"
        if message_id: edit_telegram_message(chat_id, message_id, error_msg)
        else: send_deletable_telegram_notification(error_msg, chat_id=chat_id)
        return
    results = SEARCH_RESULTS_CACHE[search_id]
    items_per_page = 10
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    page_items = results[start_index:end_index]
    
    if intro_message_override:
        message_text = intro_message_override
    else:
        message_text = "查询到以下节目，点击名称可查看详情："
        
    buttons = []
    for i, item in enumerate(page_items):
        raw_title = item.get('Name', '未知标题')
        final_year = extract_year_from_path(item.get('Path')) or item.get('ProductionYear') or ''
        title_with_year = f"{raw_title} ({final_year})" if final_year else raw_title
        button_text = f"{i + 1 + start_index}. {title_with_year}"
        if get_setting('settings.content_settings.search_display.show_media_type_in_list'):
            raw_program_type = get_program_type_from_path(item.get('Path'))
            if raw_program_type: button_text += f" | {raw_program_type}"
        buttons.append([{'text': button_text, 'callback_data': f's_detail_{search_id}_{start_index + i}_{user_id}'}])
    
    page_buttons = []
    if page > 1: page_buttons.append({'text': '◀️ 上一页', 'callback_data': f's_page_{search_id}_{page-1}_{user_id}'})
    if end_index < len(results): page_buttons.append({'text': '下一页 ▶️', 'callback_data': f's_page_{search_id}_{page+1}_{user_id}'})
    if page_buttons: buttons.append(page_buttons)
    
    if message_id: edit_telegram_message(chat_id, message_id, message_text, inline_buttons=buttons)
    else: send_deletable_telegram_notification(message_text, chat_id=chat_id, inline_buttons=buttons, delay_seconds=90)

def get_local_episodes_by_season(series_id, user_id=None):
    """返回 {season_num: set(episode_nums)}，跳过 S00 特别篇。"""
    print(f"ℹ️ 正在汇总剧集 {series_id} 的本地分季集号。")
    request_user_id = user_id or EMBY_USER_ID
    if not all([EMBY_SERVER_URL, EMBY_API_KEY, request_user_id, series_id]):
        return {}
    url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
    params = {
        'api_key': EMBY_API_KEY,
        'ParentId': series_id,
        'IncludeItemTypes': 'Episode',
        'Recursive': 'true',
        'Fields': 'ParentIndexNumber,IndexNumber'
    }
    resp = make_request_with_retry('GET', url, params=params, timeout=15)
    if not resp:
        return {}
    mapping = {}
    for ep in resp.json().get('Items', []):
        s = ep.get('ParentIndexNumber')
        e = ep.get('IndexNumber')
        if s is None or e is None:
            continue
        s = int(s); e = int(e)
        if s == 0:
            continue
        mapping.setdefault(s, set()).add(e)
    print(f"✅ 本地分季集号统计完成（共 {len(mapping)} 季）。")
    return mapping


def get_tmdb_season_numbers(series_tmdb_id):
    """返回 TMDB 的季号列表（升序，排除季号 0）。"""
    print(f"ℹ️ 正在查询 TMDB 剧集 {series_tmdb_id} 的季列表。")
    if not TMDB_API_TOKEN or not series_tmdb_id:
        return []
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    url = f"https://api.themoviedb.org/3/tv/{series_tmdb_id}"
    params = {'api_key': TMDB_API_TOKEN, 'language': 'zh-CN'}
    resp = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies)
    if not resp:
        return []
    data = resp.json()
    seasons = data.get('seasons', []) or []
    nums = []
    for s in seasons:
        n = s.get('season_number')
        try:
            if n is not None and int(n) != 0:
                nums.append(int(n))
        except Exception:
            pass
    nums = sorted(set(nums))
    print(f"✅ TMDB 季列表：{nums}")
    return nums

def get_tmdb_season_details(series_tmdb_id, season_number):
    """从TMDB获取指定剧集季度详情，包含：
    - total_episodes: TMDB该季条目数
    - max_episode_number: TMDB该季的最大集号（按 episode_number 最大值）
    - episode_numbers: TMDB该季所有集号列表（升序，去重）
    - is_finale_marked: TMDB最后一集是否标记为 finale
    """
    print(f"ℹ️ 正在查询 TMDB 剧集 {series_tmdb_id} 第 {season_number} 季的详情。")
    if not all([TMDB_API_TOKEN, series_tmdb_id, season_number is not None]):
        return None
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    url = f"https://api.themoviedb.org/3/tv/{series_tmdb_id}/season/{season_number}"
    params = {'api_key': TMDB_API_TOKEN, 'language': 'zh-CN'}
    response = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies)
    if not response:
        return None

    data = response.json()
    episodes = data.get('episodes', [])
    if not episodes:
        print(f"❌ TMDB 未找到第 {season_number} 季的剧集列表。")
        return None

    nums = []
    for ep in episodes:
        n = ep.get('episode_number')
        try:
            if n is not None:
                nums.append(int(n))
        except Exception:
            pass

    max_ep = max(nums) if nums else 0
    is_finale = episodes[-1].get('episode_type') == 'finale'

    print(f"✅ TMDB 第 {season_number} 季：共 {len(episodes)} 条目，最大集号 E{max_ep:02d}。")
    return {
        'total_episodes': len(episodes),
        'max_episode_number': max_ep,
        'episode_numbers': sorted(set(nums)),
        'is_finale_marked': is_finale
    }

def build_seasonwise_progress_and_missing_lines(series_tmdb_id, series_id, latest_season_num, latest_episode_num):
    """
    - 最大季（latest_season_num）：
        * 进度 = TMDB最大集号 − 本地最大集号
        * 缺集 = 在本地最大集号（含）之前，TMDB列出的集号 - 本地已有集号
        * 显示“更新进度：xxx”，及缺集行（如有）
    - 其他季（< 最大季）：
        * 只做“整季缺集检查”，有缺才显示“缺集：Sxx E..”
        * 不显示“已完结”等字样
    返回：已做 MarkdownV2 转义的多行字符串列表
    """
    lines = []
    if not series_tmdb_id or series_id is None or latest_season_num is None:
        return lines

    local_map = get_local_episodes_by_season(series_id, EMBY_USER_ID)
    local_latest = int(latest_season_num)

    tmdb_seasons = [s for s in get_tmdb_season_numbers(series_tmdb_id) if s <= local_latest]
    if not tmdb_seasons:
        tmdb_seasons = sorted([s for s in local_map.keys() if s <= local_latest])

    for s in tmdb_seasons:
        tmdb_info = get_tmdb_season_details(series_tmdb_id, s)
        if not tmdb_info:
            continue

        tmdb_eps = tmdb_info.get('episode_numbers') or []
        tmdb_max = tmdb_info.get('max_episode_number') or (max(tmdb_eps) if tmdb_eps else 0)
        tmdb_set = set(tmdb_eps) if tmdb_eps else set(range(1, tmdb_max + 1))

        local_set = set(local_map.get(s, set()))
        local_max = (int(latest_episode_num) if (s == local_latest and latest_episode_num is not None)
                     else (max(local_set) if local_set else 0))

        if s == local_latest:
            remaining = max(0, int(tmdb_max) - int(local_max))
            if remaining == 0:
                status = "已完结" if tmdb_info.get('is_finale_marked') else "已完结（可能不准确）"
            else:
                status = f"剩余{remaining}集"
            lines.append(escape_markdown(f"更新进度：{status}"))

            if local_max > 0:
                expected = {n for n in tmdb_set if int(n) <= local_max}
                missing = sorted(expected - local_set)
                if missing:
                    head = ", ".join([f"E{int(n):02d}" for n in missing[:10]])
                    suffix = f"…(共{len(missing)}集)" if len(missing) > 10 else ""
                    lines.append(escape_markdown(f"缺集：S{int(s):02d} {head}{suffix}"))
        else:
            missing = sorted(tmdb_set - local_set)
            if missing:
                head = ", ".join([f"E{int(n):02d}" for n in missing[:10]])
                suffix = f"…(共{len(missing)}集)" if len(missing) > 10 else ""
                lines.append(escape_markdown(f"缺集：S{int(s):02d} {head}{suffix}"))

    return lines

def build_progress_lines_for_library_new(item, media_details):
    """
    针对 library.new 事件，生成“逐季缺集 + 最大季进度”行：
    - 仅对剧集相关类型 (Series/Season/Episode) 生效
    - 需要能定位到 series_id 与 series_tmdb_id
    """
    try:
        item_type = item.get('Type')
        if item_type not in ('Series', 'Season', 'Episode'):
            return []

        if item_type == 'Series':
            series_id = item.get('Id')
        else:
            series_id = item.get('SeriesId') or None
        if not series_id:
            return []

        latest_episode = _get_latest_episode_info(series_id)
        if not latest_episode:
            return []

        local_s_num = latest_episode.get('ParentIndexNumber')
        local_e_num = latest_episode.get('IndexNumber')
        if local_s_num is None or local_e_num is None:
            return []

        series_tmdb_id = media_details.get('tmdb_id')
        if not series_tmdb_id:
            request_user_id = EMBY_USER_ID
            if request_user_id:
                series_url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items/{series_id}"
                params = {'api_key': EMBY_API_KEY, 'Fields': 'ProviderIds'}
                resp = make_request_with_retry('GET', series_url, params=params, timeout=10)
                if resp:
                    series_tmdb_id = (resp.json().get('ProviderIds') or {}).get('Tmdb')

        if not series_tmdb_id:
            return []

        return build_seasonwise_progress_and_missing_lines(series_tmdb_id, series_id, local_s_num, local_e_num)
    except Exception as e:
        print(f"⚠️ 生成新增通知进度/缺集时异常：{e}")
        return []

def get_media_stream_details(item_id, user_id=None):
    """获取指定项目的媒体流信息（视频、音频、字幕）。"""
    print(f"ℹ️ 正在获取项目 {item_id} 的媒体流信息。")
    request_user_id = user_id or EMBY_USER_ID
    if not all([EMBY_SERVER_URL, EMBY_API_KEY, request_user_id]): return None

    url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items/{item_id}"
    params = {'api_key': EMBY_API_KEY, 'Fields': 'MediaSources'}
    response = make_request_with_retry('GET', url, params=params, timeout=10)

    if not response: return None
    item_data = response.json()
    media_sources = item_data.get('MediaSources', [])
    if not media_sources: return None
    print(f"✅ 获取到项目 {item_id} 的媒体流信息。")

    video_info, audio_info_list, subtitle_info_list = {}, [], []
    for stream in media_sources[0].get('MediaStreams', []):
        if stream.get('Type') == 'Video' and not video_info:
            bitrate_mbps = stream.get('BitRate', 0) / 1_000_000
            video_info = {
                'title': stream.get('Codec', '未知').upper(),
                'resolution': f"{stream.get('Width', 0)}x{stream.get('Height', 0)}",
                'bitrate': f"{bitrate_mbps:.1f}" if bitrate_mbps > 0 else "未知",
                'video_range': stream.get('VideoRange', '')
            }
        elif stream.get('Type') == 'Audio':
            audio_info_list.append({
                'language': stream.get('Language', '未知'), 'codec': stream.get('Codec', '未知'),
                'layout': stream.get('ChannelLayout', '')
            })
        elif stream.get('Type') == 'Subtitle':
            subtitle_info_list.append({
                'language': stream.get('Language', '未知'),
                'codec': stream.get('Codec', '未知').upper()
            })
            
    return {'video_info': video_info, 'audio_info': audio_info_list, 'subtitle_info': subtitle_info_list} if video_info or audio_info_list or subtitle_info_list else None

def format_stream_details_message(stream_details, is_season_info=False, prefix='movie'):
    """格式化媒体流详细信息为消息文本。"""
    if not stream_details: return []

    message_parts = []

    video_setting_path_map = {
        'movie': 'settings.content_settings.search_display.movie.show_video_spec',
        'series': 'settings.content_settings.search_display.series.season_specs.show_video_spec',
        'new_library_notification': 'settings.content_settings.new_library_notification.show_video_spec',
        'playback_action': 'settings.content_settings.playback_action.show_video_spec'
    }
    video_setting_path = video_setting_path_map.get(prefix)
    
    video_info = stream_details.get('video_info')
    if video_info and get_setting(video_setting_path):
        parts = [video_info.get('title')]
        if video_info.get('resolution') != '0x0':
            parts.append(video_info.get('resolution'))
        if video_info.get('bitrate') and video_info.get('bitrate') != '未知':
            parts.append(f"{video_info.get('bitrate')}Mbps")
        if video_info.get('video_range'):
            parts.append(video_info.get('video_range'))

        parts = [p for p in parts if p]
        if parts:
            video_line = ' '.join(parts)
            label = "视频规格：" if prefix == 'new_library_notification' or prefix == 'playback_action' else "视频："
            indent = "    " if is_season_info else ""
            message_parts.append(f"{indent}{label}{video_line}")

    audio_setting_path_map = {
        'movie': 'settings.content_settings.search_display.movie.show_audio_spec',
        'series': 'settings.content_settings.search_display.series.season_specs.show_audio_spec',
        'new_library_notification': 'settings.content_settings.new_library_notification.show_audio_spec',
        'playback_action': 'settings.content_settings.playback_action.show_audio_spec'
    }
    audio_setting_path = audio_setting_path_map.get(prefix)
    
    audio_info_list = stream_details.get('audio_info')
    if audio_info_list and get_setting(audio_setting_path):
        audio_lines = []
        seen_tracks = set()
        for a_info in audio_info_list:
            lang_code = a_info.get('language', 'und').lower()
            lang_display = LANG_MAP.get(lang_code, {}).get('zh', lang_code.capitalize())
            audio_parts = [p for p in [lang_display if lang_display != '未知' else None, a_info.get('codec', '').upper() if a_info.get('codec', '') != '未知' else None, a_info.get('layout', '')] if p]
            if audio_parts:
                track_str = ' '.join(audio_parts)
                if track_str not in seen_tracks:
                    audio_lines.append(track_str)
                    seen_tracks.add(track_str)
        
        if audio_lines:
            full_audio_str = "、".join(audio_lines)
            label = "音频规格：" if prefix == 'new_library_notification' or prefix == 'playback_action' else "音频："
            indent = "    " if is_season_info else ""
            message_parts.append(f"{indent}{label}{full_audio_str}")
            
    subtitle_setting_path_map = {
        'movie': 'settings.content_settings.search_display.movie.show_subtitle_spec',
        'series': 'settings.content_settings.search_display.series.season_specs.show_subtitle_spec',
        'new_library_notification': 'settings.content_settings.new_library_notification.show_subtitle_spec',
        'playback_action': 'settings.content_settings.playback_action.show_subtitle_spec'
    }
    subtitle_setting_path = subtitle_setting_path_map.get(prefix)

    subtitle_info_list = stream_details.get('subtitle_info')
    if subtitle_info_list and get_setting(subtitle_setting_path):
        
        priority_map = {
            'chi': 0, 'zho': 0,
            'eng': 1,
            'jpn': 2,
            'kor': 3
        }
        DEFAULT_PRIORITY = 99

        sorted_subtitles = sorted(
            subtitle_info_list,
            key=lambda s: priority_map.get(s.get('language', 'und').lower(), DEFAULT_PRIORITY)
        )

        subtitle_lines = []
        seen_tracks = set()
        total_sub_count = len(sorted_subtitles)
        max_display_subs = 5

        for s_info in sorted_subtitles[:max_display_subs]:
            lang_code = s_info.get('language', 'und').lower()
            lang_display = LANG_MAP.get(lang_code, {}).get('zh', lang_code.capitalize())
            
            sub_parts = [p for p in [lang_display if lang_display != '未知' else None, s_info.get('codec')] if p]
            if sub_parts:
                track_str = ' '.join(sub_parts)
                if track_str not in seen_tracks:
                    subtitle_lines.append(track_str)
                    seen_tracks.add(track_str)

        if subtitle_lines:
            full_subtitle_str = "、".join(subtitle_lines)

            if total_sub_count > max_display_subs:
                full_subtitle_str += f" 等共计{total_sub_count}个字幕"

            label = "字幕规格：" if prefix in ['new_library_notification', 'playback_action'] else "字幕："
            indent = "    " if is_season_info else ""
            message_parts.append(f"{indent}{label}{full_subtitle_str}")
            
    return message_parts

def parse_season_selection(text: str):
    """
    解析季选择输入，如: "S01 S03 S05" 或 "01 3 5"
    返回去重升序的季号列表 [1,3,5]
    """
    if not text:
        return []
    tokens = re.split(r'[,\s，、]+', text.strip())
    seasons = set()
    for t in tokens:
        if not t:
            continue
        m = re.fullmatch(r'(?:S|s)?\s*(\d{1,2})', t.strip())
        if m:
            try:
                n = int(m.group(1))
                if 0 <= n < 200:
                    seasons.add(n)
            except Exception:
                pass
    return sorted(seasons)


def parse_episode_selection(s: str):
    """
    解析用户输入的季/集选择字符串，返回 {season_num: set(episode_nums)}。
    支持示例：
      - S01E03
      - E11（继承最近一次出现的季；若无则默认S01）
      - S02E03-E06（范围）
      - 混合输入：S01E03 E11 S02E03-E06 E10
    允许用空格、英文/中文逗号、顿号分隔。
    """
    if not s:
        return {}
    tokens = re.split(r'[,\s，、]+', s.strip())
    ctx_season = None
    mapping = {}
    for tok in tokens:
        if not tok:
            continue
        m = re.match(r'^(?:S(\d{1,2}))?E(\d{1,3})(?:-E?(\d{1,3}))?$', tok, re.IGNORECASE)
        if not m:
            m2 = re.match(r'^S(\d{1,2})$', tok, re.IGNORECASE)
            if m2:
                ctx_season = int(m2.group(1))
            continue

        s1, e1, e2 = m.groups()
        if s1:
            ctx_season = int(s1)
        if ctx_season is None:
            ctx_season = 1

        e1 = int(e1)
        if e2:
            e2 = int(e2)
            r = range(min(e1, e2), max(e1, e2) + 1)
            mapping.setdefault(ctx_season, set()).update(r)
        else:
            mapping.setdefault(ctx_season, set()).add(e1)
    return mapping

def get_emby_libraries():
    """获取Emby中所有的媒体库（根文件夹）。"""
    print("🗂️ 正在获取 Emby 媒体库列表...")
    if not all([EMBY_SERVER_URL, EMBY_API_KEY]):
        return None, "Emby服务器配置不完整。"
    
    url = f"{EMBY_SERVER_URL}/Library/VirtualFolders"
    params = {'api_key': EMBY_API_KEY}
    response = make_request_with_retry('GET', url, params=params, timeout=10)
    
    if response:
        try:
            libraries = response.json()
            lib_info = [{'name': lib.get('Name'), 'id': lib.get('ItemId')} 
                        for lib in libraries if lib.get('Name') and lib.get('ItemId')]
            
            if not lib_info:
                return None, "未能找到任何媒体库。"
            
            print(f"✅ 成功获取到 {len(lib_info)} 个媒体库。")
            return lib_info, None
        except (json.JSONDecodeError, KeyError) as e:
            return None, f"解析媒体库列表失败: {e}"
    
    return None, "从Emby API获取媒体库列表失败。"

def get_series_item_basic(series_id: str):
    """获取剧集基本信息（Name/Year/Path），失败返回 None。"""
    try:
        url = f"{EMBY_SERVER_URL}/Users/{EMBY_USER_ID}/Items/{series_id}"
        params = {'api_key': EMBY_API_KEY, 'Fields': 'Path,Name,ProductionYear'}
        resp = make_request_with_retry('GET', url, params=params, timeout=10)
        return resp.json() if resp else None
    except Exception:
        return None

def get_series_season_id_map(series_id: str):
    """返回 {season_number:int -> season_id:str}；跳过 S00。"""
    url = f"{EMBY_SERVER_URL}/Users/{EMBY_USER_ID}/Items"
    params = {'api_key': EMBY_API_KEY, 'ParentId': series_id, 'IncludeItemTypes': 'Season'}
    resp = make_request_with_retry('GET', url, params=params, timeout=15)
    if not resp:
        return {}
    mapping = {}
    for s in resp.json().get('Items', []):
        sn = s.get('IndexNumber')
        sid = s.get('Id')
        if sn is None or sid is None:
            continue
        sn = int(sn)
        if sn == 0:
            continue
        mapping[sn] = sid
    return mapping


def delete_emby_seasons(series_id: str, seasons: list[int]):
    """从 Emby 删除指定季，返回日志字符串。"""
    season_map = get_series_season_id_map(series_id)
    logs = []
    for sn in seasons:
        sid = season_map.get(sn)
        if not sid:
            logs.append(f"🟡 未找到 Emby 季 S{sn:02d}")
            continue
        msg = delete_emby_item(sid, f"S{sn:02d}")
        logs.append(msg)
    return "\n".join(logs) if logs else "未删除任何季。"


def delete_emby_episodes(series_id: str, season_to_eps: dict[int, list[int]]):
    """从 Emby 删除指定集，返回日志字符串。"""
    logs = []
    season_map = get_series_season_id_map(series_id)
    for sn, eps in sorted(season_to_eps.items()):
        sid = season_map.get(sn)
        if not sid:
            logs.append(f"🟡 未找到 Emby 季 S{sn:02d}")
            continue
        url = f"{EMBY_SERVER_URL}/Users/{EMBY_USER_ID}/Items"
        params = {'api_key': EMBY_API_KEY, 'ParentId': sid, 'IncludeItemTypes': 'Episode', 'Fields': 'IndexNumber,Name'}
        resp = make_request_with_retry('GET', url, params=params, timeout=15)
        if not resp:
            logs.append(f"❌ 拉取 Emby 季 S{sn:02d} 的集列表失败")
            continue
        ep_map = {}
        for ep in resp.json().get('Items', []):
            n = ep.get('IndexNumber')
            if n is not None:
                ep_map[int(n)] = ep.get('Id')
        for e in eps:
            eid = ep_map.get(e)
            if not eid:
                logs.append(f"🟡 未找到 Emby 项 S{sn:02d}E{e:02d}")
                continue
            msg = delete_emby_item(eid, f"S{sn:02d}E{e:02d}")
            logs.append(msg)
    return "\n".join(logs) if logs else "未删除任何集。"


def _series_base_dirs(series_path: str):
    """根据 series_path 推导本地与网盘的剧集根目录（都可能为 None）。"""
    if not series_path:
        return None, None
    base = series_path
    if os.path.splitext(base)[1]:
        base = os.path.dirname(base)
    local_root = base if MEDIA_BASE_PATH and base.startswith(MEDIA_BASE_PATH) else None
    cloud_root = None
    if MEDIA_BASE_PATH and MEDIA_CLOUD_PATH and local_root:
        rel = os.path.relpath(local_root, MEDIA_BASE_PATH)
        cloud_root = os.path.join(MEDIA_CLOUD_PATH, rel)
    return local_root, cloud_root


def delete_local_cloud_seasons(series_path: str, seasons: list[int], *, delete_local=False, delete_cloud=False):
    """删除剧集目录下指定季文件夹（Season 1 / Season 01），返回日志。"""
    if not delete_local and not delete_cloud:
        return "未指定删除目标。"
    local_root, cloud_root = _series_base_dirs(series_path)
    logs = []

    def _do_dir(root, label):
        if not root:
            logs.append(f"🟡 {label} 根目录未知或未配置。")
            return
        for sn in seasons:
            candidates = [os.path.join(root, f"Season {sn}"), os.path.join(root, f"Season {sn:02d}")]
            deleted_any = False
            for d in candidates:
                if os.path.isdir(d):
                    try:
                        shutil.rmtree(d)
                        logs.append(f"✅ 删除{label}目录: {d}")
                        deleted_any = True
                    except Exception as e:
                        logs.append(f"❌ 删除{label}目录失败: {d} | {e}")
            if not deleted_any:
                logs.append(f"🟡 未找到{label}季目录: S{sn:02d}")
    if delete_local:
        _do_dir(local_root, "本地")
    if delete_cloud:
        _do_dir(cloud_root, "网盘")
    return "\n".join(logs) if logs else "未执行任何删除操作。"


def delete_local_cloud_episodes(series_path: str, season_to_eps: dict[int, list[int]], *, delete_local=False, delete_cloud=False):
    """
    删除剧集目录下指定季/集的文件。
    匹配模式支持: *S{ss}E{ee}*，其中 ee = 2位 或 3位
    Season 目录候选: Season 1 / Season 01
    """
    if not delete_local and not delete_cloud:
        return "未指定删除目标。"
    import glob
    local_root, cloud_root = _series_base_dirs(series_path)
    logs = []

    def _do_files(root, label):
        if not root:
            logs.append(f"🟡 {label} 根目录未知或未配置。")
            return
        for sn, eps in sorted(season_to_eps.items()):
            season_dirs = [os.path.join(root, f"Season {sn}"), os.path.join(root, f"Season {sn:02d}")]
            found_dir = None
            for sd in season_dirs:
                if os.path.isdir(sd):
                    found_dir = sd
                    break
            if not found_dir:
                logs.append(f"🟡 未找到{label}季目录: S{sn:02d}")
                continue

            for e in eps:
                pattens = [
                    f"*S{sn:02d}E{e:02d}*",
                    f"*S{sn:02d}E{e:03d}*",
                    f"*s{sn:02d}e{e:02d}*",
                    f"*s{sn:02d}e{e:03d}*",
                ]
                matched = set()
                for p in pattens:
                    for path in glob.glob(os.path.join(found_dir, p)):
                        matched.add(path)

                if not matched:
                    logs.append(f"🟡 未找到{label}文件: S{sn:02d}E{e:02d}")
                    continue

                for fp in sorted(matched):
                    try:
                        if os.path.isdir(fp):
                            shutil.rmtree(fp)
                        else:
                            os.remove(fp)
                        logs.append(f"✅ 已删除{label}文件: {fp}")
                    except Exception as ex:
                        logs.append(f"❌ 删除{label}文件失败: {fp} | {ex}")

    if delete_local:
        _do_files(local_root, "本地")
    if delete_cloud:
        _do_files(cloud_root, "网盘")

    return "\n".join(logs) if logs else "未执行任何删除操作。"

def send_search_detail(chat_id, search_id, item_index, user_id):
    """
    发送搜索结果的详细信息。
    :param chat_id: 聊天ID
    :param search_id: 搜索结果缓存ID
    :param item_index: 项目在缓存列表中的索引
    :param user_id: 用户ID
    """
    print(f"ℹ️ 正在发送搜索结果详情，缓存 ID: {search_id}, 索引: {item_index}")
    if search_id not in SEARCH_RESULTS_CACHE or item_index >= len(SEARCH_RESULTS_CACHE[search_id]):
        send_deletable_telegram_notification("抱歉，此搜索结果已过期或无效。", chat_id=chat_id)
        return
    item_from_cache = SEARCH_RESULTS_CACHE[search_id][item_index]
    item_id = item_from_cache.get('Id')
    request_user_id = EMBY_USER_ID
    if not request_user_id:
        send_deletable_telegram_notification("错误：机器人管理员尚未设置 Emby `user_id`。", chat_id=chat_id)
        return
    full_item_url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items/{item_id}"
    params = {'api_key': EMBY_API_KEY, 'Fields': 'ProviderIds,Path,Overview,ProductionYear,ServerId,DateCreated'}
    response = make_request_with_retry('GET', full_item_url, params=params, timeout=10)
    if not response:
        send_deletable_telegram_notification("获取详细信息失败。", chat_id=chat_id)
        return
    item = response.json()
    item_type, raw_title, raw_overview = item.get('Type'), item.get('Name', '未知标题'), item.get('Overview', '暂无剧情简介')
    final_year = extract_year_from_path(item.get('Path')) or item.get('ProductionYear') or ''
    media_details = get_media_details(item, request_user_id)
    poster_url, tmdb_link = media_details.get('poster_url'), media_details.get('tmdb_link', '')
    message_parts = []
    prefix = 'movie' if item_type == 'Movie' else 'series'
    title_with_year = f"{raw_title} ({final_year})" if final_year else raw_title
    if tmdb_link and get_setting(f'settings.content_settings.search_display.{prefix}.title_has_tmdb_link'):
        message_parts.append(f"名称：[{escape_markdown(title_with_year)}]({tmdb_link})")
    else:
        message_parts.append(f"名称：*{escape_markdown(title_with_year)}*")
    if get_setting(f'settings.content_settings.search_display.{prefix}.show_type'):
        item_type_cn = "电影" if item_type == 'Movie' else "剧集"
        message_parts.append(f"类型：{escape_markdown(item_type_cn)}")
    raw_program_type = get_program_type_from_path(item.get('Path'))
    if raw_program_type and get_setting(f'settings.content_settings.search_display.{prefix}.show_category'):
        message_parts.append(f"分类：{escape_markdown(raw_program_type)}")
    if raw_overview and get_setting(f'settings.content_settings.search_display.{prefix}.show_overview'):
        overview_text = raw_overview[:150] + "..." if len(raw_overview) > 150 else raw_overview
        message_parts.append(f"剧情：{escape_markdown(overview_text)}")

    if item_type == 'Movie':
        stream_details = get_media_stream_details(item_id, request_user_id)
        formatted_parts = format_stream_details_message(stream_details, prefix='movie')
        if formatted_parts: message_parts.extend([escape_markdown(part) for part in formatted_parts])
        if get_setting('settings.content_settings.search_display.movie.show_added_time'):
            date_created_str = item.get('DateCreated')
            message_parts.append(f"入库时间：{escape_markdown(format_date(date_created_str))}")
    elif item_type == 'Series':
        season_info_list = get_series_season_media_info(item_id)
        if season_info_list:
            message_parts.append("各季规格：\n" + "\n".join([f"    {info}" for info in season_info_list]))
        latest_episode = _get_latest_episode_info(item_id)
        if latest_episode:
            message_parts.append("\u200b")
            if get_setting('settings.content_settings.search_display.series.update_progress.show_latest_episode'):
                s_num, e_num = latest_episode.get('ParentIndexNumber'), latest_episode.get('IndexNumber')
                update_info_raw = f"第 {s_num} 季 第 {e_num} 集" if s_num is not None and e_num is not None else "信息不完整"
                episode_media_details = get_media_details(latest_episode, EMBY_USER_ID)
                episode_tmdb_link = episode_media_details.get('tmdb_link')
                if episode_tmdb_link and get_setting('settings.content_settings.search_display.series.update_progress.latest_episode_has_tmdb_link'):
                    message_parts.append(f"已更新至：[{escape_markdown(update_info_raw)}]({episode_tmdb_link})")
                else:
                    message_parts.append(f"已更新至：{escape_markdown(update_info_raw)}")
            if get_setting('settings.content_settings.search_display.series.update_progress.show_overview'):
                episode_overview = latest_episode.get('Overview')
                if episode_overview:
                    overview_text = episode_overview[:100] + "..." if len(episode_overview) > 100 else episode_overview
                    message_parts.append(f"剧情：{escape_markdown(overview_text)}")
            if get_setting('settings.content_settings.search_display.series.update_progress.show_added_time'):
                message_parts.append(f"入库时间：{escape_markdown(format_date(latest_episode.get('DateCreated')))}")

            if get_setting('settings.content_settings.search_display.series.update_progress.show_progress_status'):
                series_tmdb_id = media_details.get('tmdb_id')
                local_s_num = latest_episode.get('ParentIndexNumber')
                local_e_num = latest_episode.get('IndexNumber')
                lines = build_seasonwise_progress_and_missing_lines(series_tmdb_id, item_id, local_s_num, local_e_num)
                if lines:
                    message_parts.extend(lines)

    final_poster_url = poster_url if poster_url and get_setting(f'settings.content_settings.search_display.{prefix}.show_poster') else None
    buttons = []
    if get_setting(f'settings.content_settings.search_display.{prefix}.show_view_on_server_button') and EMBY_REMOTE_URL:
        server_id = item.get('ServerId')
        if item_id and server_id:
            item_url = f"{EMBY_REMOTE_URL}/web/index.html#!/item?id={item_id}&serverId={server_id}"
            buttons.append([{'text': '➡️ 在服务器中查看', 'url': item_url}])
    send_deletable_telegram_notification(
        "\n".join(filter(None, message_parts)),
        photo_url=final_poster_url, chat_id=chat_id,
        inline_buttons=buttons if buttons else None,
        delay_seconds=90
    )

def send_settings_menu(chat_id, user_id, message_id=None, menu_key='root'):
    """
    发送或编辑设置菜单。
    :param chat_id: 聊天ID
    :param user_id: 用户ID
    :param message_id: 要编辑的消息ID，如果为None则发送新消息
    :param menu_key: 当前菜单的键
    """
    print(f"⚙️ 正在向用户 {user_id} 发送设置菜单，菜单键: {menu_key}")
    node = SETTINGS_MENU_STRUCTURE.get(menu_key, SETTINGS_MENU_STRUCTURE['root'])

    def get_breadcrumb_path(key):
        path_parts = []
        current_key = key
        while current_key is not None:
            current_node = SETTINGS_MENU_STRUCTURE.get(current_key)
            if current_node:
                path_parts.append(current_node['label'])
                current_key = current_node.get('parent')
            else:
                break
        return " >> ".join(reversed(path_parts))

    breadcrumb_title = get_breadcrumb_path(menu_key)
    text_parts = [f"*{escape_markdown(breadcrumb_title)}*"]
    
    if menu_key == 'root':
        text_parts.append("管理机器人的各项功能与通知！")
        
    buttons = []
    if menu_key == 'ip_api_selection':
        text_parts.append("请选择一个IP地理位置查询服务接口。")
        current_provider = get_setting('settings.ip_api_provider') or 'baidu'
        for child_key in node['children']:
            child_node = SETTINGS_MENU_STRUCTURE[child_key]
            api_value = child_node['config_value']
            is_selected = (api_value == current_provider)
            status_icon = "✅" if is_selected else " "
            buttons.append([{'text': f"{status_icon} {child_node['label']}", 'callback_data': f'set_ipapi_{api_value}_{user_id}'}])
    elif 'children' in node:
        for child_key in node['children']:
            child_node = SETTINGS_MENU_STRUCTURE[child_key]
            if 'children' in child_node:
                buttons.append([{'text': f"➡️ {child_node['label']}", 'callback_data': f'n_{child_key}_{user_id}'}])
            elif 'config_path' in child_node:
                is_enabled = get_setting(child_node['config_path'])
                status_icon = "✅" if is_enabled else "❌"
                item_index = child_node.get('index')
                if item_index is not None:
                    callback_data = f"t_{item_index}_{user_id}"
                    buttons.append([{'text': f"{status_icon} {child_node['label']}", 'callback_data': callback_data}])
    
    nav_buttons = []
    if 'parent' in node and node['parent'] is not None:
        nav_buttons.append({'text': '◀️ 返回上一级', 'callback_data': f'n_{node["parent"]}_{user_id}'})
    nav_buttons.append({'text': '☑️ 完成', 'callback_data': f'c_menu_{user_id}'})
    buttons.append(nav_buttons)
    
    message_text = "\n".join(text_parts)
    if message_id:
        edit_telegram_message(chat_id, message_id, message_text, inline_buttons=buttons)
    else:
        send_telegram_notification(text=message_text, chat_id=chat_id, inline_buttons=buttons)

def post_update_result_to_telegram(*, chat_id: int, message_id: int, callback_message: dict, escaped_result: str, delete_after: int = 180):
    """
    更新结果的统一投递逻辑：
    - 尝试“编辑原消息”展示结果（短内容）或“编辑成摘要”（长内容）
    - 若编辑失败或内容太长，再发送一条独立的可自动删除文本
    - 最终把原消息设置为延时删除
    """
    used_original = False
    is_photo_card = 'photo' in (callback_message or {})

    try:
        if len(escaped_result) < 900:
            if is_photo_card:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageCaption"
                payload = {
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'caption': escaped_result,
                    'parse_mode': 'MarkdownV2',
                    'reply_markup': json.dumps({'inline_keyboard': []})
                }
                resp = make_request_with_retry('POST', url, json=payload, timeout=10)
                used_original = bool(resp)
            else:
                resp = edit_telegram_message(chat_id, message_id, escaped_result, inline_buttons=[])
                used_original = bool(resp)
        else:
            summary_message = "✅ 更新成功！\n详细日志见下方新消息。"
            if is_photo_card:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageCaption"
                payload = {
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'caption': escape_markdown(summary_message),
                    'parse_mode': 'MarkdownV2',
                    'reply_markup': json.dumps({'inline_keyboard': []})
                }
                make_request_with_retry('POST', url, json=payload, timeout=10)
            else:
                edit_telegram_message(chat_id, message_id, escape_markdown(summary_message), inline_buttons=[])

            send_deletable_telegram_notification(text=escaped_result, chat_id=chat_id, delay_seconds=delete_after)
            used_original = True
    except Exception as e:
        print(f"⚠️ 投递更新结果时发生异常，将走独立文本兜底：{e}")

    if not used_original:
        send_deletable_telegram_notification(text=escaped_result, chat_id=chat_id, delay_seconds=delete_after)

    if message_id:
        delete_user_message_later(chat_id, message_id, delete_after)

def handle_callback_query(callback_query):
    """
    处理内联按钮回调：
    - 增加多层级管理菜单
    - 增加修改用户名功能
    - 增加退出按钮
    """
    global DELETION_TASK_CACHE, user_context, UPDATE_PATH_CACHE

    query_id = callback_query['id']
    data = callback_query.get('data')
    print(f"📞 收到回调查询。ID: {query_id}, 数据: {data}")
    if not data:
        answer_callback_query(query_id)
        return

    message = callback_query.get('message', {}) or {}
    clicker_id = callback_query['from']['id']
    chat_id = message.get('chat', {}).get('id')
    message_id = message.get('message_id')

    if data.startswith('set_ipapi_'):
        if not is_super_admin(clicker_id):
            answer_callback_query(query_id, text="抱歉，此操作仅对超级管理员开放。", show_alert=True)
            return
        
        try:
            params_str = data[len('set_ipapi_'):]
            provider, initiator_id_str = params_str.split('_', 1)

            if str(clicker_id) != initiator_id_str:
                answer_callback_query(query_id, text="交互由其他用户发起，您无法操作！", show_alert=True)
                return

            set_setting('settings.ip_api_provider', provider)
            save_config()
            
            provider_map = {
                'baidu': '百度 API', 'ip138': 'IP138 API', 'pconline': '太平洋电脑 API',
                'vore': 'Vore API', 'ipapi': 'IP-API.com'
            }
            provider_name = provider_map.get(provider, provider)
            
            answer_callback_query(query_id, text=f"API 已切换至: {provider_name}")
            send_settings_menu(chat_id, int(initiator_id_str), message_id, menu_key='ip_api_selection')
        except ValueError:
            answer_callback_query(query_id, text="回调参数错误。", show_alert=True)
        return

    if data.startswith('mdc_'):
        try:
            _, sub, shortid = data.split('_', 2)
        except ValueError:
            answer_callback_query(query_id, text="无效的操作。", show_alert=True)
            return

        task = DELETION_TASK_CACHE.get(shortid)
        if not task:
            answer_callback_query(query_id, text="此操作已过期，请重新选择。", show_alert=True)
            return
        if task.get('initiator_id') != clicker_id:
            answer_callback_query(query_id, text="交互由其他用户发起，您无法操作！", show_alert=True)
            return

        answer_callback_query(query_id, text="正在执行删除...", show_alert=False)

        def _paths_for_series(_series_id):
            full_item_url = f"{EMBY_SERVER_URL}/Users/{EMBY_USER_ID}/Items/{_series_id}"
            params = {'api_key': EMBY_API_KEY, 'Fields': 'Path,Name,ProductionYear'}
            resp = make_request_with_retry('GET', full_item_url, params=params, timeout=10)
            if not resp:
                return None, None, "❌ 获取节目路径失败。"
            item = resp.json()
            base_path = item.get('Path') or ""
            if base_path and os.path.splitext(base_path)[1]:
                base_path = os.path.dirname(base_path)

            media_base = get_setting('settings.media_base_path') or MEDIA_BASE_PATH
            media_cloud = get_setting('settings.media_cloud_path') or MEDIA_CLOUD_PATH

            rel = None
            if media_base and base_path and base_path.startswith(media_base):
                rel = os.path.relpath(base_path, media_base)
            cloud_dir = os.path.join(media_cloud, rel) if (media_cloud and rel) else None
            return base_path, cloud_dir, None

        def _delete_season_dirs(base_dir, cloud_dir, seasons, *, do_local=False, do_cloud=False):
            logs = []
            cand_names = lambda n: [f"Season {int(n)}", f"Season {int(n):02d}"]
            for s in seasons:
                for name in cand_names(s):
                    if do_local and base_dir:
                        p = os.path.join(base_dir, name)
                        if os.path.isdir(p):
                            try:
                                shutil.rmtree(p); logs.append(f"✅ 本地已删: {p}")
                            except Exception as e:
                                logs.append(f"❌ 本地删除失败: {p} ({e})")
                    if do_cloud and cloud_dir:
                        p = os.path.join(cloud_dir, name)
                        if os.path.isdir(p):
                            try:
                                shutil.rmtree(p); logs.append(f"✅ 网盘已删: {p}")
                            except Exception as e:
                                logs.append(f"❌ 网盘删除失败: {p} ({e})")
            return logs

        def _delete_episodes_files(base_dir, cloud_dir, mapping, *, do_local=False, do_cloud=False):
            logs = []
            def cand_names(n): return [f"Season {int(n)}", f"Season {int(n):02d}"]
            for s, eps in mapping.items():
                eps = sorted(set(int(e) for e in eps))
                for sd_name in cand_names(s):
                    if do_local and base_dir:
                        sd = os.path.join(base_dir, sd_name)
                        if os.path.isdir(sd):
                            for fn in os.listdir(sd):
                                low = fn.lower()
                                for e in eps:
                                    p2 = re.compile(rf'(?i)S{int(s):02d}E{int(e):02d}(?!\d)')
                                    p3 = re.compile(rf'(?i)S{int(s):02d}E{int(e):03d}(?!\d)')
                                    if p2.search(low) or p3.search(low):
                                        try:
                                            os.remove(os.path.join(sd, fn))
                                            logs.append(f"✅ 本地已删: {sd}/{fn}")
                                        except IsADirectoryError:
                                            try:
                                                shutil.rmtree(os.path.join(sd, fn))
                                                logs.append(f"✅ 本地已删目录: {sd}/{fn}")
                                            except Exception as ex:
                                                logs.append(f"❌ 本地删除失败: {sd}/{fn} ({ex})")
                                        except Exception as ex:
                                            logs.append(f"❌ 本地删除失败: {sd}/{fn} ({ex})")
                    if do_cloud and cloud_dir:
                        sd = os.path.join(cloud_dir, sd_name)
                        if os.path.isdir(sd):
                            for fn in os.listdir(sd):
                                low = fn.lower()
                                for e in eps:
                                    p2 = re.compile(rf'(?i)S{int(s):02d}E{int(e):02d}(?!\d)')
                                    p3 = re.compile(rf'(?i)S{int(s):02d}E{int(e):03d}(?!\d)')
                                    if p2.search(low) or p3.search(low):
                                        try:
                                            os.remove(os.path.join(sd, fn))
                                            logs.append(f"✅ 网盘已删: {sd}/{fn}")
                                        except IsADirectoryError:
                                            try:
                                                shutil.rmtree(os.path.join(sd, fn))
                                                logs.append(f"✅ 网盘已删目录: {sd}/{fn}")
                                            except Exception as ex:
                                                logs.append(f"❌ 网盘删除失败: {sd}/{fn} ({ex})")
                                        except Exception as ex:
                                            logs.append(f"❌ 网盘删除失败: {sd}/{fn} ({ex})")
            return logs

        def _emby_delete_for_task(_task):
            t = _task['type']
            series_id = _task['series_id']
            request_user_id = EMBY_USER_ID
            if not request_user_id:
                return ["❌ 未配置 EMBY_USER_ID，无法定位条目。"]

            items_api = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
            logs = []

            if t == 'seasons':
                params = {'api_key': EMBY_API_KEY, 'ParentId': series_id, 'IncludeItemTypes': 'Season',
                            'Fields': 'IndexNumber,Name'}
                resp = make_request_with_retry('GET', items_api, params=params, timeout=15)
                seasons = resp.json().get('Items', []) if resp else []
                target = [s for s in seasons if (s.get('IndexNumber') in _task['seasons'])]
                if not target:
                    return ["ℹ️ Emby 中未找到匹配的季条目。"]
                for it in target:
                    name = it.get('Name') or f"Season {it.get('IndexNumber')}"
                    res = delete_emby_item(it.get('Id'), name)
                    logs.append(res)
                return logs

            if t == 'episodes':
                params = {'api_key': EMBY_API_KEY, 'ParentId': series_id, 'IncludeItemTypes': 'Episode',
                            'Recursive': 'true', 'Fields': 'ParentIndexNumber,IndexNumber,Name'}
                resp = make_request_with_retry('GET', items_api, params=params, timeout=20)
                eps = resp.json().get('Items', []) if resp else []
                want = []
                for it in eps:
                    s = it.get('ParentIndexNumber'); e = it.get('IndexNumber')
                    if s is None or e is None: continue
                    if int(s) in _task['mapping'] and int(e) in set(_task['mapping'][int(s)]):
                        want.append(it)
                if not want:
                    return ["ℹ️ Emby 中未找到匹配的集条目。"]
                for it in want:
                    s = it.get('ParentIndexNumber'); e = it.get('IndexNumber')
                    name = it.get('Name') or f"S{s:02d}E{e:02d}"
                    res = delete_emby_item(it.get('Id'), name)
                    logs.append(res)
                return logs

            return ["❌ 未知任务类型。"]

        base_dir, cloud_dir, err = _paths_for_series(task['series_id'])
        if err:
            final_msg = escape_markdown(err)
            if message_id:
                edit_telegram_message(chat_id, message_id, final_msg, inline_buttons=[])
                delete_user_message_later(chat_id, message_id, 90)
            else:
                send_deletable_telegram_notification(final_msg, chat_id=chat_id, delay_seconds=120)
            return

        logs = []
        if sub == 'e':
            logs = _emby_delete_for_task(task)
        elif sub in ('l', 'c', 'b'):
            do_local = sub in ('l', 'b')
            do_cloud = sub in ('c', 'b')
            if task['type'] == 'seasons':
                logs = _delete_season_dirs(base_dir, cloud_dir, task['seasons'], do_local=do_local, do_cloud=do_cloud)
                if not logs:
                    logs = ["ℹ️ 未找到需要删除的目录（可能已经不存在）。"]
            elif task['type'] == 'episodes':
                logs = _delete_episodes_files(base_dir, cloud_dir, task['mapping'], do_local=do_local, do_cloud=do_cloud)
                if not logs:
                    logs = ["ℹ️ 未匹配到需要删除的文件（可能已被移除）。"]
            else:
                logs = ["❌ 未知任务类型。"]
        else:
            answer_callback_query(query_id, text="无效的删除方式。", show_alert=True)
            return

        try:
            DELETION_TASK_CACHE.pop(shortid, None)
        except Exception:
            pass

        result_text = "\n".join([escape_markdown(x) for x in logs]) or escape_markdown("✅ 操作完成。")
        if message_id:
            if len(result_text) > 900:
                try:
                    edit_telegram_message(chat_id, message_id, escape_markdown("✅ 删除完成！\n详细日志见下方新消息。"), inline_buttons=[])
                except Exception as e:
                    print(f"⚠️ 编辑原消息失败：{e}")
                send_deletable_telegram_notification(result_text, chat_id=chat_id, delay_seconds=180)
            else:
                edit_telegram_message(chat_id, message_id, result_text, inline_buttons=[])
            delete_user_message_later(chat_id, message_id, 180)
        else:
            send_deletable_telegram_notification(result_text, chat_id=chat_id, delay_seconds=180)
        return

    try:
        command, rest_of_data = data.split('_', 1)
    except (ValueError, AttributeError):
        answer_callback_query(query_id); return

    if command == 'n':
        main_data, initiator_id_str = rest_of_data.rsplit('_', 1)
        if not is_super_admin(clicker_id):
            answer_callback_query(query_id, text="抱歉，此操作仅对超级管理员开放。", show_alert=True)
            return
        answer_callback_query(query_id)
        send_settings_menu(chat_id, int(initiator_id_str), message_id, main_data)
        return

    if command == 't':
        item_index_str, initiator_id_str = rest_of_data.split('_', 1)
        if not is_super_admin(clicker_id):
            answer_callback_query(query_id, text="抱歉，此操作仅对超级管理员开放。", show_alert=True)
            return
        item_index = int(item_index_str)
        node_key = TOGGLE_INDEX_TO_KEY.get(item_index)
        if not node_key:
            answer_callback_query(query_id, text="无效的设置项。", show_alert=True)
            return
        node_info = TOGGLE_KEY_TO_INFO.get(node_key)
        config_path, menu_key_to_refresh = node_info['config_path'], node_info['parent']
        current_value = get_setting(config_path)
        set_setting(config_path, not current_value)
        save_config()
        answer_callback_query(query_id, text=f"设置已更新: {'✅' if not current_value else '❌'}")
        send_settings_menu(chat_id, int(initiator_id_str), message_id, menu_key_to_refresh)
        return

    if command == 'c' and rest_of_data == f"menu_{clicker_id}":
        answer_callback_query(query_id)
        delete_telegram_message(chat_id, message_id)
        send_simple_telegram_message("✅ 设置菜单已关闭。", chat_id=chat_id)
        return

    if command == 's':
        action, rest_params = rest_of_data.split('_', 1)
        
        initiator_id_str = rest_params.rsplit('_', -1)[-1]
        if initiator_id_str.isdigit():
            initiator_id = int(initiator_id_str)
            if not is_super_admin(clicker_id) and clicker_id != initiator_id:
                answer_callback_query(query_id, text="交互由其他用户发起，您无法操作！", show_alert=True)
                return

        if action == 'page':
            try:
                search_id, page_str, initiator_id_str = rest_params.split('_')
                answer_callback_query(query_id)
                send_search_results_page(chat_id, search_id, int(initiator_id_str), int(page_str), message_id)
            except ValueError:
                answer_callback_query(query_id, text="回调参数错误。", show_alert=True)
            return
            
        elif action == 'detail':
            try:
                search_id, item_index_str, initiator_id_str = rest_params.split('_')
                item_index = int(item_index_str)
                initiator_id = int(initiator_id_str)
                answer_callback_query(query_id, text="正在获取详细信息...")
                send_search_detail(chat_id, search_id, item_index, initiator_id)
            except ValueError:
                answer_callback_query(query_id, text="回调参数错误。", show_alert=True)
            return

        answer_callback_query(query_id)
        return

    if command == 'm':
        parts = rest_of_data.split('_')
        action = parts[0]
        
        if len(parts) > 1:
            if parts[0] in ['scanitem', 'scanlibrary', 'scanall', 'userdelete', 'deleteemby', 'deletelocal', 'deletecloud', 'deleteboth', 'refresh'] and parts[1] == 'confirm':
                action = f"{parts[0]}confirm"
            elif parts[0] == 'scanlibrary' and parts[1] == 'execute':
                action = 'scanlibraryexecute'
            elif parts[0] == 'scanall' and parts[1] == 'execute':
                action = 'scanallexecute'

        rest_params = rest_of_data[len(action)+1:] if rest_of_data.startswith(action + '_') else ''
        if not rest_params and len(parts) > 1 and action == parts[0]:
             rest_params = '_'.join(parts[1:])

        try:
            initiator_id_str = rest_params.rsplit('_', 1)[-1]
            if initiator_id_str.isdigit():
                if not is_super_admin(clicker_id) and str(clicker_id) != initiator_id_str:
                    answer_callback_query(query_id, text="交互由其他用户发起，您无法操作！", show_alert=True)
                    return
        except (ValueError, IndexError):
            pass

        if action == 'filesmain':
            initiator_id_str = rest_params.split('_')[0]
            answer_callback_query(query_id)
            prompt_message = "请选择节目和文件管理操作："
            buttons = [
                [{'text': '🔀 管理单个节目', 'callback_data': f'm_searchshow_dummy_{initiator_id_str}'}],
                [{'text': '🔎 扫描媒体库', 'callback_data': f'm_scanlibrary_{initiator_id_str}'}],
                [{'text': '⬇️ 从网盘同步新节目', 'callback_data': f'm_addfromcloud_dummy_{initiator_id_str}'}],
                [{'text': '◀️ 返回上一级', 'callback_data': f'm_backtomain_{initiator_id_str}'}],
                [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{initiator_id_str}'}]
            ]
            edit_telegram_message(chat_id, message_id, escape_markdown(prompt_message), inline_buttons=buttons)
            return

        if action == 'backtomain':
            initiator_id_str = rest_params.split('_')[0]
            answer_callback_query(query_id)
            send_manage_main_menu(chat_id, int(initiator_id_str), message_id)
            return

        if action == 'usermain':
            initiator_id_str = rest_params.split('_')[0]
            answer_callback_query(query_id)
            buttons = [
                [{'text': '➕ 创建用户', 'callback_data': f'm_usercreate_{initiator_id_str}'}],
                [{'text': '✏️ 修改用户名', 'callback_data': f'm_userrename_{initiator_id_str}'}],
                [{'text': '🔑 修改密码', 'callback_data': f'm_userpass_{initiator_id_str}'}],
                [{'text': '🗑️ 删除用户', 'callback_data': f'm_userdelete_{initiator_id_str}'}],
                [{'text': '◀️ 返回上一级', 'callback_data': f'm_backtomain_{initiator_id_str}'}],
                [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{initiator_id_str}'}]
            ]
            edit_telegram_message(chat_id, message_id, "请选择用户管理操作：", inline_buttons=buttons)
            return

        if action == 'userrename':
            initiator_id_str = rest_params.split('_')[0]
            answer_callback_query(query_id)
            prompt = "✍️ 请输入用户的 **旧用户名** 和 **新用户名**，用空格隔开。\n\n*注意：新旧用户名本身均不允许包含空格。*"
            user_context[chat_id] = {'state': 'awaiting_rename_info', 'initiator_id': int(initiator_id_str), 'message_id': message_id}
            edit_telegram_message(chat_id, message_id, escape_markdown(prompt))
            return

        if action == 'usercreate':
            initiator_id_str = rest_params.split('_')[0]
            answer_callback_query(query_id)
            if not EMBY_TEMPLATE_USER_ID:
                edit_telegram_message(chat_id, message_id, escape_markdown("❌ 操作失败: 未在 config.yaml 中配置 `template_user_id`。"), inline_buttons=[])
                return
            prompt = "✍️ 请输入 **用户名** 和 **初始密码**（可选），用空格隔开。\n\n*注意：*\n*1. 用户名和密码本身均不允许包含空格。\n2. 若只输入用户名，密码将设置为空。*"
            user_context[chat_id] = {'state': 'awaiting_new_user_credentials', 'initiator_id': int(initiator_id_str), 'message_id': message_id}
            edit_telegram_message(chat_id, message_id, escape_markdown(prompt))
            return
            
        if action == 'userpass':
            initiator_id_str = rest_params.split('_')[0]
            answer_callback_query(query_id)
            prompt = "✍️ 请输入要修改密码的 **用户名** 和 **新密码**（可选），用空格隔开。\n\n*注意：*\n*1. 用户名和密码本身均不允许包含空格。\n2. 若只输入用户名，密码将设置为空。*"
            user_context[chat_id] = {'state': 'awaiting_password_change_info', 'initiator_id': int(initiator_id_str), 'message_id': message_id}
            edit_telegram_message(chat_id, message_id, escape_markdown(prompt))
            return
        
        if action == 'searchshow':
            answer_callback_query(query_id)
            prompt_text = "✍️ 请输入需要管理的节目名称（可包含年份）或 TMDB ID。"
            user_context[chat_id] = {'state': 'awaiting_manage_query', 'initiator_id': clicker_id, 'message_id': message_id}
            edit_telegram_message(chat_id, message_id, escape_markdown(prompt_text))
            return

        if action == 'addfromcloud':
            answer_callback_query(query_id)
            prompt_text = "✍️ 请输入节目名称、年份、节目类型（用空格分隔，如 `凡人修仙传 2025 国产剧`）："
            user_context[chat_id] = {'state': 'awaiting_new_show_info', 'initiator_id': clicker_id, 'message_id': message_id}
            edit_telegram_message(chat_id, message_id, escape_markdown(prompt_text))
            return
            
        if action == 'userdelete':
            initiator_id_str = rest_params.split('_')[0]
            answer_callback_query(query_id)
            prompt = "✍️ 请输入您要删除的Emby用户的 **准确用户名**。"
            user_context[chat_id] = {'state': 'awaiting_user_to_delete', 'initiator_id': int(initiator_id_str), 'message_id': message_id}
            edit_telegram_message(chat_id, message_id, escape_markdown(prompt))
            return
            
        if action == 'userdeleteconfirm':
            user_id_to_delete, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id, "正在执行删除...", show_alert=False)
            success = delete_emby_user_by_id(user_id_to_delete)
            result_message = f"✅ 用户(ID: {user_id_to_delete}) 已成功删除。" if success else f"❌ 删除用户(ID: {user_id_to_delete}) 失败。"
            edit_telegram_message(chat_id, message_id, escape_markdown(result_message), inline_buttons=[])
            delete_user_message_later(chat_id, message_id, 60)
            return

        if action == 'doupdate':
            update_uuid, initiator_id_str = rest_params.rsplit('_', 1)
            answer_callback_query(query_id, "正在从网盘同步文件...", show_alert=False)

            base_path = UPDATE_PATH_CACHE.pop(update_uuid, None)
            if not base_path:
                error_text = "❌ 操作已过期或无效，请重新发起。"
                post_update_result_to_telegram(
                    chat_id=chat_id, message_id=message_id, callback_message=message,
                    escaped_result=escape_markdown(error_text), delete_after=60
                )
                return

            result_message = update_media_files(base_path)
            escaped_result = escape_markdown(result_message)

            post_update_result_to_telegram(
                chat_id=chat_id, message_id=message_id, callback_message=message,
                escaped_result=escaped_result, delete_after=180
            )
            return

        if action == 'page':
            search_id, page_str, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id)
            send_manage_results_page(chat_id, search_id, int(initiator_id_str), int(page_str), message_id)
            return

        if action == 'detail':
            search_id, item_index_str, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id, text="正在获取详细信息...")
            send_manage_detail(chat_id, search_id, int(item_index_str), int(initiator_id_str))
            return

        if action == 'files':
            item_id, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id)
            delete_telegram_message(chat_id, message_id)
            buttons = [
                [{'text': '🗂️ 扫描文件夹', 'callback_data': f'm_scanitem_{item_id}_{initiator_id_str}'}],
                [{'text': '🔄 刷新元数据', 'callback_data': f'm_refresh_{item_id}_{initiator_id_str}'}],
                [{'text': '❌ 删除该节目', 'callback_data': f'm_delete_{item_id}_{initiator_id_str}'}],
                [{'text': '🔄 更新该节目', 'callback_data': f'm_update_{item_id}_{initiator_id_str}'}],
                [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{initiator_id_str}'}]
            ]
            send_deletable_telegram_notification(text="请选择要对该节目执行的文件操作：", chat_id=chat_id, inline_buttons=buttons, delay_seconds=120)
            return
        
        if action == 'scanitem':
            item_id, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id)
            item_info = get_series_item_basic(item_id)
            item_name = item_info.get('Name', f"ID: {item_id}") if item_info else f"ID: {item_id}"
            prompt_text = f"❓ 您确定要扫描 *{escape_markdown(item_name)}* 所在的文件夹吗？\n\n此操作会查找新增或变更的文件（例如新剧集）。"
            buttons = [
                [{'text': '⚠️ 是的，扫描', 'callback_data': f'm_scanitemconfirm_{item_id}_{initiator_id_str}'}],
                [{'text': '◀️ 返回', 'callback_data': f'm_files_{item_id}_{initiator_id_str}'}]
            ]
            edit_telegram_message(chat_id, message_id, prompt_text, inline_buttons=buttons)
            return

        if action == 'scanitemconfirm':
            item_id, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id, "正在发送扫描请求...", show_alert=False)
            item_info = get_series_item_basic(item_id)
            item_name = item_info.get('Name', f"ID: {item_id}") if item_info else f"ID: {item_id}"
            result_message = scan_emby_item(item_id, item_name)
            edit_telegram_message(chat_id, message_id, escape_markdown(result_message), inline_buttons=[])
            delete_user_message_later(chat_id, message_id, 90)
            return
            
        if action == 'refresh':
            item_id, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id)
            item_info = get_series_item_basic(item_id)
            item_name = item_info.get('Name', f"ID: {item_id}") if item_info else f"ID: {item_id}"
            prompt_text = f"❓ 您确定要刷新 *{escape_markdown(item_name)}* 的元数据吗？\n\n此操作会重新扫描所有相关文件并从网上获取信息。"
            buttons = [
                [{'text': '⚠️ 是的，刷新', 'callback_data': f'm_refreshconfirm_{item_id}_{initiator_id_str}'}],
                [{'text': '◀️ 返回', 'callback_data': f'm_files_{item_id}_{initiator_id_str}'}]
            ]
            edit_telegram_message(chat_id, message_id, prompt_text, inline_buttons=buttons)
            return

        if action == 'refreshconfirm':
            item_id, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id, "正在发送刷新请求...", show_alert=False)
            item_info = get_series_item_basic(item_id)
            item_name = item_info.get('Name', f"ID: {item_id}") if item_info else f"ID: {item_id}"
            result_message = refresh_emby_item(item_id, item_name)
            edit_telegram_message(chat_id, message_id, escape_markdown(result_message), inline_buttons=[])
            delete_user_message_later(chat_id, message_id, 90)
            return
        
        if action == 'scanlibrary':
            initiator_id_str = rest_params.split('_')[0]
            answer_callback_query(query_id, text="正在获取媒体库列表...")
            libraries, error = get_emby_libraries()
            if error:
                edit_telegram_message(chat_id, message_id, escape_markdown(f"❌ 获取媒体库失败: {error}"), inline_buttons=[])
                return
            buttons = []
            buttons.append([{'text': '💥 扫描所有媒体库', 'callback_data': f"m_scanallconfirm_{initiator_id_str}"}])
            for lib in libraries:
                lib_name_b64 = base64.b64encode(lib['name'].encode('utf-8')).decode('utf-8')
                buttons.append([{'text': f"🗂️ {lib['name']}", 'callback_data': f"m_scanlibraryconfirm_{lib['id']}_{lib_name_b64}_{initiator_id_str}"}])
            buttons.append([{'text': '◀️ 返回上一级', 'callback_data': f'm_filesmain_{initiator_id_str}'}])
            edit_telegram_message(chat_id, message_id, escape_markdown("请选择要扫描的媒体库："), inline_buttons=buttons)
            return

        if action == 'scanallconfirm':
            initiator_id_str = rest_params
            answer_callback_query(query_id)
            prompt_text = f"❓ 您确定要扫描 **所有** 媒体库吗？\n\n此操作会消耗较多服务器资源，可能需要一些时间。"
            buttons = [
                [{'text': '⚠️ 是的，全部扫描', 'callback_data': f'm_scanallexecute_{initiator_id_str}'}],
                [{'text': '◀️ 返回', 'callback_data': f'm_scanlibrary_{initiator_id_str}'}]
            ]
            edit_telegram_message(chat_id, message_id, prompt_text, inline_buttons=buttons)
            return

        if action == 'scanallexecute':
            initiator_id_str = rest_params
            answer_callback_query(query_id, "正在发送全局扫描请求...", show_alert=False)
            result_message = scan_all_emby_libraries()
            edit_telegram_message(chat_id, message_id, escape_markdown(result_message), inline_buttons=[])
            delete_user_message_later(chat_id, message_id, 90)
            return

        if action == 'scanlibraryconfirm':
            try:
                lib_id, lib_name_b64, initiator_id_str = rest_params.split('_', 2)
                lib_name = base64.b64decode(lib_name_b64).decode('utf-8')
            except Exception:
                answer_callback_query(query_id, text="回调参数错误", show_alert=True)
                return
            answer_callback_query(query_id)
            prompt_text = f"❓ 您确定要扫描媒体库 *{escape_markdown(lib_name)}* 吗？\n\n此操作可能需要一些时间。"
            buttons = [
                [{'text': '⚠️ 是的，扫描', 'callback_data': f"m_scanlibraryexecute_{lib_id}_{lib_name_b64}_{initiator_id_str}"}],
                [{'text': '◀️ 返回', 'callback_data': f'm_scanlibrary_{initiator_id_str}'}]
            ]
            edit_telegram_message(chat_id, message_id, prompt_text, inline_buttons=buttons)
            return

        if action == 'scanlibraryexecute':
            try:
                lib_id, lib_name_b64, initiator_id_str = rest_params.split('_', 2)
                lib_name = base64.b64decode(lib_name_b64).decode('utf-8')
            except Exception:
                answer_callback_query(query_id, text="回调参数错误", show_alert=True)
                return
            answer_callback_query(query_id, "正在发送扫描请求...", show_alert=False)
            result_message = scan_emby_item(lib_id, lib_name)
            edit_telegram_message(chat_id, message_id, escape_markdown(result_message), inline_buttons=[])
            delete_user_message_later(chat_id, message_id, 90)
            return

        if action == 'delete':
            item_id, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id, "正在获取节目类型...")
            full_item_url = f"{EMBY_SERVER_URL}/Users/{EMBY_USER_ID}/Items/{item_id}"
            params = {'api_key': EMBY_API_KEY, 'Fields': 'Type'}
            response = make_request_with_retry('GET', full_item_url, params=params, timeout=10)
            if not response:
                edit_telegram_message(chat_id, message_id, escape_markdown("❌ 获取节目类型失败，请重试。"), inline_buttons=[])
                return
            item_type = response.json().get('Type')
            if item_type == 'Movie':
                buttons = [
                    [{'text': '⏏️ 从Emby中删除节目', 'callback_data': f'm_deleteemby_{item_id}_{initiator_id_str}'}],
                    [{'text': '🗑️ 删除本地文件', 'callback_data': f'm_deletelocal_{item_id}_{initiator_id_str}'}],
                    [{'text': '☁️ 删除网盘文件', 'callback_data': f'm_deletecloud_{item_id}_{initiator_id_str}'}],
                    [{'text': '💥 删除本地和网盘文件', 'callback_data': f'm_deleteboth_{item_id}_{initiator_id_str}'}],
                    [{'text': '◀️ 返回上一步', 'callback_data': f'm_files_{item_id}_{initiator_id_str}'}],
                    [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{initiator_id_str}'}]
                ]
                edit_telegram_message(chat_id, message_id, escape_markdown("检测到该节目为**电影**，请选择删除方式："), inline_buttons=buttons)
            elif item_type == 'Series':
                buttons = [
                    [{'text': '❌ 删除整个剧集', 'callback_data': f'm_deleteall_{item_id}_{initiator_id_str}'}],
                    [{'text': '❌ 删除季', 'callback_data': f'm_deleteseasons_{item_id}_{initiator_id_str}'}],
                    [{'text': '❌ 删除集', 'callback_data': f'm_deleteepisodes_{item_id}_{initiator_id_str}'}],
                    [{'text': '◀️ 返回上一步', 'callback_data': f'm_files_{item_id}_{initiator_id_str}'}],
                    [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{initiator_id_str}'}]
                ]
                edit_telegram_message(chat_id, message_id, escape_markdown("检测到该节目为**剧集**，请选择需要删除的内容："), inline_buttons=buttons)
            else:
                edit_telegram_message(chat_id, message_id, escape_markdown(f"❌ 不支持的节目类型: {item_type}，无法执行删除操作。"), inline_buttons=[])
            return

        if action == 'deleteall':
            item_id, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id)
            buttons = [
                [{'text': '⏏️ 从Emby中删除节目', 'callback_data': f'm_deleteemby_{item_id}_{initiator_id_str}'}],
                [{'text': '🗑️ 删除本地文件', 'callback_data': f'm_deletelocal_{item_id}_{initiator_id_str}'}],
                [{'text': '☁️ 删除网盘文件', 'callback_data': f'm_deletecloud_{item_id}_{initiator_id_str}'}],
                [{'text': '💥 删除本地和网盘文件', 'callback_data': f'm_deleteboth_{item_id}_{initiator_id_str}'}],
                [{'text': '◀️ 返回上一步', 'callback_data': f'm_delete_{item_id}_{initiator_id_str}'}],
                [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{initiator_id_str}'}]
            ]
            edit_telegram_message(chat_id, message_id, "请选择要删除的项目：", inline_buttons=buttons)
            return

        if action == 'deleteseasons':
            series_id, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id)
            prompt = (
                "✍️ 请输入要删除的季编号，多个用空格分隔（支持 S 前缀或纯数字）：\n"
                "例如：`S01 S03 S05` 或 `1 3 5`"
            )
            user_context[chat_id] = {'state': 'awaiting_season_selection', 'initiator_id': int(initiator_id_str), 'series_id': series_id, 'message_id': message_id}
            edit_telegram_message(chat_id, message_id, escape_markdown(prompt))
            return

        if action == 'deleteepisodes':
            series_id, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id)
            prompt = (
                "✍️ 请输入要删除的季和集编号，支持范围与省略季的写法；多个用空格/逗号分隔：\n"
                "例如：`S01E03 E11 S02E03-E06 E10`"
            )
            user_context[chat_id] = {'state': 'awaiting_episode_selection', 'initiator_id': int(initiator_id_str), 'series_id': series_id, 'message_id': message_id}
            edit_telegram_message(chat_id, message_id, escape_markdown(prompt))
            return
        
        if action in ['deleteemby', 'deletelocal', 'deletecloud', 'deleteboth']:
            item_id, initiator_id_str = rest_params.split('_')
            
            if action in ['deletecloud', 'deleteboth'] and not get_setting('settings.media_cloud_path'):
                answer_callback_query(query_id)
                buttons = [
                    [{'text': '◀️ 返回上一步', 'callback_data': f'm_delete_{item_id}_{initiator_id_str}'}],
                    [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{initiator_id_str}'}]
                ]
                edit_telegram_message(chat_id, message_id, escape_markdown("❌ 操作失败：网盘目录 (media_cloud_path) 未在配置中设置。"), inline_buttons=buttons)
                return

            full_item_url = f"{EMBY_SERVER_URL}/Users/{EMBY_USER_ID}/Items/{item_id}"
            params = {'api_key': EMBY_API_KEY, 'Fields': 'Path,Name,ProductionYear'}
            response = make_request_with_retry('GET', full_item_url, params=params, timeout=10)
            if not response:
                answer_callback_query(query_id, "获取项目信息失败！", show_alert=True)
                return
            item_data = response.json()
            item_name = item_data.get('Name', '未知节目')
            year = item_data.get('ProductionYear')
            full_item_name = f"{item_name} ({year})" if item_name and year else item_name

            action_map = {
                'deleteemby': {'text': f"Emby媒体库中的 *{full_item_name}*", 'confirm_cb': f'm_deleteembyconfirm_{item_id}_{initiator_id_str}'},
                'deletelocal': {'text': '本地文件', 'confirm_cb': f'm_deletelocalconfirm_{item_id}_{initiator_id_str}'},
                'deletecloud': {'text': '网盘文件', 'confirm_cb': f'm_deletecloudconfirm_{item_id}_{initiator_id_str}'},
                'deleteboth': {'text': '本地和网盘文件', 'confirm_cb': f'm_deletebothconfirm_{item_id}_{initiator_id_str}'}
            }
            prompt_target = action_map[action]['text']
            confirm_callback = action_map[action]['confirm_cb']

            prompt_text = f"❓ 您确定要删除 `{escape_markdown(prompt_target)}` 吗？\n\n此操作无法撤销！"
            buttons = [
                [{'text': '⚠️ 是的，删除', 'callback_data': confirm_callback}],
                [{'text': '◀️ 返回上一步', 'callback_data': f'm_delete_{item_id}_{initiator_id_str}'}],
                [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{initiator_id_str}'}]
            ]
            answer_callback_query(query_id)
            edit_telegram_message(chat_id, message_id, prompt_text, inline_buttons=buttons)
            return

        if action == 'deleteembyconfirm':
            item_id_to_delete, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id, "正在获取信息并执行删除...", show_alert=False)

            full_item_url = f"{EMBY_SERVER_URL}/Users/{EMBY_USER_ID}/Items/{item_id_to_delete}"
            params = {'api_key': EMBY_API_KEY, 'Fields': 'Name,ProductionYear'}
            response = make_request_with_retry('GET', full_item_url, params=params, timeout=10)

            full_item_name = f"项目 (ID: {item_id_to_delete})"
            if response:
                item_data = response.json()
                name = item_data.get('Name', '')
                year = item_data.get('ProductionYear')
                if name and year:
                    full_item_name = f"{name} ({year})"
                elif name:
                    full_item_name = name

            result_message = delete_emby_item(item_id_to_delete, full_item_name)
            edit_telegram_message(chat_id, message_id, escape_markdown(result_message), inline_buttons=[])
            delete_user_message_later(chat_id, message_id, 60)
            return

        if action in ['deletelocalconfirm', 'deletecloudconfirm', 'deletebothconfirm']:
            item_id, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id, "正在执行删除操作...", show_alert=False)

            full_item_url = f"{EMBY_SERVER_URL}/Users/{EMBY_USER_ID}/Items/{item_id}"
            params = {'api_key': EMBY_API_KEY, 'Fields': 'Path'}
            response = make_request_with_retry('GET', full_item_url, params=params, timeout=10)
            if not response:
                edit_telegram_message(chat_id, message_id, "❌ 获取项目路径失败，无法删除。", inline_buttons=[])
                return

            item_path = response.json().get('Path')

            if action == 'deletelocalconfirm':
                result_message = delete_media_files(item_path, delete_local=True)
            elif action == 'deletecloudconfirm':
                result_message = delete_media_files(item_path, delete_cloud=True)
            elif action == 'deletebothconfirm':
                result_message = delete_media_files(item_path, delete_local=True, delete_cloud=True)

            edit_telegram_message(chat_id, message_id, escape_markdown(result_message), inline_buttons=[])
            delete_user_message_later(chat_id, message_id, 60)
            return

        if action == 'update':
            item_id, initiator_id_str = rest_params.split('_')
            answer_callback_query(query_id, "正在从云端更新文件...", show_alert=False)

            full_item_url = f"{EMBY_SERVER_URL}/Users/{EMBY_USER_ID}/Items/{item_id}"
            params = {'api_key': EMBY_API_KEY, 'Fields': 'Path'}
            response = make_request_with_retry('GET', full_item_url, params=params, timeout=10)
            if not response:
                edit_telegram_message(chat_id, message_id, "❌ 获取项目路径失败，无法更新。", inline_buttons=[])
                return

            item_path = response.json().get('Path')
            if item_path and os.path.splitext(item_path)[1]:
                item_path = os.path.dirname(item_path)

            result_message = update_media_files(item_path)
            escaped = escape_markdown(result_message)

            post_update_result_to_telegram(
                chat_id=chat_id,
                message_id=message_id,
                callback_message=message,
                escaped_result=escaped,
                delete_after=180
            )
            return

        if action == 'exit':
            answer_callback_query(query_id)
            delete_telegram_message(chat_id, message_id)
            send_simple_telegram_message("✅ 已退出管理。", chat_id=chat_id, delay_seconds=15)
            return
        return

    if command == 'session':
        if rest_of_data.startswith('terminateall'):
            if rest_of_data == f"terminateall_{clicker_id}":
                answer_callback_query(query_id)
                confirmation_buttons = [[
                    {'text': '⚠️ 是的，全部停止', 'callback_data': f'session_terminateall_confirm_{clicker_id}'},
                    {'text': '取消', 'callback_data': f'session_action_cancel_{clicker_id}'}
                ]]
                edit_telegram_message(chat_id, message_id, escape_markdown("❓ 您确定要停止*所有*正在播放的会话吗？此操作无法撤销。"), inline_buttons=confirmation_buttons)
                return

            if rest_of_data == f"terminateall_confirm_{clicker_id}":
                answer_callback_query(query_id, text="正在停止所有会话...", show_alert=False)
                sessions_to_terminate = [s for s in get_active_sessions() if s.get('NowPlayingItem')]
                count = 0
                if not sessions_to_terminate:
                    edit_telegram_message(chat_id, message_id, "✅ 当前已无活跃会话，无需操作。", inline_buttons=[])
                else:
                    for session in sessions_to_terminate:
                        session_id = session.get('Id')
                        if session_id and terminate_emby_session(session_id, None):
                            count += 1
                    edit_telegram_message(chat_id, message_id, f"✅ 操作完成，共停止了 {count} 个播放会话。", inline_buttons=[])
                delete_user_message_later(chat_id, message_id, 60)
                return

        if rest_of_data == f"broadcast_{clicker_id}":
            answer_callback_query(query_id)
            user_context[chat_id] = {'state': 'awaiting_broadcast_message', 'initiator_id': clicker_id}
            prompt_text = "✍️ 请输入您想*群发*给所有用户的消息内容："
            if chat_id < 0:
                prompt_text = "✍️ *请回复本消息*，输入您想*群发*给所有用户的消息内容："
            send_deletable_telegram_notification(escape_markdown(prompt_text), chat_id=chat_id, delay_seconds=60)
            return

        if rest_of_data == f"action_cancel_{clicker_id}":
            answer_callback_query(query_id)
            original_text = message.get('text', '操作已取消')
            edit_telegram_message(chat_id, message_id, f"~~{original_text}~~\n\n✅ 操作已取消。", inline_buttons=[])
            delete_user_message_later(chat_id, message_id, 60)
            return

        try:
            action, session_id, initiator_id_str = rest_of_data.split('_')
            initiator_id = int(initiator_id_str)
        except ValueError:
            answer_callback_query(query_id); return

        if action == 'terminate':
            answer_callback_query(query_id)
            if terminate_emby_session(session_id, chat_id):
                answer_callback_query(query_id, text="✅ 播放已成功停止。", show_alert=True)
            else:
                answer_callback_query(query_id, text="❌ 播放停止失败。", show_alert=True)
        elif action == 'message':
            answer_callback_query(query_id)
            user_context[chat_id] = {'state': 'awaiting_message_for_session', 'session_id': session_id, 'initiator_id': initiator_id}
            prompt_text = "✍️ 请输入您想发送给该用户的消息内容："
            if chat_id < 0:
                prompt_text = "✍️ *请回复本消息*，输入您想发送给该用户的消息内容："
            send_deletable_telegram_notification(escape_markdown(prompt_text), chat_id=chat_id, delay_seconds=60)
        return

    answer_callback_query(query_id)
       
def handle_telegram_command(message):
    """
    处理用户在聊天中直接输入的命令/文本。
    - 新增多层级 /manage 菜单
    - 增加修改用户名、允许空密码等新逻辑
    """
    global user_search_state, user_context, DELETION_TASK_CACHE

    msg_text = (message.get('text') or '').strip()
    chat_id = message['chat']['id']
    user_id = message['from']['id']
    print(f"➡️ 收到来自用户 {user_id} 在 Chat ID {chat_id} 的命令: {msg_text}")

    if not is_user_authorized(user_id):
        print(f"🚫 已忽略来自未授权用户的消息。")
        return

    is_group_chat = chat_id < 0
    is_reply = 'reply_to_message' in message
    mention = f"@{message['from'].get('username')} " if is_group_chat and message['from'].get('username') else ""

    awaiting = (chat_id in user_context) or (chat_id in user_search_state)
    if awaiting:
        if msg_text.startswith('/'):
            user_search_state.pop(chat_id, None)
            user_context.pop(chat_id, None)
            print(f"ℹ️ 用户 {user_id} 输入了新命令，取消之前的等待状态。")
        else:
            if is_group_chat and not is_reply:
                return

            if chat_id in user_search_state:
                original_user_id = user_search_state.get(chat_id)
                if original_user_id is None or original_user_id != user_id:
                    return
                del user_search_state[chat_id]
                print(f"🔍 用户 {user_id} 发起了搜索: {msg_text}")
                send_search_emby_and_format(msg_text, chat_id, user_id, is_group_chat, mention)
                return

            ctx = user_context.get(chat_id) or {}
            if ctx.get('initiator_id') is not None and ctx['initiator_id'] != user_id:
                return

            state = ctx.get('state')
            
            if state == 'awaiting_new_user_credentials':
                original_message_id = ctx.get('message_id')
                del user_context[chat_id]
                parts = msg_text.split()
                if len(parts) > 2 or (len(parts) > 0 and ' ' in parts[0]):
                    error_msg = "❌ 格式错误。用户名不能包含空格，且用户名和密码之间只能用一个空格分隔。"
                    safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(error_msg), delete_after=60)
                    return
                
                username = parts[0] if len(parts) > 0 else ""
                password = parts[1] if len(parts) > 1 else ""
                
                if not username:
                     error_msg = "❌ 用户名不能为空。"
                     safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(error_msg), delete_after=60)
                     return

                result_message = create_emby_user(username, password)
                safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(result_message), delete_after=120)
                return

            if state == 'awaiting_rename_info':
                original_message_id = ctx.get('message_id')
                del user_context[chat_id]
                parts = msg_text.split()
                if len(parts) != 2 or ' ' in parts[0] or ' ' in parts[1]:
                    error_msg = "❌ 格式错误。请输入旧用户名和新用户名，用一个空格隔开，且两者均不能包含空格。"
                    safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(error_msg), delete_after=60)
                    return
                
                old_username, new_username = parts
                user_obj, error = get_emby_user_by_name(old_username)
                if error:
                    safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(f"❌ 操作失败: {error}"), delete_after=60)
                    return
                
                result_message = rename_emby_user(user_obj['Id'], new_username)
                safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(result_message), delete_after=120)
                return

            if state == 'awaiting_password_change_info':
                original_message_id = ctx.get('message_id')
                del user_context[chat_id]
                parts = msg_text.split()
                if len(parts) > 2 or (len(parts) > 0 and ' ' in parts[0]):
                    error_msg = "❌ 格式错误。用户名不能包含空格，且用户名和新密码之间只能用一个空格分隔。"
                    safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(error_msg), delete_after=60)
                    return
                
                username = parts[0] if len(parts) > 0 else ""
                new_password = parts[1] if len(parts) > 1 else ""

                if not username:
                     error_msg = "❌ 用户名不能为空。"
                     safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(error_msg), delete_after=60)
                     return

                user_obj, error = get_emby_user_by_name(username)
                if error:
                    safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(f"❌ 操作失败: {error}"), delete_after=60)
                    return

                if set_emby_user_password(user_obj['Id'], new_password):
                    result_message = f"✅ 用户 '{username}' 的密码已成功修改。"
                else:
                    result_message = f"❌ 修改用户 '{username}' 的密码失败。"
                safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(result_message), delete_after=120)
                return

            if state == 'awaiting_user_to_delete':
                original_message_id = ctx.get('message_id')
                del user_context[chat_id]
                username_to_delete = msg_text.strip()

                emby_bot_username = (CONFIG.get('emby', {}).get('username') or "").lower()
                if username_to_delete.lower() == emby_bot_username:
                    error_msg = "❌ 不能删除机器人自身正在使用的管理员账户。"
                    safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(error_msg), delete_after=60)
                    return

                user_obj, error = get_emby_user_by_name(username_to_delete)
                if error:
                    safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(f"❌ 操作失败: {error}"), delete_after=60)
                    return

                user_id_to_delete = user_obj['Id']
                prompt_text = f"❓ 您确定要删除用户 *{escape_markdown(username_to_delete)}* \(ID: `{user_id_to_delete}`\) 吗？\n\n**此操作无法撤销！**"
                buttons = [
                    [{'text': '⚠️ 是的，删除', 'callback_data': f'm_userdeleteconfirm_{user_id_to_delete}_{user_id}'}],
                    [{'text': '◀️ 返回上一级', 'callback_data': f'm_usermain_{user_id}'}]
                ]
                safe_edit_or_send_message(chat_id, original_message_id, prompt_text, buttons=buttons)
                return

            if state == 'awaiting_message_for_session':
                session_id_to_send = ctx['session_id']
                del user_context[chat_id]
                print(f"✉️ 用户 {user_id} 回复了消息，发送给会话 {session_id_to_send}: {msg_text}")
                send_message_to_emby_session(session_id_to_send, msg_text, chat_id)
                return

            if state == 'awaiting_broadcast_message':
                del user_context[chat_id]
                sessions_to_broadcast = [s for s in get_active_sessions() if s.get('NowPlayingItem')]
                if not sessions_to_broadcast:
                    send_simple_telegram_message("当前无人观看，无需群发。", chat_id)
                else:
                    count = 0
                    for s in sessions_to_broadcast:
                        sid = s.get('Id')
                        if sid:
                            send_message_to_emby_session(sid, msg_text, None)
                            count += 1
                    send_simple_telegram_message(f"✅ 已向 {count} 个会话发送群发消息。", chat_id)
                return

            if state == 'awaiting_season_selection':
                try:
                    series_id = ctx['series_id']
                    origin_msg_id = ctx.get('message_id')
                    
                    seasons = parse_season_selection(msg_text)
                    if not seasons:
                        send_deletable_telegram_notification("❌ 输入无效，请按示例输入：S01 S03 S05", chat_id=chat_id, delay_seconds=90)
                        return

                    shortid = uuid.uuid4().hex[:8]
                    DELETION_TASK_CACHE[shortid] = {
                        'type': 'seasons',
                        'series_id': series_id,
                        'seasons': seasons,
                        'initiator_id': user_id
                    }
                    
                    preview = "、".join([f"S{n:02d}" for n in seasons])
                    msg = f"⚠️ 将要删除的季：{preview}\n请选择删除方式："
                    
                    buttons = [
                        [{'text': '⏏️ 从Emby中删除', 'callback_data': f'mdc_e_{shortid}'}],
                        [{'text': '🗑️ 删除本地文件', 'callback_data': f'mdc_l_{shortid}'}],
                        [{'text': '☁️ 删除网盘文件', 'callback_data': f'mdc_c_{shortid}'}],
                        [{'text': '💥 删除本地+网盘', 'callback_data': f'mdc_b_{shortid}'}],
                        [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{user_id}'}],
                    ]

                    del user_context[chat_id]
                    if origin_msg_id:
                        edit_telegram_message(chat_id, origin_msg_id, escape_markdown(msg), inline_buttons=buttons)
                    else:
                        send_deletable_telegram_notification(escape_markdown(msg), chat_id=chat_id, inline_buttons=buttons, delay_seconds=180)
                except Exception as e:
                    print(f"❌ 处理季号输入时异常：{e}")
                return

            if state == 'awaiting_episode_selection':
                try:
                    series_id = ctx['series_id']
                    origin_msg_id = ctx.get('message_id')

                    mapping = parse_episode_selection(msg_text)
                    if not mapping:
                        send_deletable_telegram_notification("❌ 未能解析任何有效的季/集编号。示例：`S01E03 E11 S02E03-E06 E10`", chat_id=chat_id, delay_seconds=120)
                        return

                    shortid = uuid.uuid4().hex[:8]
                    DELETION_TASK_CACHE[shortid] = {
                        'type': 'episodes',
                        'series_id': series_id,
                        'mapping': mapping,
                        'initiator_id': user_id
                    }

                    groups = []
                    for s in sorted(mapping.keys()):
                        eps = ",".join([f"E{int(e):02d}" for e in sorted(list(mapping[s]))])
                        groups.append(f"S{int(s):02d}({eps})")
                    preview = "；".join(groups)
                    
                    msg = f"⚠️ 将要删除的集：{preview}\n请选择删除方式："

                    buttons = [
                        [{'text': '⏏️ 从Emby中删除', 'callback_data': f'mdc_e_{shortid}'}],
                        [{'text': '🗑️ 删除本地文件', 'callback_data': f'mdc_l_{shortid}'}],
                        [{'text': '☁️ 删除网盘文件', 'callback_data': f'mdc_c_{shortid}'}],
                        [{'text': '💥 删除本地+网盘', 'callback_data': f'mdc_b_{shortid}'}],
                        [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{user_id}'}],
                    ]

                    del user_context[chat_id]
                    if origin_msg_id:
                        edit_telegram_message(chat_id, origin_msg_id, escape_markdown(msg), inline_buttons=buttons)
                    else:
                        send_deletable_telegram_notification(escape_markdown(msg), chat_id=chat_id, inline_buttons=buttons, delay_seconds=180)
                except Exception as e:
                    print(f"❌ 处理集编号输入时异常：{e}")
                return

            if state == 'awaiting_manage_query':
                original_message_id = ctx.get('message_id')
                del user_context[chat_id]
                if original_message_id:
                    delete_telegram_message(chat_id, original_message_id)
                print(f"🗃️ 用户 {user_id} 回复了管理查询: {msg_text}")
                send_manage_emby_and_format(msg_text, chat_id, user_id, is_group_chat, mention)
                return
            
            if state == 'awaiting_new_show_info':
                original_message_id = ctx.get('message_id')
                del user_context[chat_id]
                
                parts = msg_text.split()
                if len(parts) < 3 or not parts[-2].isdigit() or len(parts[-2]) != 4:
                    error_text = "❌ 输入格式不正确，请确保包含名称、四位年份和类型，并用空格分隔。"
                    buttons = [[{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{user_id}'}]]
                    safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(error_text), buttons=buttons, delete_after=60)
                    return

                name = " ".join(parts[:-2])
                year = parts[-2]
                media_type_folder = parts[-1]
                
                media_cloud_path = get_setting('settings.media_cloud_path')
                media_base_path = get_setting('settings.media_base_path')

                if not media_cloud_path or not media_base_path:
                    safe_edit_or_send_message(chat_id, original_message_id, escape_markdown("❌ 配置错误：`media_cloud_path` 或 `media_base_path` 未设置。"), delete_after=60)
                    return

                source_category_dir = os.path.join(media_cloud_path, media_type_folder)
                if not os.path.isdir(source_category_dir):
                    safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(f"❌ 未找到云端分类目录：`{media_type_folder}`"), delete_after=60)
                    return

                best_match_dir = None
                for dirname in os.listdir(source_category_dir):
                    if name in dirname and year in dirname:
                        best_match_dir = dirname
                        break
                
                if not best_match_dir:
                    safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(f"❌ 在 `{media_type_folder}` 分类下未找到与“{name} ({year})”匹配的节目目录。"), delete_after=60)
                    return
                
                full_cloud_path = os.path.join(source_category_dir, best_match_dir)
                
                preferred_nfo = os.path.join(full_cloud_path, 'tvshow.nfo')
                nfo_file = preferred_nfo if os.path.isfile(preferred_nfo) else find_nfo_file_in_dir(full_cloud_path)

                if not nfo_file:
                    error_text = f"❌ 在目录 `/{escape_markdown(os.path.join(media_type_folder, best_match_dir))}` 中未找到 .nfo 文件。"
                    buttons = [[{'text': '◀️ 返回上一级', 'callback_data': f'm_filesmain_{user_id}'}],
                               [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{user_id}'}]]
                    safe_edit_or_send_message(chat_id, original_message_id, error_text, buttons=buttons, delete_after=120)
                    return
                
                tmdb_id = parse_tmdbid_from_nfo(nfo_file)
                if not tmdb_id:
                    nfo_filename = os.path.basename(nfo_file)
                    error_text = f"❌ 无法从文件 `{escape_markdown(nfo_filename)}` 中解析出有效的 TMDB ID。"
                    buttons = [[{'text': '◀️ 返回上一级', 'callback_data': f'm_filesmain_{user_id}'}],
                               [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{user_id}'}]]
                    safe_edit_or_send_message(chat_id, original_message_id, error_text, buttons=buttons, delete_after=120)
                    return
                
                tmdb_details = None
                if TMDB_API_TOKEN:
                    forced_media_type = None
                    if os.path.basename(nfo_file).lower() == 'tvshow.nfo':
                        forced_media_type = 'tv'
                    elif '电影' in media_type_folder:
                        forced_media_type = 'movie'

                    if forced_media_type:
                        url = f"https://api.themoviedb.org/3/{forced_media_type}/{tmdb_id}"
                        params = {'api_key': TMDB_API_TOKEN, 'language': 'zh-CN'}
                        proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
                        response = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies, max_retries=1)
                        if response:
                            tmdb_details = response.json()
                            if not tmdb_details.get('title') and not tmdb_details.get('name'):
                                tmdb_details = None
                    
                    if not tmdb_details:
                        tmdb_details = get_tmdb_details_by_id(tmdb_id)

                if not tmdb_details:
                    error_text = f"❌ 使用 TMDB ID `{tmdb_id}` 查询信息失败。"
                    buttons = [[{'text': '◀️ 返回上一级', 'callback_data': f'm_filesmain_{user_id}'}],
                               [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{user_id}'}]]
                    safe_edit_or_send_message(chat_id, original_message_id, escape_markdown(error_text), buttons=buttons, delete_after=120)
                    return
                
                poster_path = tmdb_details.get('poster_path')
                poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
                title = tmdb_details.get('title') or tmdb_details.get('name')
                overview = tmdb_details.get('overview', '暂无剧情简介。')
                tmdb_url_type = "movie" if 'title' in tmdb_details else "tv"
                tmdb_link = f"https://www.themoviedb.org/{tmdb_url_type}/{tmdb_id}"

                message_parts = [
                    f"请确认是否要从网盘同步以下节目：",
                    f"\n名称：[{escape_markdown(f'{title} ({year})')}]({tmdb_link})",
                    f"分类：{escape_markdown(media_type_folder)}",
                    f"剧情：{escape_markdown(overview[:150] + '...' if len(overview) > 150 else overview)}"
                ]
                message_text = "\n".join(message_parts)
                
                update_uuid = str(uuid.uuid4())
                target_path_for_emby = os.path.join(media_base_path, media_type_folder, best_match_dir)
                UPDATE_PATH_CACHE[update_uuid] = target_path_for_emby

                buttons = [
                    [{'text': '⬇️ 确认并开始同步', 'callback_data': f'm_doupdate_{update_uuid}_{user_id}'}],
                    [{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{user_id}'}]
                ]
                
                if original_message_id:
                    delete_telegram_message(chat_id, original_message_id)
                send_deletable_telegram_notification(message_text, photo_url=poster_url, chat_id=chat_id, inline_buttons=buttons, delay_seconds=300, disable_preview=True)
                return

            return

    if '@' in msg_text:
        msg_text = msg_text.split('@')[0]
    if not msg_text.startswith('/'):
        return

    command = msg_text.split()[0]

    if command == '/start':
        welcome_text = (
            escape_markdown("👋 欢迎使用 Emby机器人！\n\n") +
            escape_markdown("本机器人可以帮助您与 Emby 服务器进行交互。\n\n") +
            escape_markdown("以下是您可以使用的命令：\n\n") +
            "🔍 /search" + escape_markdown(" - 在Emby媒体库中搜索电影或剧集。\n") +
            escape_markdown("    示例：/search 流浪地球 或者 /search 凡人修仙传 2025 \n\n") +
            "📊 /status" + escape_markdown(" - 查看Emby服务器上的当前播放状态（仅限服务器管理员）。\n\n") +
            "⚙️ /settings" + escape_markdown(" - 进入交互式菜单以配置机器人通知和功能（仅限服务器管理员）。\n\n") +
            "🗃️ /manage" + escape_markdown(" - 管理Emby节目、媒体文件和用户（仅限服务器管理员）。\n\n") +
            escape_markdown("您可以直接输入命令开始使用。")
        )
        send_telegram_notification(text=welcome_text, chat_id=chat_id, disable_preview=True)
        return

    if command in ['/status', '/settings', '/manage']:
        if not is_super_admin(user_id):
            send_simple_telegram_message("权限不足：此命令仅限超级管理员使用。", chat_id)
            print(f"🚫 拒绝用户 {user_id} 执行管理员命令 {command}")
            return

        if command == '/status':
            status_info = get_active_sessions_info(user_id)
            if isinstance(status_info, str):
                send_deletable_telegram_notification(f"{mention}{status_info}", chat_id=chat_id)
            elif isinstance(status_info, list) and status_info:
                title_message = f"{mention}*🎬 Emby 当前播放会话数: {len(status_info)}*"
                global_buttons = []
                row = []
                if get_setting('settings.content_settings.status_feedback.show_broadcast_button'):
                    row.append({'text': '✉️ 群发消息', 'callback_data': f'session_broadcast_{user_id}'})
                if get_setting('settings.content_settings.status_feedback.show_terminate_all_button'):
                    row.append({'text': '⏹️ 停止所有', 'callback_data': f'session_terminateall_{user_id}'})
                if row: global_buttons.append(row)
                send_deletable_telegram_notification(text=title_message, chat_id=chat_id, inline_buttons=global_buttons or None, disable_preview=True)
                time.sleep(0.5)
                for s in status_info:
                    if s.get('poster_url'):
                        send_telegram_notification(text=s['message'], photo_url=s['poster_url'], chat_id=chat_id, inline_buttons=s.get('buttons'), disable_preview=True)
                    else:
                        send_deletable_telegram_notification(text=s['message'], chat_id=chat_id, inline_buttons=s.get('buttons'), disable_preview=True)
                    time.sleep(0.5)
            return

        if command == '/settings':
            send_settings_menu(chat_id, user_id)
            return

        if command == '/manage':
            search_term = msg_text[len('/manage'):].strip()
            if search_term:
                send_manage_emby_and_format(search_term, chat_id, user_id, is_group_chat, mention)
            else:
                send_manage_main_menu(chat_id, user_id)
            return

    if command == '/search':
        search_term = msg_text[len('/search'):].strip()
        if search_term:
            send_search_emby_and_format(search_term, chat_id, user_id, is_group_chat, mention)
        else:
            user_search_state[chat_id] = user_id
            prompt_message = "请提供您想搜索的节目名称（可选年份）。\n例如：流浪地球 或 凡人修仙传 2025"
            if is_group_chat:
                prompt_message = f"{mention}请回复本消息，提供您想搜索的节目名称（可选年份）。\n例如：流浪地球 或 凡人修仙传 2025"
            send_deletable_telegram_notification(escape_markdown(prompt_message), chat_id=chat_id, delay_seconds=60)

def send_manage_emby_and_format(query, chat_id, user_id, is_group_chat, mention):
    """为 /manage 命令执行搜索并格式化结果。"""
    print(f"🗃️ 用户 {user_id} 发起了管理搜索，查询: {query}")
    original_query = query.strip()
    search_term = original_query
    results = []

    match = re.search(r'(\d{4})$', search_term)
    year_for_filter = match.group(1) if match else None
    if match:
        search_term = search_term[:match.start()].strip()
    
    if original_query.isdigit():
        tmdb_details = get_tmdb_details_by_id(original_query)
        if tmdb_details:
            search_term = tmdb_details.get('title') or tmdb_details.get('name')
            print(f"ℹ️ TMDB ID 查询成功，将使用名称 '{search_term}' 在 Emby 中搜索。")
        else:
            send_deletable_telegram_notification(f"在 TMDB 中找不到 ID 为 `{escape_markdown(original_query)}` 的节目。", chat_id=chat_id)
            return

    request_user_id = EMBY_USER_ID
    if not request_user_id:
        send_deletable_telegram_notification("错误：机器人管理员尚未在配置文件中设置 Emby `user_id`。", chat_id=chat_id)
        return

    url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
    params = {
        'api_key': EMBY_API_KEY, 
        'SearchTerm': search_term, 
        'IncludeItemTypes': 'Movie,Series',
        'Recursive': 'true', 
        'Fields': 'ProviderIds,Path,ProductionYear,Name'
    }

    if year_for_filter:
        params['Years'] = year_for_filter
        
    response = make_request_with_retry('GET', url, params=params, timeout=20)
    results = response.json().get('Items', []) if response else []

    if not results:
        send_deletable_telegram_notification(f"在 Emby 中找不到与“{escape_markdown(original_query)}”相关的任何内容。", chat_id=chat_id)
        return

    search_id = str(uuid.uuid4())
    SEARCH_RESULTS_CACHE[search_id] = results

    print(f"✅ 管理搜索成功，找到 {len(results)} 个结果，缓存 ID: {search_id}")
    
    send_manage_results_page(chat_id, search_id, user_id, page=1)

def send_manage_results_page(chat_id, search_id, user_id, page=1, message_id=None):
    """发送管理搜索结果的某一页。"""
    print(f"📄 正在发送管理搜索结果第 {page} 页，缓存 ID: {search_id}")
    if search_id not in SEARCH_RESULTS_CACHE:
        error_msg = "抱歉，此搜索结果已过期，请重新发起搜索。"
        if message_id: edit_telegram_message(chat_id, message_id, error_msg)
        else: send_deletable_telegram_notification(error_msg, chat_id=chat_id)
        return

    results = SEARCH_RESULTS_CACHE[search_id]
    items_per_page = 10
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    page_items = results[start_index:end_index]

    message_text = "请选择您要管理的节目："
    buttons = []
    for i, item in enumerate(page_items):
        raw_title = item.get('Name', '未知标题')
        final_year = extract_year_from_path(item.get('Path')) or item.get('ProductionYear') or ''
        title_with_year = f"{raw_title} ({final_year})" if final_year else raw_title
        button_text = f"{i + 1 + start_index}. {title_with_year}"
        raw_program_type = get_program_type_from_path(item.get('Path'))
        if raw_program_type: button_text += f" | {raw_program_type}"
        buttons.append([{'text': button_text, 'callback_data': f'm_detail_{search_id}_{start_index + i}_{user_id}'}])

    page_buttons = []
    if page > 1: page_buttons.append({'text': '◀️ 上一页', 'callback_data': f'm_page_{search_id}_{page-1}_{user_id}'})
    if end_index < len(results): page_buttons.append({'text': '下一页 ▶️', 'callback_data': f'm_page_{search_id}_{page+1}_{user_id}'})
    if page_buttons: buttons.append(page_buttons)

    if message_id: edit_telegram_message(chat_id, message_id, message_text, inline_buttons=buttons)
    else: send_deletable_telegram_notification(message_text, chat_id=chat_id, inline_buttons=buttons, delay_seconds=90)

def send_manage_detail(chat_id, search_id, item_index, user_id):
    """
    发送管理搜索结果的详细信息，并附带管理按钮。
    此函数基于 send_search_detail，增加了文件管理功能。
    :param chat_id: 聊天ID
    :param search_id: 搜索结果缓存ID
    :param item_index: 项目在缓存列表中的索引
    :param user_id: 用户ID
    """
    print(f"ℹ️ 正在发送管理详情，缓存 ID: {search_id}, 索引: {item_index}")
    if search_id not in SEARCH_RESULTS_CACHE or item_index >= len(SEARCH_RESULTS_CACHE[search_id]):
        send_deletable_telegram_notification("抱歉，此搜索结果已过期或无效。", chat_id=chat_id)
        return
    item_from_cache = SEARCH_RESULTS_CACHE[search_id][item_index]
    item_id = item_from_cache.get('Id')
    request_user_id = EMBY_USER_ID
    if not request_user_id:
        send_deletable_telegram_notification("错误：机器人管理员尚未设置 Emby `user_id`。", chat_id=chat_id)
        return
    full_item_url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items/{item_id}"
    params = {'api_key': EMBY_API_KEY, 'Fields': 'ProviderIds,Path,Overview,ProductionYear,ServerId,DateCreated'}
    response = make_request_with_retry('GET', full_item_url, params=params, timeout=10)
    if not response:
        send_deletable_telegram_notification("获取详细信息失败。", chat_id=chat_id)
        return
    item = response.json()
    item_type, raw_title, raw_overview = item.get('Type'), item.get('Name', '未知标题'), item.get('Overview', '暂无剧情简介')
    final_year = extract_year_from_path(item.get('Path')) or item.get('ProductionYear') or ''
    media_details = get_media_details(item, request_user_id)
    poster_url, tmdb_link = media_details.get('poster_url'), media_details.get('tmdb_link', '')
    message_parts = []
    prefix = 'movie' if item_type == 'Movie' else 'series'
    title_with_year = f"{raw_title} ({final_year})" if final_year else raw_title
    if tmdb_link and get_setting(f'settings.content_settings.search_display.{prefix}.title_has_tmdb_link'):
        message_parts.append(f"名称：[{escape_markdown(title_with_year)}]({tmdb_link})")
    else:
        message_parts.append(f"名称：*{escape_markdown(title_with_year)}*")
    if get_setting(f'settings.content_settings.search_display.{prefix}.show_type'):
        item_type_cn = "电影" if item_type == 'Movie' else "剧集"
        message_parts.append(f"类型：{escape_markdown(item_type_cn)}")
    raw_program_type = get_program_type_from_path(item.get('Path'))
    if raw_program_type and get_setting(f'settings.content_settings.search_display.{prefix}.show_category'):
        message_parts.append(f"分类：{escape_markdown(raw_program_type)}")
    if raw_overview and get_setting(f'settings.content_settings.search_display.{prefix}.show_overview'):
        overview_text = raw_overview[:150] + "..." if len(raw_overview) > 150 else raw_overview
        message_parts.append(f"剧情：{escape_markdown(overview_text)}")

    if item_type == 'Movie':
        stream_details = get_media_stream_details(item_id, request_user_id)
        formatted_parts = format_stream_details_message(stream_details, prefix='movie')
        if formatted_parts: message_parts.extend([escape_markdown(part) for part in formatted_parts])
        if get_setting('settings.content_settings.search_display.movie.show_added_time'):
            date_created_str = item.get('DateCreated')
            message_parts.append(f"入库时间：{escape_markdown(format_date(date_created_str))}")
    elif item_type == 'Series':
        season_info_list = get_series_season_media_info(item_id)
        if season_info_list:
            message_parts.append("各季规格：\n" + "\n".join([f"    {info}" for info in season_info_list]))
        latest_episode = _get_latest_episode_info(item_id)
        if latest_episode:
            message_parts.append("\u200b")
            if get_setting('settings.content_settings.search_display.series.update_progress.show_latest_episode'):
                s_num, e_num = latest_episode.get('ParentIndexNumber'), latest_episode.get('IndexNumber')
                update_info_raw = f"第 {s_num} 季 第 {e_num} 集" if s_num is not None and e_num is not None else "信息不完整"
                episode_media_details = get_media_details(latest_episode, EMBY_USER_ID)
                episode_tmdb_link = episode_media_details.get('tmdb_link')
                if episode_tmdb_link and get_setting('settings.content_settings.search_display.series.update_progress.latest_episode_has_tmdb_link'):
                    message_parts.append(f"已更新至：[{escape_markdown(update_info_raw)}]({episode_tmdb_link})")
                else:
                    message_parts.append(f"已更新至：{escape_markdown(update_info_raw)}")
            if get_setting('settings.content_settings.search_display.series.update_progress.show_overview'):
                episode_overview = latest_episode.get('Overview')
                if episode_overview:
                    overview_text = episode_overview[:100] + "..." if len(episode_overview) > 100 else episode_overview
                    message_parts.append(f"剧情：{escape_markdown(overview_text)}")
            if get_setting('settings.content_settings.search_display.series.update_progress.show_added_time'):
                message_parts.append(f"入库时间：{escape_markdown(format_date(latest_episode.get('DateCreated')))}")

            if get_setting('settings.content_settings.search_display.series.update_progress.show_progress_status'):
                series_tmdb_id = media_details.get('tmdb_id')
                local_s_num = latest_episode.get('ParentIndexNumber')
                local_e_num = latest_episode.get('IndexNumber')
                lines = build_seasonwise_progress_and_missing_lines(series_tmdb_id, item_id, local_s_num, local_e_num)
                if lines:
                    message_parts.extend(lines)

    final_poster_url = poster_url if poster_url and get_setting(f'settings.content_settings.search_display.{prefix}.show_poster') else None

    buttons = []
    if get_setting(f'settings.content_settings.search_display.{prefix}.show_view_on_server_button') and EMBY_REMOTE_URL:
        server_id = item.get('ServerId')
        if item_id and server_id:
            item_url = f"{EMBY_REMOTE_URL}/web/index.html#!/item?id={item_id}&serverId={server_id}"
            buttons.append([{'text': '➡️ 在服务器中查看', 'url': item_url}])

    buttons.append([{'text': '🔄 管理该节目', 'callback_data': f'm_files_{item_id}_{user_id}'}])
    buttons.append([{'text': '↩️ 退出管理', 'callback_data': f'm_exit_dummy_{user_id}'}])

    send_deletable_telegram_notification(
        "\n".join(filter(None, message_parts)),
        photo_url=final_poster_url, chat_id=chat_id,
        inline_buttons=buttons if buttons else None,
        delay_seconds=180
    )

def poll_telegram_updates():
    """轮询Telegram API获取更新。"""
    update_id = 0
    print("🤖 Telegram 命令轮询服务已启动...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {'offset': update_id + 1, 'timeout': 30}
            proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
            response = requests.get(url, params=params, timeout=40, proxies=proxies)
            if response.status_code == 200:
                updates = response.json().get('result', [])
                for update in updates:
                    update_id = update['update_id']
                    if 'message' in update:
                        message = update['message']
                        chat_id = message['chat']['id']
                        message_id = message['message_id']
                        
                        is_group_chat = chat_id < 0
                        should_delete = False
                        if not is_group_chat:
                            should_delete = True
                        else:
                            msg_text = message.get('text', '')
                            if msg_text.startswith('/'):
                                should_delete = True
                            elif 'reply_to_message' in message:
                                bot_id = int(TELEGRAM_TOKEN.split(':')[0])
                                if message['reply_to_message']['from']['id'] == bot_id:
                                    should_delete = True
                        
                        if should_delete:
                            delete_user_message_later(chat_id, message_id, delay_seconds=60)

                        handle_telegram_command(message)

                    elif 'callback_query' in update:
                        handle_callback_query(update['callback_query'])
            else:
                print(f"❌ 轮询 Telegram 更新失败: {response.status_code} - {response.text}")
                time.sleep(10)
        
        except requests.exceptions.RequestException as e:
            error_message = str(e)
            if TELEGRAM_TOKEN:
                error_message = error_message.replace(TELEGRAM_TOKEN, "[REDACTED_TOKEN]")
            print(f"❌ 轮询 Telegram 时网络错误: {error_message}")
            time.sleep(10)
            
        except Exception as e:
            print(f"❌ 处理 Telegram 更新时发生未处理错误: {e}")
            traceback.print_exc()
            time.sleep(5)

class WebhookHandler(BaseHTTPRequestHandler):
    """处理Emby Webhook请求的HTTP请求处理程序。"""

    def do_POST(self):
        """处理POST请求，解析并处理Emby事件。"""
        print("🔔 接收到 Webhook 请求。")
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data_bytes = self.rfile.read(content_length)

            content_type = self.headers.get('Content-Type', '').lower()
            json_string = None

            if 'application/json' in content_type:
                json_string = post_data_bytes.decode('utf-8')
            elif 'application/x-www-form-urlencoded' in content_type:
                parsed_form = parse_qs(post_data_bytes.decode('utf-8'))
                json_string = parsed_form.get('data', [None])[0]
            else:
                print(f"❌ 不支持的 Content-Type: {content_type}")
                self.send_response(400); self.end_headers()
                return

            if not json_string:
                print("❌ Webhook 请求中没有数据。")
                self.send_response(400); self.end_headers()
                return

            event_data = json.loads(unquote(json_string))
            print("\n--- Emby Webhook 推送内容开始 ---\n")
            print(json.dumps(event_data, indent=2, ensure_ascii=False))
            print("\n--- Emby Webhook 推送内容结束 ---\n")

            event_type = event_data.get('Event')
            item_from_webhook = event_data.get('Item', {}) or {}
            user = event_data.get('User', {}) or {}
            session = event_data.get('Session', {}) or {}
            playback_info = event_data.get('PlaybackInfo', {}) or {}
            print(f"ℹ️ 检测到 Emby 事件: {event_type}")
            
            if event_type == "library.new":
                if not any([
                    get_setting('settings.notification_management.library_new.to_group'),
                    get_setting('settings.notification_management.library_new.to_channel'),
                    get_setting('settings.notification_management.library_new.to_private')
                ]):
                    print("⚠️ 已关闭新增节目通知，跳过。")
                    self.send_response(204); self.end_headers()
                    return

                item = item_from_webhook
                stream_details = None

                if item.get('Id') and EMBY_USER_ID:
                    item_id = item.get("Id")
                    print(f"ℹ️ 正在轮询等待项目 {item_id} 刮削/分析完成…")
                    polled = fetch_library_item_with_poll(item_id)

                    # 只在 polled 返回了有效条目时才覆盖
                    if isinstance(polled, dict) and polled.get("Id"):
                        item = polled
                        print("✅ 补充元数据成功（轮询获取）。")
                    else:
                        print("⚠️ 轮询补充元数据失败，将使用 Webhook 原始数据。")

                media_details = get_media_details(item, event_data.get('User', {}).get('Id'))
                added_summary, added_list = parse_episode_ranges_from_description(event_data.get('Description', ''))

                if item.get('Type') == 'Series':
                    def sxxeyy_key(s_str):
                        match = re.match(r'S(\d+)E(\d+)', s_str, re.IGNORECASE)
                        if match:
                            return int(match.group(1)), int(match.group(2))
                        return 0, 0

                    if added_list:
                        print("🔍 规格查找策略 1: 检查本次新增的剧集...")
                        sorted_added_list = sorted(added_list, key=sxxeyy_key)
                        for ep_str in sorted_added_list:
                            s_num, e_num = sxxeyy_key(ep_str)
                            if s_num > 0 and e_num > 0:
                                episode_item = get_episode_item_by_number(item.get('Id'), s_num, e_num)
                                if episode_item:
                                    temp_details = get_media_stream_details(episode_item.get('Id'), EMBY_USER_ID)
                                    if temp_details:
                                        print(f"✅ 规格查找成功 (策略 1): 使用 {ep_str} 的规格。")
                                        stream_details = temp_details
                                        break
                    
                    if not stream_details and added_list:
                        print("🔍 规格查找策略 2: 检查同季的其他剧集...")
                        involved_seasons = sorted(list(set(sxxeyy_key(s)[0] for s in added_list if sxxeyy_key(s)[0] > 0)))
                        for s_num in involved_seasons:
                            episode_item = get_any_episode_from_season(item.get('Id'), s_num)
                            if episode_item:
                                temp_details = get_media_stream_details(episode_item.get('Id'), EMBY_USER_ID)
                                if temp_details:
                                    print(f"✅ 规格查找成功 (策略 2): 使用 S{s_num:02d} 中参考集 (ID: {episode_item.get('Id')}) 的规格。")
                                    stream_details = temp_details
                                    break
                    
                    if not stream_details:
                        print("🔍 规格查找策略 3: 回退至获取媒体库最新一集。")
                        episode_item = _get_latest_episode_info(item.get('Id'))
                        if episode_item:
                            stream_details = get_media_stream_details(episode_item.get('Id'), EMBY_USER_ID)
                            if stream_details:
                                s_num = episode_item.get('ParentIndexNumber', 0)
                                e_num = episode_item.get('IndexNumber', 0)
                                print(f"✅ 规格查找成功 (策略 3): 使用了媒体库最新集 S{s_num:02d}E{e_num:02d} (ID: {episode_item.get('Id')}) 的规格。")
                else:
                    print("ℹ️ 新增项目为电影/其他类型，准备延时以等待Emby分析媒体源...")
                    time.sleep(30)
                    print(f"🔍 规格查找策略 1: 尝试获取项目 {item.get('Name')} (ID: {item.get('Id')}) 的精确规格...")
                    stream_details = get_media_stream_details(item.get('Id'), None)
                    if stream_details:
                        print(f"✅ 规格查找成功 (策略 1): 成功获取项目 {item.get('Name')} (ID: {item.get('Id')}) 的规格。")

                if not stream_details and item.get('Type') == 'Episode':
                    season_num = item.get('ParentIndexNumber')
                    series_id = item.get('SeriesId')
                    if season_num is not None and series_id:
                        print(f"🔍 规格查找策略 2: 策略1失败，尝试查找 S{season_num:02d} 中其他剧集的规格作为参考...")
                        ref_episode_item = get_any_episode_from_season(series_id, season_num)
                        if ref_episode_item:
                            stream_details = get_media_stream_details(ref_episode_item.get('Id'), EMBY_USER_ID)
                            if stream_details:
                                print(f"✅ 规格查找成功 (策略 2): 使用了同季参考集 (ID: {ref_episode_item.get('Id')}) 的规格。")

                if not stream_details:
                    print("❌ 所有规格查找策略均失败，将发送不含规格的通知。")

                parts = []
                raw_episode_info = ""
                if item.get('Type') == 'Episode':
                    s, e, en = item.get('ParentIndexNumber'), item.get('IndexNumber'), item.get('Name')
                    raw_episode_info = f" S{s:02d}E{e:02d} {en or ''}" if s is not None and e is not None else f" {en or ''}"

                if item.get('Type') in ['Episode', 'Series', 'Season']:
                    raw_title = item.get('SeriesName', item.get('Name', '未知标题'))
                else:
                    raw_title = item.get('Name', '未知标题')

                title_with_year_and_episode = f"{raw_title} ({media_details.get('year')})" if media_details.get('year') else raw_title
                title_with_year_and_episode += raw_episode_info
                action_text = "✅ 新增"
                item_type_cn = "剧集" if item.get('Type') in ['Episode', 'Series', 'Season'] else "电影" if item.get('Type') == 'Movie' else ""

                if get_setting('settings.content_settings.new_library_notification.show_media_detail'):
                    if get_setting('settings.content_settings.new_library_notification.media_detail_has_tmdb_link') and media_details.get('tmdb_link'):
                        full_title_line = f"[{escape_markdown(title_with_year_and_episode)}]({media_details.get('tmdb_link')})"
                    else:
                        full_title_line = escape_markdown(title_with_year_and_episode)
                    parts.append(f"{action_text}{item_type_cn} {full_title_line}")
                else:
                    parts.append(f"{action_text}{item_type_cn}")

                if added_summary:
                    count_match = re.search(r'(\d+)\s*项目', (event_data.get('Title') or ''))
                    count_str = f"（共 {count_match.group(1)} 集）" if count_match else ""
                    parts.append(f"本次新增：{escape_markdown(added_summary)}{escape_markdown(count_str)}")

                if get_setting('settings.content_settings.new_library_notification.show_media_type'):
                    raw_program_type = get_program_type_from_path(item.get('Path'))
                    if raw_program_type:
                        parts.append(f"节目类型：{escape_markdown(raw_program_type)}")

                if get_setting('settings.content_settings.new_library_notification.show_overview'):
                    overview_text = (item.get("Overview") or "").strip() or "暂无剧情简介"
                    if overview_text:
                        overview_text = overview_text[:150] + "..." if len(overview_text) > 150 else overview_text
                        parts.append(f"剧情：{escape_markdown(overview_text)}")

                if stream_details:
                    formatted_specs = format_stream_details_message(stream_details, prefix='new_library_notification')
                    for part in formatted_specs:
                        parts.append(escape_markdown(part))

                if get_setting('settings.content_settings.new_library_notification.show_progress_status'):
                    progress_lines = build_progress_lines_for_library_new(item, media_details)
                    if progress_lines:
                        parts.extend(progress_lines)

                if get_setting('settings.content_settings.new_library_notification.show_timestamp'):
                    parts.append(f"入库时间：{escape_markdown(datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'))}")

                message = "\n".join(parts)
                photo_url = None
                if get_setting('settings.content_settings.new_library_notification.show_poster'):
                    photo_url = media_details.get('poster_url')

                buttons = []
                if get_setting('settings.content_settings.new_library_notification.show_view_on_server_button') and EMBY_REMOTE_URL:
                    item_id_, server_id = item.get('Id'), item.get('ServerId')
                    if item_id_ and server_id:
                        item_url = f"{EMBY_REMOTE_URL}/web/index.html#!/item?id={item_id_}&serverId={server_id}"
                        buttons.append([{'text': '➡️ 在服务器中查看', 'url': item_url}])

                auto_delete_group   = get_setting('settings.auto_delete_settings.new_library.to_group')
                auto_delete_channel = get_setting('settings.auto_delete_settings.new_library.to_channel')
                auto_delete_private = get_setting('settings.auto_delete_settings.new_library.to_private')

                if get_setting('settings.notification_management.library_new.to_group') and GROUP_ID:
                    print(f"✉️ 向群组 {GROUP_ID} 发送新增通知。")
                    if auto_delete_group:
                        send_deletable_telegram_notification(message, photo_url, chat_id=GROUP_ID, inline_buttons=buttons if buttons else None, delay_seconds=60)
                    else:
                        send_telegram_notification(message, photo_url, chat_id=GROUP_ID, inline_buttons=buttons if buttons else None)

                if get_setting('settings.notification_management.library_new.to_channel') and CHANNEL_ID:
                    print(f"✉️ 向频道 {CHANNEL_ID} 发送新增通知。")
                    if auto_delete_channel:
                        send_deletable_telegram_notification(message, photo_url, chat_id=CHANNEL_ID, inline_buttons=buttons if buttons else None, delay_seconds=60)
                    else:
                        send_telegram_notification(message, photo_url, chat_id=CHANNEL_ID, inline_buttons=buttons if buttons else None)

                if get_setting('settings.notification_management.library_new.to_private') and ADMIN_USER_ID:
                    print(f"✉️ 向管理员 {ADMIN_USER_ID} 发送新增通知。")
                    if auto_delete_private:
                        send_deletable_telegram_notification(message, photo_url, chat_id=ADMIN_USER_ID, inline_buttons=buttons if buttons else None, delay_seconds=60)
                    else:
                        send_telegram_notification(message, photo_url, chat_id=ADMIN_USER_ID, inline_buttons=buttons if buttons else None)

                self.send_response(200); self.end_headers()
                return

            if event_type == "library.deleted":
                if not get_setting('settings.notification_management.library_deleted'):
                    print("⚠️ 已关闭删除节目通知，跳过。")
                    self.send_response(204); self.end_headers()
                    return

                item = item_from_webhook
                item_type = item.get('Type')
                if item_type not in ['Movie', 'Series', 'Season', 'Episode']:
                    print(f"⚠️ 忽略不支持的删除事件类型: {item_type}")
                    self.send_response(204); self.end_headers()
                    return

                if item_type in ['Episode', 'Season'] and item.get('SeriesId'):
                    series_id = item.get('SeriesId')
                    try:
                        url = f"{EMBY_SERVER_URL}/Users/{EMBY_USER_ID}/Items/{series_id}"
                        params = {'api_key': EMBY_API_KEY, 'Fields': 'ProviderIds,Path,ProductionYear,ServerId'}
                        resp = make_request_with_retry('GET', url, params=params, timeout=10)
                        series_stub = resp.json() if resp else {}
                    except Exception:
                        series_stub = {}
                    media_details = get_media_details(series_stub or item, EMBY_USER_ID)
                    display_title = series_stub.get('Name') or item.get('SeriesName') or item.get('Name', '未知标题')
                    year = series_stub.get('ProductionYear') or extract_year_from_path((series_stub.get('Path') or item.get('Path') or ''))
                else:
                    media_details = get_media_details(item, EMBY_USER_ID)
                    display_title = item.get('Name', '未知标题')
                    year = item.get('ProductionYear') or extract_year_from_path(item.get('Path'))

                episode_info = ""
                if item_type == 'Episode':
                    s, e, en = item.get('ParentIndexNumber'), item.get('IndexNumber'), (item.get('Name') or '')
                    episode_info = f" S{s:02d}E{e:02d} {en or ''}" if s is not None and e is not None else f" {en or ''}"
                elif item_type == 'Season':
                    s = item.get('IndexNumber')
                    episode_info = f" 第 {s} 季" if s is not None else ""

                title_full = f"{display_title} ({year})" if year else display_title
                title_full += episode_info
                parts = []
                action_text = "🗑️ 删除"
                item_type_cn = "剧集" if item_type in ['Series', 'Season', 'Episode'] else "电影"

                if get_setting('settings.content_settings.library_deleted_notification.show_media_detail'):
                    if get_setting('settings.content_settings.library_deleted_notification.media_detail_has_tmdb_link') and media_details.get('tmdb_link'):
                        parts.append(f"{action_text}{item_type_cn} [{escape_markdown(title_full)}]({media_details.get('tmdb_link')})")
                    else:
                        parts.append(f"{action_text}{item_type_cn} {escape_markdown(title_full)}")
                else:
                    parts.append(f"{action_text}{item_type_cn}")

                if get_setting('settings.content_settings.library_deleted_notification.show_media_type'):
                    program_type = get_program_type_from_path(item.get('Path') or '')
                    if program_type:
                        parts.append(f"节目类型：{escape_markdown(program_type)}")

                deleted_summary, _ = parse_episode_ranges_from_description(event_data.get('Description', ''))
                if deleted_summary:
                    parts.append(f"已删除：{escape_markdown(deleted_summary)}")

                if get_setting('settings.content_settings.library_deleted_notification.show_overview'):
                    ov = (item.get('Overview') or '')[:150]
                    if ov:
                        parts.append(f"剧情：{escape_markdown(ov + ('...' if len(item.get('Overview') or '') > 150 else ''))}")

                if get_setting('settings.content_settings.library_deleted_notification.show_timestamp'):
                    now_str = datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
                    parts.append(f"删除时间：{escape_markdown(now_str)}")

                message = "\n".join(parts)
                photo_url = media_details.get('poster_url') if get_setting('settings.content_settings.library_deleted_notification.show_poster') else None

                if ADMIN_USER_ID:
                    auto_del = get_setting('settings.auto_delete_settings.library_deleted')
                    if auto_del:
                        send_deletable_telegram_notification(message, photo_url, chat_id=ADMIN_USER_ID, delay_seconds=60)
                    else:
                        send_telegram_notification(message, photo_url, chat_id=ADMIN_USER_ID)
                else:
                    print("⚠️ 删除通知跳过：未配置 ADMIN_USER_ID。")
                self.send_response(200); self.end_headers()
                return

            user_and_system_events = [
                "user.authenticated", "user.authenticationfailed", "user.created",
                "user.policyupdated", "user.passwordchanged", "user.deleted",
                "system.serverrestartrequired"
            ]

            if event_type in user_and_system_events:
                config_map = {
                    "user.authenticated": 'settings.notification_management.advanced.user_login_success',
                    "user.authenticationfailed": 'settings.notification_management.advanced.user_login_failure',
                    "user.created": 'settings.notification_management.advanced.user_creation_deletion',
                    "user.deleted": 'settings.notification_management.advanced.user_creation_deletion',
                    "user.policyupdated": 'settings.notification_management.advanced.user_updates',
                    "user.passwordchanged": 'settings.notification_management.advanced.user_updates',
                    "system.serverrestartrequired": 'settings.notification_management.advanced.server_restart_required',
                }
                
                config_path = config_map.get(event_type)
                if not config_path or not get_setting(config_path):
                    print(f"⚠️ 已关闭 {event_type} 事件通知，跳过。")
                    self.send_response(204); self.end_headers(); return

                if not ADMIN_USER_ID:
                    print(f"⚠️ 未配置 ADMIN_USER_ID，无法发送用户/系统事件通知。")
                    self.send_response(204); self.end_headers(); return
                
                time_str = get_event_time_str(event_data)
                parts = []
                icon = "ℹ️"
                custom_title = ""

                username = user.get('Name')
                if event_type == "user.authenticated":
                    icon = "✅"
                    custom_title = f"用户 {username} 已成功登录"
                    session_info = event_data.get("Session", {})
                    ip_address = session_info.get('RemoteEndPoint', '')
                    location = get_ip_geolocation(ip_address)
                    parts.append(f"客户端: {escape_markdown(session_info.get('Client'))}")
                    parts.append(f"设备: {escape_markdown(session_info.get('DeviceName'))}")
                    parts.append(f"位置: `{escape_markdown(ip_address)}` {escape_markdown(location)}")
                
                elif event_type == "user.authenticationfailed":
                    icon = "⚠️"
                    original_title = event_data.get("Title", "")
                    username_match = re.search(r'(?:来自|from)\s+(.+?)\s+(?:的登录|on)', original_title)
                    username = username_match.group(1).strip() if username_match else "未知"
                    custom_title = f"用户 {username} 登录失败"
                    desc_text = event_data.get("Description", "")
                    ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', desc_text)
                    ip_address = ip_match.group(1) if ip_match else "未知IP"
                    location = get_ip_geolocation(ip_address)
                    device_info = event_data.get("DeviceInfo", {})
                    parts.append(f"客户端: {escape_markdown(device_info.get('AppName'))}")
                    parts.append(f"设备: {escape_markdown(device_info.get('Name'))}")
                    parts.append(f"位置: `{escape_markdown(ip_address)}` {escape_markdown(location)}")
                
                    if username != "未知":
                        all_users = get_all_emby_users()
                        if username in all_users:
                            failure_reason = "失败原因：密码错误"
                        else:
                            failure_reason = "失败原因：用户不存在"
                        parts.append(escape_markdown(failure_reason))

                elif event_type == "user.created":
                    icon = "➕"
                    custom_title = f"用户 {username} 已成功创建"
                elif event_type == "user.deleted":
                    icon = "➖"
                    custom_title = f"用户 {username} 已删除"
                elif event_type == "user.policyupdated":
                    icon = "🔧"
                    custom_title = f"用户 {username} 的策略已更新"
                elif event_type == "user.passwordchanged":
                    icon = "🔧"
                    custom_title = f"用户 {username} 的密码已修改"
                elif event_type == "system.serverrestartrequired":
                    icon = "🔄"
                    custom_title = "服务器需要重启"
                    parts.append(escape_markdown(event_data.get("Title", "")))
                
                message_parts = [f"{icon} *{escape_markdown(custom_title)}*"]
                message_parts.extend(parts)
                if time_str != "未知":
                    message_parts.append(f"时间: {escape_markdown(time_str)}")
                    
                message = "\n".join(message_parts)

                autodelete_config_map = {
                    "user.authenticated": 'settings.auto_delete_settings.advanced.user_login',
                    "user.authenticationfailed": 'settings.auto_delete_settings.advanced.user_login',
                    "user.created": 'settings.auto_delete_settings.advanced.user_management',
                    "user.deleted": 'settings.auto_delete_settings.advanced.user_management',
                    "user.policyupdated": 'settings.auto_delete_settings.advanced.user_management',
                    "user.passwordchanged": 'settings.auto_delete_settings.advanced.user_management',
                    "system.serverrestartrequired": 'settings.auto_delete_settings.advanced.server_events',
                }
                autodelete_path = autodelete_config_map.get(event_type)

                if autodelete_path and get_setting(autodelete_path):
                    send_deletable_telegram_notification(message, chat_id=ADMIN_USER_ID, delay_seconds=180)
                else:
                    send_telegram_notification(message, chat_id=ADMIN_USER_ID)
                
                self.send_response(200); self.end_headers()
                return

            elif event_type in ["playback.start", "playback.unpause", "playback.stop", "playback.pause"]:
                event_key_map = {
                    'playback.start': 'playback_start',
                    'playback.unpause': 'playback_start',
                    'playback.stop': 'playback_stop',
                    'playback.pause': 'playback_pause'
                }
                notification_type = event_key_map.get(event_type)
                if not notification_type or not get_setting(f'settings.notification_management.{notification_type}'):
                    print(f"⚠️ 已关闭 {event_type} 通知，跳过。")
                    self.send_response(204); self.end_headers(); return

                if not ADMIN_USER_ID:
                    print("⚠️ 未配置 ADMIN_USER_ID，跳过发送播放通知。")
                    self.send_response(204); self.end_headers(); return

                if event_type in ["playback.start", "playback.unpause"]:
                    now = time.time()
                    event_key = ((user or {}).get('Id'), (item_from_webhook or {}).get('Id'))
                    if now - recent_playback_notifications.get(event_key, 0) < PLAYBACK_DEBOUNCE_SECONDS:
                        print(f"⏳ 忽略 {event_type} 事件，因为它发生在防抖时间 ({PLAYBACK_DEBOUNCE_SECONDS}秒) 内。")
                        self.send_response(204); self.end_headers(); return
                    recent_playback_notifications[event_key] = now

                item = item_from_webhook or {}
                media_details = get_media_details(item, (user or {}).get('Id'))
                stream_details = get_media_stream_details(item.get('Id'), (user or {}).get('Id'))

                raw_title = item.get('SeriesName') if item.get('Type') == 'Episode' else item.get('Name', '未知标题')
                raw_episode_info = ""
                if item.get('Type') == 'Episode':
                    s, e, en = item.get('ParentIndexNumber'), item.get('IndexNumber'), item.get('Name')
                    raw_episode_info = f" S{s:02d}E{e:02d} {en or ''}" if s is not None and e is not None else f" {en or ''}"

                title_with_year_and_episode = f"{raw_title} ({media_details.get('year')})" if media_details.get('year') else raw_title
                title_with_year_and_episode += raw_episode_info

                action_text_map = {
                    "playback.start": "▶️ 开始播放",
                    "playback.unpause": "▶️ 继续播放",
                    "playback.stop": "⏹️ 停止播放",
                    "playback.pause": "⏸️ 暂停播放"
                }
                action_text = action_text_map.get(event_type, "")
                item_type_cn = "剧集" if item.get('Type') in ['Episode', 'Series'] else ("电影" if item.get('Type') == 'Movie' else "")

                parts = []
                if get_setting('settings.content_settings.playback_action.show_media_detail'):
                    if get_setting('settings.content_settings.playback_action.media_detail_has_tmdb_link') and media_details.get('tmdb_link'):
                        full_title_line = f"[{escape_markdown(title_with_year_and_episode)}]({media_details.get('tmdb_link')})"
                    else:
                        full_title_line = escape_markdown(title_with_year_and_episode)
                    parts.append(f"{action_text}{item_type_cn} {full_title_line}")
                else:
                    parts.append(f"{action_text}{item_type_cn}")

                if get_setting('settings.content_settings.playback_action.show_user'):
                    parts.append(f"用户：{escape_markdown((user or {}).get('Name', '未知用户'))}")
                if get_setting('settings.content_settings.playback_action.show_player'):
                    parts.append(f"播放器：{escape_markdown((session or {}).get('Client', ''))}")
                if get_setting('settings.content_settings.playback_action.show_device'):
                    parts.append(f"设备：{escape_markdown((session or {}).get('DeviceName', ''))}")

                if get_setting('settings.content_settings.playback_action.show_location'):
                    ip = (session or {}).get('RemoteEndPoint', '').split(':')[0]
                    loc = get_ip_geolocation(ip)
                    if loc == "局域网":
                        parts.append(f"位置：{escape_markdown('局域网')}")
                    else:
                        parts.append(f"位置：`{escape_markdown(ip)}` {escape_markdown(loc)}")
                
                if get_setting('settings.content_settings.playback_action.show_progress'):
                    pos_ticks, run_ticks = (playback_info or {}).get('PositionTicks'), item.get('RunTimeTicks')
                    if pos_ticks is not None and run_ticks and run_ticks > 0:
                        percent = (pos_ticks / run_ticks) * 100
                        progress = (
                            f"进度：已观看 {percent:.1f}%"
                            if event_type == "playback.stop"
                            else f"进度：{percent:.1f}% ({format_ticks_to_hms(pos_ticks)} / {format_ticks_to_hms(run_ticks)})"
                        )
                        parts.append(escape_markdown(progress))

                if stream_details:
                    formatted_specs = format_stream_details_message(stream_details, prefix='playback_action')
                    for part in formatted_specs:
                        parts.append(escape_markdown(part))

                raw_program_type = get_program_type_from_path(item.get('Path'))
                if raw_program_type and get_setting('settings.content_settings.playback_action.show_media_type'):
                    parts.append(f"节目类型：{escape_markdown(raw_program_type)}")

                webhook_overview = item.get('Overview')
                if webhook_overview and get_setting('settings.content_settings.playback_action.show_overview'):
                    overview = webhook_overview[:150] + '...' if len(webhook_overview) > 150 else webhook_overview
                    parts.append(f"剧情：{escape_markdown(overview)}")

                if get_setting('settings.content_settings.playback_action.show_timestamp'):
                    parts.append(f"时间：{escape_markdown(datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'))}")

                message = "\n".join(parts)
                print(f"✉️ 向管理员 {ADMIN_USER_ID} 发送播放通知。")

                buttons = []
                photo_url = media_details.get('poster_url') if get_setting('settings.content_settings.playback_action.show_poster') else None
                if EMBY_REMOTE_URL and get_setting('settings.content_settings.playback_action.show_view_on_server_button'):
                    item_id, server_id = item.get('Id'), item.get('ServerId') or (event_data.get('Server', {}).get('Id') if event_data else None)
                    if item_id and server_id:
                        buttons.append([{'text': '➡️ 在服务器中查看', 'url': f"{EMBY_REMOTE_URL}/web/index.html#!/item?id={item_id}&serverId={server_id}"}])

                auto_delete_path_map = {
                    'playback.start': 'settings.auto_delete_settings.playback_start',
                    'playback.unpause': 'settings.auto_delete_settings.playback_start',
                    'playback.pause': 'settings.auto_delete_settings.playback_pause',
                    'playback.stop': 'settings.auto_delete_settings.playback_stop'
                }
                auto_delete_path = auto_delete_path_map.get(event_type)
                if auto_delete_path and get_setting(auto_delete_path):
                    send_deletable_telegram_notification(
                        message, photo_url, chat_id=ADMIN_USER_ID,
                        inline_buttons=buttons if buttons else None, delay_seconds=60
                    )
                else:
                    send_telegram_notification(
                        message, photo_url, chat_id=ADMIN_USER_ID,
                        inline_buttons=buttons if buttons else None
                    )

                self.send_response(200); self.end_headers(); return

            else:
                print(f"ℹ️ 未处理的事件类型：{event_type}")
                self.send_response(204); self.end_headers()
                return

        except Exception as e:
            print(f"❌ 处理 Webhook 时发生错误: {e}")
            traceback.print_exc()
            self.send_response(500)
            self.end_headers()

class QuietWebhookHandler(WebhookHandler):
    """一个安静的Webhook处理程序，不打印常规的HTTP日志。"""
    def log_message(self, format, *args):
        pass

def run_server(server_class=HTTPServer, handler_class=WebhookHandler, port=8080):
    """启动HTTP服务器。"""
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"🚀 服务器已在 http://0.0.0.0:{port} 启动...")
    httpd.serve_forever()

if __name__ == '__main__':
    if not EMBY_USER_ID:
        print("="*60 + "\n⚠️ 严重警告：在 config.yaml 中未找到 'user_id' 配置。\n 这可能导致部分需要用户上下文的 Emby API 请求失败。\n 强烈建议配置一个有效的用户ID以确保所有功能正常运作。\n" + "="*60)

    telegram_poll_thread = threading.Thread(target=poll_telegram_updates, daemon=True)
    telegram_poll_thread.start()

    run_server(handler_class=QuietWebhookHandler)
