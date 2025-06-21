import sys
import re
import time
import traceback
from datetime import datetime

import requests
import pytz
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QTextEdit, QLabel, QSplitter, QStatusBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor

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
    border-radius: 4px;
    padding: 8px;
    color: #ECEFF4;
}
QLineEdit:focus {
    border: 1px solid #88C0D0;
}
QPushButton {
    background-color: #5E81AC;
    color: #ECEFF4;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #81A1C1;
}
QPushButton:pressed {
    background-color: #88C0D0;
}
QTextEdit {
    background-color: #3B4252;
    border: 1px solid #4C566A;
    border-radius: 4px;
    color: #D8DEE9;
}
QLabel#titleLabel {
    font-size: 18px;
    font-weight: bold;
    color: #88C0D0;
    padding-bottom: 10px;
}
QStatusBar {
    background-color: #3B4252;
    color: #D8DEE9;
}
QSplitter::handle {
    background-color: #4C566A;
}
QSplitter::handle:hover {
    background-color: #5E81AC;
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
        unit = 'KT' if 'KT' in wind_code or is_trend else 'MPS'
        if 'VRB' in wind_code:
            speed = int(re.search(r'VRB(\d+)', wind_code).group(1))
            return f'风向不定, 风速 {speed}{unit}'
        direction = int(wind_code[0:3])
        if 'KT' in wind_code:
            speed = int(wind_code[3:5])
            gust_match = re.search(r'G(\d+)', wind_code)
            desc = f'风向 {direction}度, 风速 {speed}节'
            if gust_match:
                gust_speed = int(gust_match.group(1))
                desc += f', 阵风 {gust_speed}节'
            return desc
        if 'MPS' in wind_code:
            speed_mps = wind_code[4:]
            speed_desc = '>99米/秒' if 'P99' in speed_mps else f'{int(speed_mps)}米/秒'
            return f'风向 {direction}度, 风速 {speed_desc}'
        if is_trend:
            speed_match = re.search(r'(\d{2,3})(KT|MPS)', wind_code)
            if speed_match:
                speed = int(speed_match.group(1))
                unit_str = '节' if speed_match.group(2) == 'KT' else '米/秒'
                return f'风向 {direction}度, 风速 {speed}{unit_str}'
        return wind_code

    def parse(self, metar_line):
        if not metar_line: return []
        parts = {
            '原始报文': metar_line,
            '场站': '', '观测时间': '', '风': '', '能见度': '', '天气现象': '',
            '云况': '', '温度/露点': '', '气压': '', '跑道视程': '',
            '趋势预报': '', '近期天气': '', '风切变': '', '备注': ''
        }
        # The full parsing logic from the previous Tkinter app is integrated here.
        # This method now returns a dictionary of parsed parts.
        # 场站
        station_match = re.search(r'^([A-Z]{4})', metar_line)
        if station_match: parts['场站'] = station_match.group(1)

        # 时间
        time_match = re.search(r'(\d{2})(\d{2})(\d{2})Z', metar_line)
        if time_match: parts['观测时间'] = f'{time_match.group(1)}日 {time_match.group(2)}:{time_match.group(3)} UTC'

        # 风
        wind_match = re.search(r' (\d{5}(G\d{2,3})?KT|VRB\d{2,3}KT|\d{3}P(99|\d{2})MPS) ', metar_line)
        if wind_match:
            wind_code = wind_match.group(1)
            parts['风'] = f'{self.parse_wind(wind_code)} ({wind_code})'

        # 能见度
        vis_match = re.search(r' (\d{4}) ', metar_line)
        if vis_match: parts['能见度'] = f'{vis_match.group(1)}米'
        elif 'CAVOK' in metar_line: parts['能见度'] = 'CAVOK (云和能见度都良好)'

        # 天气现象
        weather_match = re.search(r' ((-|\+)?(VC)?(MI|BC|PR|DR|BL|SH|TS|FZ)?([A-Z]{2}|[A-Z]{4})+?) ', metar_line)
        if weather_match:
            full_code = weather_match.group(1)
            parts['天气现象'] = f'{self.translate_weather_phenomena(full_code)} ({full_code})'

        # 云
        cloud_matches = re.findall(r' (FEW|SCT|BKN|OVC)(\d{3})(CB|TCU)?', metar_line)
        if cloud_matches:
            cloud_info = ', '.join([
                f'{self.translate_cloud_cover(c[0])} at {int(c[1])*100}英尺' + (f' ({c[2]})' if c[2] else '')
                for c in cloud_matches
            ])
            parts['云况'] = cloud_info
        elif 'NSC' in metar_line:
            parts['云况'] = '无重要云 (NSC)'

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
        trend_part_match = re.search(r' (NOSIG|BECMG.+$|TEMPO.+$)', metar_line)
        if trend_part_match:
            trend_part = trend_part_match.group(1).strip()
            if 'NOSIG' in trend_part:
                parts['趋势预报'] = '无显著变化 (NOSIG)'
            else:
                trend_groups = re.split(r' (BECMG|TEMPO) ', ' ' + trend_part)[1:]
                full_trend_desc = []
                for i in range(0, len(trend_groups), 2):
                    trend_type = trend_groups[i]
                    trend_content = trend_groups[i+1].strip()
                    details = self.parse_trend(trend_type, trend_content)
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
        wind_match = re.search(r'(\d{5}G?\d{2,3}KT|VRB\d{2,3}KT|\d{5,8}MPS)', remaining_content)
        if wind_match:
            wind_code = wind_match.group(0)
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

        # 搜索栏
        search_layout = QHBoxLayout()
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("输入ICAO代码 (多个用逗号隔开)...")
        self.search_entry.returnPressed.connect(self.search_metar)
        search_button = QPushButton("查询")
        search_button.clicked.connect(self.search_metar)
        search_layout.addWidget(self.search_entry)
        search_layout.addWidget(search_button)
        main_layout.addLayout(search_layout)

        # 分割窗口
        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)

        # 结果显示区域
        result_widget = QWidget()
        result_layout = QVBoxLayout(result_widget)
        result_title = QLabel("METAR 解析结果")
        result_title.setObjectName("titleLabel")
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        result_layout.addWidget(result_title)
        result_layout.addWidget(self.result_text)
        splitter.addWidget(result_widget)

        # 日志显示区域
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_title = QLabel("系统日志")
        log_title.setObjectName("titleLabel")
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.log_text)
        splitter.addWidget(log_widget)

        splitter.setSizes([600, 200])

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

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

    def search_metar(self):
        query = self.search_entry.text().upper().strip()
        if not query:
            self.result_text.setHtml("<i style='color:#EBCB8B;'>请输入至少一个ICAO代码。</i>")
            return

        icao_codes = [code.strip() for code in query.split(',')]
        self.display_metar(icao_codes)

    def display_metar(self, icao_codes):
        html_content = ""
        for code in icao_codes:
            metar_line = self.downloader.metar_data.get(code)
            html_content += f"<h3 style='color:#8FBCBB;'>查询结果: {code}</h3>"
            if metar_line:
                parsed_data = self.parser.parse(metar_line)
                html_content += f"<p style='font-family:Consolas;color:#A3BE8C; margin-bottom: 10px;'>{parsed_data.get('原始报文', '')}</p>"
                html_content += "<table style='width:100%; border-collapse: collapse;'>"
                for key, value in parsed_data.items():
                    if key != '原始报文':
                        html_content += f"<tr><td style='padding: 4px; font-weight: bold; color: #E5E9F0; width: 150px;'>{key}</td><td style='padding: 4px; color: #D8DEE9;'>{value}</td></tr>"
                html_content += "</table>"
            else:
                html_content += f"<p style='color:#BF616A;'>未找到代码 {code} 的METAR数据。</p>"
            html_content += "<hr style='border-color: #4C566A;'>"
        self.result_text.setHtml(html_content)

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
