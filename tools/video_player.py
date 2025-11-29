"""
Video player widget wrapper using C++ ArchiGui.VideoPlayerWidget
"""
import os
import shutil
import subprocess
import tempfile
from typing import Optional

import FreeCAD
import FreeCADGui

try:
    from PySide.QtCore import Qt
    from PySide.QtWidgets import QWidget, QVBoxLayout, QMessageBox, QLabel
    from PySide import shiboken
except ImportError:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QMessageBox, QLabel
    try:
        import shiboken6 as shiboken
    except ImportError:
        shiboken = None

# Import C++ video player
try:
    import ArchiGui
    HAS_CPP_PLAYER = True
except ImportError:
    HAS_CPP_PLAYER = False
    FreeCAD.Console.PrintWarning("ArchiGui C++ module not found, video player unavailable\\n")


class VideoPlayerWidget(QWidget):
    """Python wrapper for C++ VideoPlayerWidget using shiboken6.wrapInstance"""
    
    def __init__(self, video_path=None, on_frame_added=None, parent=None):
        super().__init__(parent)
        self._video_path = video_path
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        if not HAS_CPP_PLAYER:
            # Fallback UI
            label = QLabel("Video player unavailable: ArchiGui C++ module not loaded")
            label.setStyleSheet("color: red; padding: 20px;")
            layout.addWidget(label)
            self.setLayout(layout)
            return
        
        if not shiboken:
            # Fallback if shiboken not available
            label = QLabel("Video player unavailable: shiboken6 not found")
            label.setStyleSheet("color: red; padding: 20px;")
            layout.addWidget(label)
            self.setLayout(layout)
            return
        
        try:
            # Create C++ player instance
            self._cpp_player = ArchiGui.VideoPlayerWidget()
            
            # Get the QWidget* pointer as integer
            widget_ptr = self._cpp_player.getWidget()
            
            if widget_ptr:
                # Wrap the C++ QWidget pointer with shiboken
                self.video_widget = shiboken.wrapInstance(int(widget_ptr), QWidget)
                
                # Add to layout
                layout.addWidget(self.video_widget)
                
                # Load video if path provided
                if video_path:
                    self._cpp_player.loadVideo(video_path)
            else:
                label = QLabel("Failed to get widget from C++ player")
                label.setStyleSheet("color: red; padding: 20px;")
                layout.addWidget(label)
                
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to create video player: {e}\\n")
            label = QLabel(f"Video player error: {e}")
            label.setStyleSheet("color: red; padding: 20px;")
            layout.addWidget(label)
        
        self.setLayout(layout)
    
    def play(self):
        """Start or resume playback"""
        if HAS_CPP_PLAYER and hasattr(self, '_cpp_player'):
            self._cpp_player.play()
    
    def pause(self):
        """Pause playback"""
        if HAS_CPP_PLAYER and hasattr(self, '_cpp_player'):
            self._cpp_player.pause()
    
    def stop(self):
        """Stop playback"""
        if HAS_CPP_PLAYER and hasattr(self, '_cpp_player'):
            self._cpp_player.stop()
    
    def set_controls_visible(self, visible: bool):
        """Show or hide native playback controls"""
        if HAS_CPP_PLAYER and hasattr(self, '_cpp_player'):
            try:
                self._cpp_player.setControlsVisible(bool(visible))
            except AttributeError:
                pass
    
    def set_auto_loop(self, loop: bool):
        """Enable or disable automatic looping"""
        if HAS_CPP_PLAYER and hasattr(self, '_cpp_player'):
            try:
                self._cpp_player.setAutoLoop(bool(loop))
            except AttributeError:
                pass

    def current_position(self) -> int:
        """Return current playback position in milliseconds."""
        if HAS_CPP_PLAYER and hasattr(self, '_cpp_player'):
            try:
                return int(self._cpp_player.position())
            except Exception:
                return 0
        return 0

    def capture_frame(self) -> Optional[str]:
        """Capture current frame to a temporary file."""
        if not HAS_CPP_PLAYER or not hasattr(self, '_cpp_player'):
            return None
        if not self._video_path or not os.path.exists(self._video_path):
            return None
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            FreeCAD.Console.PrintWarning("ffmpeg not found, cannot capture frame\n")
            return None
        position = self.current_position()
        timestamp = max(position / 1000.0, 0.0)
        temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        temp_file.close()
        cmd = [
            ffmpeg,
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            self._video_path,
            "-frames:v",
            "1",
            temp_file.name,
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as exc:
            FreeCAD.Console.PrintError(f"Failed to capture frame: {exc}\n")
            try:
                os.remove(temp_file.name)
            except OSError:
                pass
            return None
        return temp_file.name
    
    def closeEvent(self, event):
        """Cleanup on close"""
        if HAS_CPP_PLAYER and hasattr(self, '_cpp_player'):
            try:
                self._cpp_player.stop()
            except:
                pass
        super().closeEvent(event)
