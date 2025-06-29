import sys
import re
import time
import traceback
from datetime import datetime

import requests
import pytz
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QTextEdit, QLabel, QSplitter, QStatusBar,
    QProgressBar, QFrame, QGridLayout, QTabWidget, QScrollArea,
    QGroupBox, QComboBox, QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QFont, QPalette, QColor, QIcon, QPixmap, QPainter, QPen
from PyQt6.QtSvgWidgets import QSvgWidget


# --- 样式表 --- 
STYLESHEET = """
QWidget {
    background-color: #2E3440;
    color: #D8DEE9;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 14px;
}
QMainWindow {
    border: 1px solid #4C566A;
}
QLineEdit {
    background-color: #3B4252;
    border: 1px solid #4C566A;
    border-radius: 6px;
    padding: 10px;
    color: #ECEFF4;
    font-size: 14px;
}
QLineEdit:focus {
    border: 2px solid #88C0D0;
    background-color: #434C5E;
}
QPushButton {
    background-color: #5E81AC;
    color: #ECEFF4;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 14px;
}
QPushButton:hover {
    background-color: #81A1C1;
    transform: translateY(-1px);
}
QPushButton:pressed {
    background-color: #88C0D0;
}
QPushButton#clearButton {
    background-color: #BF616A;
}
QPushButton#clearButton:hover {
    background-color: #D08770;
}
QTextEdit {
    background-color: #3B4252;
    border: 1px solid #4C566A;
    border-radius: 6px;
    color: #D8DEE9;
    padding: 8px;
}
QLabel#titleLabel {
    font-size: 18px;
    font-weight: bold;
    color: #88C0D0;
    padding-bottom: 10px;
}
QLabel#statsLabel {
    font-size: 12px;
    color: #A3BE8C;
    padding: 5px;
    background-color: #3B4252;
    border-radius: 4px;
    border: 1px solid #4C566A;
}
QStatusBar {
    background-color: #3B4252;
    color: #D8DEE9;
    border-top: 1px solid #4C566A;
}
QSplitter::handle {
    background-color: #4C566A;
    height: 3px;
}
QSplitter::handle:hover {
    background-color: #5E81AC;
}
QProgressBar {
    border: 1px solid #4C566A;
    border-radius: 4px;
    text-align: center;
    background-color: #3B4252;
    color: #D8DEE9;
}
QProgressBar::chunk {
    background-color: #A3BE8C;
    border-radius: 3px;
}
QGroupBox {
    font-weight: bold;
    border: 2px solid #4C566A;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    color: #88C0D0;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px 0 5px;
}
QTabWidget::pane {
    border: 1px solid #4C566A;
    background-color: #3B4252;
}
QTabBar::tab {
    background-color: #434C5E;
    color: #D8DEE9;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: #5E81AC;
    color: #ECEFF4;
}
QTabBar::tab:hover {
    background-color: #4C566A;
}
QComboBox {
    background-color: #3B4252;
    border: 1px solid #4C566A;
    border-radius: 4px;
    padding: 5px;
    color: #D8DEE9;
}
QComboBox:hover {
    border: 1px solid #88C0D0;
}
QComboBox::drop-down {
    border: none;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #D8DEE9;
}
QCheckBox {
    color: #D8DEE9;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #4C566A;
    border-radius: 3px;
    background-color: #3B4252;
}
QCheckBox::indicator:checked {
    background-color: #A3BE8C;
    border: 1px solid #A3BE8C;
}
QSpinBox {
    background-color: #3B4252;
    border: 1px solid #4C566A;
    border-radius: 4px;
    padding: 5px;
    color: #D8DEE9;
}
QFrame#separatorLine {
    background-color: #4C566A;
    max-height: 1px;
    min-height: 1px;
}
"""

# --- METAR 解析器 --- 
class METARParser:
    WEATHER_PHENOMENA = {
        'MI': '浅', 'BC': '散', 'PR': '部分', 'DR': '低吹', 'BL': '高吹', 'SH': '阵性', 'TS': '雷暴', 'FZ': '冻',
        'DZ': '毛毛雨', 'RA': '雨', 'SN': '雪', 'SG': '米雪', 'PL': '冰丸', 'GR': '雹', 'GS': '小雹',
        'UP': '不明降水', 'BR': '轻雾', 'FG': '雾', 'FU': '烟', 'VA': '火山灰', 'DU': '尘', 'SA': '沙', 'HZ': '霾',
        'PO': '尘/沙旋风', 'SQ': '飑', 'FC': '漏斗云', 'SS': '沙暴', 'DS': '尘暴',
        'TSRA': '雷雨', 'TSSN': '雷雪', 'TSPL': '雷阵冰丸', 'TSGR': '雷阵雹', 'TSGS': '雷阵小冰雹',
        'SHRA': '阵雨', 'SHSN': '阵雪', 'SHGR': '阵雹', 'SHGS': '阵小冰雹',
        'FZRA': '冻雨', 'FZDZ': '冻毛毛雨', 'FZUP': '未知冻雨',
        'VCTS': '附近雷暴', 'VCSH': '附近阵雨'
    }

    def translate_cloud_cover(self, code):
        return {
            'FEW': '少云 (1-2成)', 'SCT': '疏云 (3-4成)', 'BKN': '多云 (5-7成)',
            'OVC': '阴天 (8成)', 'NSC': '无重要云', 'NCD': '无云'
        }.get(code, code)

    def translate_weather_phenomena(self, code):
        code_to_parse = code.replace('+', '').replace('-', '').replace('VC', '')
        desc = ''
        i = 0
        while i < len(code_to_parse):
            if i + 4 <= len(code_to_parse) and code_to_parse[i:i+4] in self.WEATHER_PHENOMENA:
                desc += self.WEATHER_PHENOMENA[code_to_parse[i:i+4]]
                i += 4
            elif i + 2 <= len(code_to_parse) and code_to_parse[i:i+2] in self.WEATHER_PHENOMENA:
                desc += self.WEATHER_PHENOMENA[code_to_parse[i:i+2]]
                i += 2
            else:
                i += 2
        final_desc = desc.strip()
        if code.startswith('+'): final_desc = '强 ' + final_desc
        if code.startswith('-'): final_desc = '弱 ' + final_desc
        if 'VC' in code: final_desc = '附近 ' + final_desc
        return final_desc if final_desc else code

    def parse_wind(self, wind_code, is_trend=False):
        unit_str = '米/秒' if 'MPS' in wind_code else '节'

        if 'VRB' in wind_code:
            speed_match = re.search(r'VRB(\d{2,3})', wind_code)
            if speed_match:
                speed = int(speed_match.group(1))
                return f'风向不定, 风速 {speed}{unit_str}'
            return wind_code  # 无法解析

        # 匹配 风向/风速/阵风
        match = re.match(r'(\d{3})(\d{2,3})(G\d{2,3})?', wind_code)
        if not match:
            return wind_code  # 无法解析则返回原始代码

        direction_str = match.group(1)
        speed = int(match.group(2))
        gust_part = match.group(3)

        if direction_str == '000' and speed == 0:
            return '静风'

        desc = f'风向 {direction_str}度, 风速 {speed}{unit_str}'
        if gust_part:
            gust_speed = int(gust_part[1:])  # 移除 'G'
            desc += f', 阵风 {gust_speed}{unit_str}'

        return desc

    def parse(self, metar_line):
        if not metar_line: return []
        parts = {
            '原始报文': metar_line,
            '场站': '', '观测时间': '', '风': '', '能见度': '', '天气现象': '',
            '云况': '', '温度/露点': '', '气压': '', '跑道视程': '',
            '趋势预报': '', '近期天气': '', '风切变': '', '备注': ''
        }

        # 场站
        station_match = re.search(r'^([A-Z]{4})', metar_line)
        if station_match: parts['场站'] = station_match.group(1)

        # 时间
        time_match = re.search(r'(\d{2})(\d{2})(\d{2})Z', metar_line)
        if time_match: parts['观测时间'] = f'{time_match.group(1)}日 {time_match.group(2)}:{time_match.group(3)} UTC'

        # 风
        wind_match = re.search(r' ((\d{3}|VRB|00000KT)\d{2,3}(G\d{2,3})?(KT|MPS)) ',
                               metar_line)
        if wind_match:
            wind_code = wind_match.group(1)
            # 针对静风的特殊处理
            if wind_code == '00000KT':
                parts['风'] = '静风 (00000KT)'
            else:
                parts['风'] = f'{self.parse_wind(wind_code)} ({wind_code})'

        # 能见度
        vis_match = re.search(r' (\d{4}) ', metar_line)
        if vis_match: parts['能见度'] = f'{vis_match.group(1)}米'
        elif 'CAVOK' in metar_line: parts['能见度'] = 'CAVOK (云和能见度都良好)'

        # 天气现象 (改进正则，处理更复杂的情况)
        weather_match = re.search(r' ((-|\+)?(VC)?(MI|BC|PR|DR|BL|SH|TS|FZ)?([A-Z]{2}){1,3}) ', metar_line)
        if weather_match:
            full_code = weather_match.group(1)
            # 避免将云码错误识别为天气现象
            if full_code not in ['FEW', 'SCT', 'BKN', 'OVC', 'NSC']:
                parts['天气现象'] = f'{self.translate_weather_phenomena(full_code)} ({full_code})'

        # 云
        cloud_matches = re.findall(r' (FEW|SCT|BKN|OVC|VV)(\d{3})(CB|TCU)?', metar_line)
        if cloud_matches:
            cloud_info_parts = []
            for c in cloud_matches:
                if c[0] == 'VV':
                    cloud_info_parts.append(f'垂直能见度 {int(c[1])*100}英尺')
                else:
                    cloud_info_parts.append(
                        f'{self.translate_cloud_cover(c[0])} at {int(c[1])*100}英尺' + (f' ({c[2]})' if c[2] else '')
                    )
            parts['云况'] = ', '.join(cloud_info_parts)
        elif 'NSC' in metar_line:
            parts['云况'] = '无重要云 (NSC)'
        elif 'NCD' in metar_line:
            parts['云况'] = '无云 (NCD)'

        # 温度/露点
        temp_dew_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar_line)
        if temp_dew_match:
            temp = temp_dew_match.group(1).replace('M', '-')
            dew = temp_dew_match.group(2).replace('M', '-')
            parts['温度/露点'] = f'温度 {temp}°C, 露点 {dew}°C'

        # 气压
        pressure_match = re.search(r' Q(\d{4})', metar_line)
        if pressure_match: parts['气压'] = f'{pressure_match.group(1)} hPa'

        # RVR
        rvr_matches = re.findall(r' R(\d{2}[RLC]?)/([PM]?\d{4})', metar_line)
        if rvr_matches:
            rvr_info = ', '.join([f'跑道 {r[0]}: {r[1]}米' for r in rvr_matches])
            parts['跑道视程'] = rvr_info

        # 趋势预报 
        trend_part_match = re.search(r' (NOSIG|BECMG.*|TEMPO.*)', metar_line)
        if trend_part_match:
            trend_full_string = trend_part_match.group(1).strip()
            if 'NOSIG' in trend_full_string:
                parts['趋势预报'] = '无显著变化 (NOSIG)'
            else:
                trend_blocks = re.findall(r'(BECMG|TEMPO)(.*?)(?=\sBECMG|\sTEMPO|$)', trend_full_string)
                full_trend_desc = []
                for trend_type, trend_content in trend_blocks:
                    details = self.parse_trend(trend_type, trend_content.strip())
                    full_trend_desc.append('<br>'.join(details))
                parts['趋势预报'] = '<br>'.join(full_trend_desc)

        # 近期天气
        recent_weather_match = re.search(r' RE([A-Z]{2,8}) ', metar_line)
        if recent_weather_match:
            code = recent_weather_match.group(1)
            parts['近期天气'] = f'{self.translate_weather_phenomena(code)} ({code})'

        # 风切变
        windshear_match = re.search(r' WS (ALL RWY|RWY(\d{2}[RLC]?))', metar_line)
        if windshear_match:
            ws_info = '所有跑道' if windshear_match.group(1) == 'ALL RWY' else f'跑道 {windshear_match.group(2)}'
            parts['风切变'] = ws_info

        # 备注
        rmk_match = re.search(r' RMK .+', metar_line)
        if rmk_match: parts['备注'] = rmk_match.group(0)

        return {k: v for k, v in parts.items() if v}

    def parse_trend(self, trend_type, trend_content):
        details = [f'<b>{trend_type}:</b>']
        remaining_content = trend_content

        # 时间
        time_match = re.search(r'(FM|TL|AT)(\d{4})', remaining_content)
        if time_match:
            time_desc = {'FM': '从', 'TL': '直到', 'AT': '在'}[time_match.group(1)]
            time_str = time_match.group(2)
            details.append(f"- 时间: {time_desc} {time_str[0:2]}:{time_str[2:4]} UTC")
            remaining_content = remaining_content.replace(time_match.group(0), '').strip()

        # 风
        wind_match = re.search(r'((\d{3}|VRB)\d{2,3}(G\d{2,3})?(KT|MPS))', remaining_content)
        if wind_match:
            wind_code = wind_match.group(1)
            details.append(f'- 风: {self.parse_wind(wind_code, is_trend=True)}')
            remaining_content = remaining_content.replace(wind_code, '').strip()

        # 能见度
        vis_match = re.search(r' (\d{4}) ', f' {remaining_content} ')
        if vis_match:
            details.append(f'- 能见度: {vis_match.group(1)}米')
            remaining_content = remaining_content.replace(vis_match.group(1), '').strip()
        elif 'CAVOK' in remaining_content:
            details.append('- 能见度: CAVOK')
            remaining_content = remaining_content.replace('CAVOK', '').strip()

        # 云
        cloud_matches = re.findall(r'(FEW|SCT|BKN|OVC)(\d{3})(CB|TCU)?', remaining_content)
        if cloud_matches:
            cloud_descs = []
            for match in cloud_matches:
                cloud_descs.append(f'{self.translate_cloud_cover(match[0])} at {int(match[1])*100}英尺' + (f' ({match[2]})' if match[2] else ''))
                remaining_content = remaining_content.replace(''.join(match), '').strip()
            details.append(f'- 云: {", ".join(cloud_descs)}')

        # 天气
        weather_codes = re.findall(r'(-|\+|VC)?([A-Z]{2,4})', remaining_content)
        if weather_codes:
            weather_descs = []
            for code in weather_codes:
                full_code = ''.join(filter(None, code))
                if full_code not in ['BECMG', 'TEMPO', 'FM', 'TL', 'AT', 'KT', 'MPS', 'NSC'] and not full_code.isdigit():
                    weather_descs.append(self.translate_weather_phenomena(full_code))
            if weather_descs:
                details.append(f'- 天气: {", ".join(weather_descs)}')

        return details


# --- 统计面板类 ---
class StatsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.reset_stats()
        
    def init_ui(self):
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # 统计标签
        self.total_requests_label = QLabel("总请求: 0")
        self.successful_requests_label = QLabel("成功: 0")
        self.failed_requests_label = QLabel("失败: 0")
        self.success_rate_label = QLabel("成功率: 0%")
        self.last_update_label = QLabel("最后更新: 未知")
        
        # 设置样式
        for label in [self.total_requests_label, self.successful_requests_label, 
                     self.failed_requests_label, self.success_rate_label, self.last_update_label]:
            label.setObjectName("statsLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 布局
        layout.addWidget(self.total_requests_label, 0, 0)
        layout.addWidget(self.successful_requests_label, 0, 1)
        layout.addWidget(self.failed_requests_label, 1, 0)
        layout.addWidget(self.success_rate_label, 1, 1)
        layout.addWidget(self.last_update_label, 2, 0, 1, 2)
        
        self.setLayout(layout)
        
    def reset_stats(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.update_display()
        
    def add_request(self, success=True):
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        self.update_display()
        
    def update_display(self):
        self.total_requests_label.setText(f"总请求: {self.total_requests}")
        self.successful_requests_label.setText(f"成功: {self.successful_requests}")
        self.failed_requests_label.setText(f"失败: {self.failed_requests}")
        
        if self.total_requests > 0:
            success_rate = (self.successful_requests / self.total_requests) * 100
            self.success_rate_label.setText(f"成功率: {success_rate:.1f}%")
        else:
            self.success_rate_label.setText("成功率: 0%")
            
        current_time = datetime.now().strftime("%H:%M:%S")
        self.last_update_label.setText(f"最后更新: {current_time}")

# --- METAR 查找线程 ---
class MetarFinderThread(QThread):
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    
    def __init__(self, icao_code):
        super().__init__()
        self.icao_code = icao_code
    
    def run(self):
        try:
            # 开始进度
            self.progress_updated.emit(10)
            
            # 构建URL
            url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{self.icao_code.upper()}.TXT"
            self.progress_updated.emit(30)
            
            # 发送请求
            response = requests.get(url, timeout=10)
            self.progress_updated.emit(70)
            response.raise_for_status()
            
            # 解析响应
            lines = response.text.strip().split('\n')
            self.progress_updated.emit(90)
            
            if len(lines) >= 2:
                # 第一行是时间戳，第二行是METAR数据
                timestamp = lines[0]
                metar_data = lines[1]
                
                result = f"时间戳: {timestamp}\nMETAR数据: {metar_data}"
                self.progress_updated.emit(100)
                self.result_ready.emit(result)
            else:
                self.error_occurred.emit("无效的METAR数据格式")
                
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"网络请求失败: {str(e)}")
        except Exception as e:
            self.error_occurred.emit(f"未知错误: {str(e)}")

# --- 后台下载线程 (使用同步请求) ---
class DownloaderThread(QThread):
    log_signal = pyqtSignal(str)
    update_complete_signal = pyqtSignal(int)
    metar_data = {}

    def run(self):
        while True:
            self.download_metar_file()
            self.log_signal.emit("60秒后开始下一次下载周期。")
            time.sleep(60)

    def download_metar_file(self):
        start_time = datetime.now()
        self.log_signal.emit("开始下载数据......")
        try:
            utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
            file_name = f"{utc_time.hour:02d}Z.TXT"
            self.log_signal.emit(f"尝试下载文件: {file_name}")
            url = f"https://tgftp.nws.noaa.gov/data/observations/metar/cycles/{file_name}"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            raw_data = response.text
            lines = raw_data.split('\n')
            pattern = re.compile(r"^[A-Z]{4} ")
            metar_lines = [line for line in lines if pattern.match(line) and len(line.split()) > 1]
            for line in metar_lines:
                station = line.split()[0]
                self.metar_data[station] = line
            self.update_complete_signal.emit(len(metar_lines))
            self.log_signal.emit("本地数据缓存已更新。")
        except Exception as e:
            self.log_signal.emit(f"下载错误: {e}")
        finally:
            elapsed = (datetime.now() - start_time).total_seconds()
            self.log_signal.emit(f"本次下载周期完成，耗时: {elapsed:.2f} 秒。")

# --- 主窗口 ---
class MetarApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("METAR 实时解析工具")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet(STYLESHEET)
        self.parser = METARParser()
        self.init_ui()
        self.start_downloader()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 标题和统计面板
        header_layout = QHBoxLayout()
        
        # 标题
        title_label = QLabel("METAR 实时解析工具")
        title_label.setObjectName("titleLabel")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # 统计面板
        self.stats_panel = StatsPanel()
        stats_group = QGroupBox("统计信息")
        stats_layout = QVBoxLayout()
        stats_layout.addWidget(self.stats_panel)
        stats_group.setLayout(stats_layout)
        stats_group.setMaximumWidth(300)
        header_layout.addWidget(stats_group)
        
        main_layout.addLayout(header_layout)
        
        # 分隔线
        separator = QFrame()
        separator.setObjectName("separatorLine")
        separator.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(separator)

        # 搜索栏
        search_group = QGroupBox("查询设置")
        search_layout = QVBoxLayout()
        
        # 第一行：输入和按钮
        first_row = QHBoxLayout()
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("输入ICAO代码 (多个用逗号隔开)...")
        self.search_entry.returnPressed.connect(self.search_metar)
        search_button = QPushButton("🔍 查询 METAR")
        search_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #5E81AC, stop: 1 #81A1C1);
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #81A1C1, stop: 1 #88C0D0);
            }
            QPushButton:pressed {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #4C566A, stop: 1 #5E81AC);
            }
        """)
        search_button.clicked.connect(self.search_metar)
        clear_button = QPushButton("清空结果")
        clear_button.setObjectName("clearButton")
        clear_button.clicked.connect(self.clear_results)
        
        first_row.addWidget(QLabel("机场代码:"))
        first_row.addWidget(self.search_entry)
        first_row.addWidget(search_button)
        first_row.addWidget(clear_button)
        search_layout.addLayout(first_row)
        
        # 第二行：选项
        second_row = QHBoxLayout()
        self.save_history_check = QCheckBox("保存历史")
        self.save_history_check.setChecked(True)
        
        second_row.addWidget(self.save_history_check)
        second_row.addStretch()
        search_layout.addLayout(second_row)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #4C566A;
                border-radius: 5px;
                text-align: center;
                background-color: #3B4252;
                color: #E5E9F0;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                                          stop: 0 #A3BE8C, stop: 1 #88C0D0);
                border-radius: 3px;
            }
        """)
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        search_layout.addWidget(self.progress_bar)
        
        search_group.setLayout(search_layout)
        main_layout.addWidget(search_group)

        # 选项卡区域
        self.tab_widget = QTabWidget()
        
        # 解析结果选项卡
        result_tab = QWidget()
        result_layout = QVBoxLayout()
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        result_layout.addWidget(self.result_text)
        result_tab.setLayout(result_layout)
        self.tab_widget.addTab(result_tab, "📋 详细结果")
        

        
        # 系统日志选项卡
        log_tab = QWidget()
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        log_layout.addWidget(self.log_text)
        log_tab.setLayout(log_layout)
        self.tab_widget.addTab(log_tab, "系统日志")
        
        # 历史记录选项卡
        history_tab = QWidget()
        history_layout = QVBoxLayout()
        self.history_text = QTextEdit()
        self.history_text.setPlaceholderText("查询历史将在这里显示...")
        self.history_text.setReadOnly(True)
        history_layout.addWidget(self.history_text)
        history_tab.setLayout(history_layout)
        self.tab_widget.addTab(history_tab, "历史记录")
        
        main_layout.addWidget(self.tab_widget)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 添加状态指示器
        self.connection_status = QLabel("🔴 离线")
        self.connection_status.setStyleSheet("color: #BF616A; font-weight: bold;")
        self.status_bar.addPermanentWidget(self.connection_status)
        
        self.data_count_label = QLabel("数据: 0 条")
        self.data_count_label.setStyleSheet("color: #88C0D0; font-weight: bold;")
        self.status_bar.addPermanentWidget(self.data_count_label)
        
        self.time_label = QLabel()
        self.time_label.setStyleSheet("color: #A3BE8C; font-weight: bold;")
        self.status_bar.addPermanentWidget(self.time_label)
        
        # 创建定时器更新时间
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)  # 每秒更新
        
        # 初始化时更新连接状态
        self.update_connection_status()
        
        # 历史记录
        self.query_history = []
        
    def create_app_icon(self):
        """创建应用程序图标"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制简单的飞机图标
        painter.setPen(QPen(QColor("#88C0D0"), 2))
        painter.setBrush(QColor("#5E81AC"))
        
        # 机身
        painter.drawEllipse(8, 12, 16, 8)
        # 机翼
        painter.drawEllipse(4, 14, 24, 4)
        # 尾翼
        painter.drawEllipse(10, 8, 12, 4)
        
        painter.end()
        return QIcon(pixmap)
        
    def update_time(self):
        """更新状态栏时间显示"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_label.setText(f"⏰ {current_time}")
        
    def update_connection_status(self):
        """更新连接状态"""
        try:
            # 简单的网络连接测试
            response = requests.get("https://tgftp.nws.noaa.gov/data/observations/metar/stations/", timeout=3)
            if response.status_code == 200:
                self.connection_status.setText("🟢 在线")
                self.connection_status.setStyleSheet("color: #A3BE8C; font-weight: bold;")
            else:
                self.connection_status.setText("🟡 连接异常")
                self.connection_status.setStyleSheet("color: #EBCB8B; font-weight: bold;")
        except:
            self.connection_status.setText("🔴 离线")
            self.connection_status.setStyleSheet("color: #BF616A; font-weight: bold;")
            
    def update_data_count(self, count):
        """更新数据计数显示"""
        self.data_count_label.setText(f"📊 数据: {count} 条")

    def start_downloader(self):
        self.downloader = DownloaderThread()
        self.downloader.log_signal.connect(self.update_log)
        self.downloader.update_complete_signal.connect(self.on_update_complete)
        self.downloader.start()
        self.status_bar.showMessage("正在启动后台下载...")

    def update_log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        self.status_bar.showMessage(message, 5000)

    def on_update_complete(self, count):
        self.status_bar.showMessage(f"数据缓存已更新，共 {count} 条记录。", 10000)
        self.update_data_count(count)
        self.update_connection_status()
        # 切换到日志选项卡显示更新信息
        if hasattr(self, 'tab_widget'):
            self.tab_widget.setCurrentIndex(1)  # 切换到日志选项卡

    def clear_results(self):
        """清空所有结果显示区域"""
        self.result_text.clear()
        self.history_text.clear()
        self.query_history.clear()
        self.stats_panel.reset_stats()
        self.status_bar.showMessage("结果已清空", 3000)
        

        self.tab_widget.setCurrentIndex(0)  # 切换到结果选项卡

    def search_metar(self):
        query = self.search_entry.text().upper().strip()
        if not query:
            self.status_bar.showMessage("请输入ICAO代码", 5000)
            return

        icao_codes = [code.strip() for code in query.split(',')]
        
        # 显示进度条和状态
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(icao_codes))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"准备查询 {len(icao_codes)} 个机场... %p%")
        
        # 禁用搜索按钮防止重复点击
        if hasattr(self, 'search_button'):
            self.search_button.setEnabled(False)
            self.search_button.setText("🔄 查询中...")
        
        self.status_bar.showMessage(f"正在查询 {len(icao_codes)} 个机场的METAR数据...")
        
        # 强制刷新界面
        QApplication.processEvents()
        
        try:
            # 添加到历史记录
            if self.save_history_check.isChecked():
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                history_entry = f"[{timestamp}] 查询: {', '.join(icao_codes)}"
                self.query_history.append(history_entry)
                self.update_history_display()
            
            self.display_metar(icao_codes)
            
        except Exception as e:
            self.status_bar.showMessage(f"查询失败: {str(e)}", 5000)
        
        finally:
            # 恢复界面状态
            self.progress_bar.setVisible(False)
            if hasattr(self, 'search_button'):
                self.search_button.setEnabled(True)
                self.search_button.setText("🔍 查询 METAR")

    def update_history_display(self):
        """更新历史记录显示"""
        history_html = "<h3 style='color:#8FBCBB;'>查询历史</h3>"
        for entry in self.query_history[-20:]:  # 只显示最近20条
            history_html += f"<p style='color:#D8DEE9; margin: 5px 0;'>{entry}</p>"
        self.history_text.setHtml(history_html)

    def display_metar(self, icao_codes):
        html_content = "<div style='font-family: Segoe UI, Arial, sans-serif;'>"
        html_content += f"<h2 style='color:#88C0D0; text-align: center; margin-bottom: 20px;'>📊 METAR 查询结果</h2>"
        success_count = 0
        
        for i, code in enumerate(icao_codes):
            # 更新进度条
            if hasattr(self, 'progress_bar') and self.progress_bar.isVisible():
                self.progress_bar.setValue(i)
                QApplication.processEvents()  # 刷新界面
            
            metar_line = self.downloader.metar_data.get(code)
            
            # 添加卡片样式的容器
            card_style = "background: linear-gradient(135deg, #3B4252 0%, #434C5E 100%); border: 1px solid #4C566A; border-radius: 8px; padding: 15px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"
            html_content += f"<div style='{card_style}'>"
            
            if metar_line:
                success_count += 1
                # 成功图标和标题
                html_content += f"<h3 style='color:#A3BE8C; margin: 0 0 10px 0;'>✅ {code} - 查询成功</h3>"
                
                parsed_data = self.parser.parse(metar_line)
                
                # 原始报文
                html_content += f"<div style='background-color: #2E3440; border-left: 4px solid #A3BE8C; padding: 10px; margin: 10px 0; border-radius: 4px;'>"
                html_content += f"<p style='font-family: Consolas, monospace; color: #A3BE8C; margin: 0; font-size: 13px;'><strong>原始报文:</strong><br>{parsed_data.get('原始报文', '')}</p>"
                html_content += "</div>"
                
                # 解析结果表格
                html_content += "<table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>"
                for key, value in parsed_data.items():
                    if key != '原始报文':
                        # 添加图标
                        icon = self.get_weather_icon(key)
                        html_content += f"<tr style='border-bottom: 1px solid #4C566A;'>"
                        html_content += f"<td style='padding: 8px; font-weight: bold; color: #E5E9F0; width: 180px;'>{icon} {key}</td>"
                        html_content += f"<td style='padding: 8px; color: #D8DEE9;'>{value}</td></tr>"
                html_content += "</table>"
                
                self.stats_panel.add_request(success=True)
            else:
                # 失败图标和消息
                html_content += f"<h3 style='color:#BF616A; margin: 0 0 10px 0;'>❌ {code} - 查询失败</h3>"
                html_content += f"<p style='color:#BF616A; margin: 0;'>未找到代码 {code} 的METAR数据。请检查代码是否正确。</p>"
                self.stats_panel.add_request(success=False)
            
            html_content += "</div>"
            
            # 最终更新进度条
            if hasattr(self, 'progress_bar') and self.progress_bar.isVisible():
                self.progress_bar.setValue(i + 1)
                QApplication.processEvents()
        
        # 添加总结信息
        summary_style = "background: linear-gradient(135deg, #5E81AC 0%, #81A1C1 100%); color: white; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center;"
        html_content += f"<div style='{summary_style}'>"
        html_content += f"<h3 style='margin: 0 0 5px 0;'>📈 查询统计</h3>"
        html_content += f"<p style='margin: 0;'>成功: {success_count} | 失败: {len(icao_codes) - success_count} | 总计: {len(icao_codes)} | 成功率: {(success_count/len(icao_codes)*100):.1f}%</p>"
        html_content += "</div>"
        
        html_content += "</div>"
        
        self.result_text.setHtml(html_content)
        self.status_bar.showMessage(f"查询完成: {success_count}/{len(icao_codes)} 成功", 5000)
        
        # 记录到日志
        log_entry = f"[{datetime.now().strftime('%H:%M:%S')}] 查询完成: {', '.join(icao_codes)} - 成功率 {(success_count/len(icao_codes)*100):.1f}%"
        self.log_text.append(log_entry)
        

        
    def get_weather_icon(self, key):
        """根据天气要素返回对应的图标"""
        icons = {
            '场站': '🛩️',
            '观测时间': '🕐',
            '风': '💨',
            '能见度': '👁️',
            '天气现象': '🌦️',
            '云况': '☁️',
            '温度/露点': '🌡️',
            '气压': '📊',
            '跑道视程': '🛬',
            '趋势预报': '📈',
            '近期天气': '🌧️',
            '风切变': '💨',
            '备注': '📝'
        }
        return icons.get(key, '📋')
     


if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        window = MetarApp()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        with open("error.log", "w") as f:
            f.write(f"An unhandled exception occurred: {datetime.now()}\n")
            f.write(traceback.format_exc())
