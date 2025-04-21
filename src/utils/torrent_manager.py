import libtorrent as lt
import time
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable

@dataclass
class TorrentStatus:
    updated_at: int
    bytes_total: int 
    bytes_done: int
    progress: float
    state: str
    speed: float

class TorrentManager:
    def __init__(self):
        self.session = lt.session()
        self.session.listen_on(6881, 6891)
        self.handle = None
        self.logger = logging.getLogger('TorrentManager')
        self._status_callback = None
        
    def start_download(self, torrent_path: str, save_path: str, 
                      trackers: list = None,
                      status_callback=None):
        try:
            # Загружаем торрент файл
            info = lt.torrent_info(torrent_path)
            
            # Добавляем трекеры если указаны
            if trackers:
                for tracker in trackers:
                    info.add_tracker(tracker)
                    
            # Создаем handle
            self.handle = self.session.add_torrent({
                'ti': info,
                'save_path': save_path
            })
            
            # Запускаем мониторинг
            self._monitor_download(status_callback)
            
        except Exception as e:
            self.logger.error(f"Error starting download: {e}")
            raise
            
    def _monitor_download(self, status_callback):
        """Отслеживает прогресс загрузки"""
        while not self.handle.is_seed():
            s = self.handle.status()
            
            status = TorrentStatus(
                updated_at=int(time.time()),
                bytes_total=s.total_wanted,
                bytes_done=s.total_wanted_done, 
                progress=s.progress * 100,
                state=self._get_state(s.state),
                speed=s.download_rate
            )
            
            if status_callback:
                status_callback(status)
                
            time.sleep(1)
            
    def _get_state(self, state):
        """Возвращает текстовое состояние загрузки"""
        states = {
            lt.torrent_status.checking_files: "checking",
            lt.torrent_status.downloading_metadata: "dl metadata",
            lt.torrent_status.downloading: "progress",
            lt.torrent_status.finished: "finished",
            lt.torrent_status.seeding: "seeding",
            lt.torrent_status.allocating: "allocating",
            lt.torrent_status.checking_resume_data: "checking resume"
        }
        return states.get(state, "progress") 

    def add_torrent(self, torrent_path: str = None, magnet_uri: str = None):
        """Добавляет торрент из файла или магнет-ссылки"""
        if torrent_path:
            info = lt.torrent_info(torrent_path)
            return self.session.add_torrent({'ti': info})
        elif magnet_uri:
            return self.session.add_torrent({'url': magnet_uri})
        else:
            raise ValueError("Необходимо указать torrent_path или magnet_uri")

    def check_files(self):
        """Запускает проверку файлов"""
        if self.handle:
            self.handle.force_recheck()

    def get_files(self):
        """Возвращает список файлов в торренте"""
        if not self.handle or not self.handle.has_metadata():
            return []
            
        files = []
        torrent_info = self.handle.get_torrent_info()
        
        for f in torrent_info.files():
            files.append({
                'path': f.path,
                'size': f.size,
                'progress': 0  # Будет обновляться в _monitor_download
            })
        return files 