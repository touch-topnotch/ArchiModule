# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2023                                                    *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import FreeCAD
import os
import traceback

# Module name for log messages
MODULE_NAME = "ArchiModule"


class LogLevel:
    """Enumeration of log levels for ArchiModule."""
    
    RESET = -1
    ERROR = 0
    WARNING = 1
    NOTICE = 2
    INFO = 3
    DEBUG = 4
    
    _names = {
        ERROR: "ERROR",
        WARNING: "WARNING",
        NOTICE: "NOTICE",
        INFO: "INFO",
        DEBUG: "DEBUG",
    }
    
    @classmethod
    def toString(cls, level):
        """Convert log level to string representation."""
        return cls._names.get(level, "UNKNOWN")


# Module configuration
_defaultLogLevel = LogLevel.NOTICE
_moduleLogLevel = {
    "ArchiModule": LogLevel.DEBUG,
}
_useConsole = True

# Initialize FreeCAD log level for ArchiModule
try:
    # Force print to stdout first to debug
    print("=== ArchiModule Log Initialization ===")
    
    # Set FreeCAD log level for ArchiModule to show all messages
    FreeCAD.setLogLevel("ArchiModule", "Trace")  # This enables all log levels
    print(f"Set ArchiModule log level to Trace")
    
    # Force refresh to apply changes
    print("Console refreshed")
    
    # Test immediate logging
    FreeCAD.Console.PrintMessage("=== ArchiModule Console Test ===\n")
    FreeCAD.Console.PrintLog("=== ArchiModule Log Test ===\n")
    FreeCAD.Console.PrintWarning("=== ArchiModule Warning Test ===\n")
    FreeCAD.Console.PrintError("=== ArchiModule Error Test ===\n")
    
    print("=== ArchiModule Log Initialization Complete ===")
    
except Exception as e:
    # Print to stdout if FreeCAD console is not available
    print(f"ArchiModule log initialization warning: {e}")
    print("Logs will be printed to stdout instead of FreeCAD console")
    import traceback
    traceback.print_exc()

def checkLogStatus():
    """Check the current log status of FreeCAD console."""
    print("=== FreeCAD Console Status ===")
    print(f"ArchiModule log level: {FreeCAD.getLogLevel('ArchiModule')}")
    print(f"Default log level: {FreeCAD.getLogLevel('Default')}")
    print(f"DebugDefault log level: {FreeCAD.getLogLevel('DebugDefault')}")
    print("=== FreeCAD Console Status Complete ===")


def logToConsole(yes=True):
    """Set whether to log to FreeCAD console or standard output.
    
    Args:
        yes (bool): If True (default), use FreeCAD console. Otherwise use stdout.
    """
    global _useConsole
    _useConsole = yes


def setLevel(level, module=None):
    """Set the logging level globally or for specific module.
    
    Args:
        level (LogLevel): The log level to set
        module (str, optional): Module name. If None, sets global default level.
    """
    global _defaultLogLevel
    global _moduleLogLevel
    
    if module:
        if level == LogLevel.RESET:
            if module in _moduleLogLevel:
                del _moduleLogLevel[module]
        else:
            _moduleLogLevel[module] = level
            
        # Also update FreeCAD log level
        try:
            if level == LogLevel.RESET:
                FreeCAD.setLogLevel(module, "Default")
            elif level == LogLevel.ERROR:
                FreeCAD.setLogLevel(module, "Error")
            elif level == LogLevel.WARNING:
                FreeCAD.setLogLevel(module, "Warning")
            elif level == LogLevel.NOTICE:
                FreeCAD.setLogLevel(module, "Message")
            elif level == LogLevel.INFO:
                FreeCAD.setLogLevel(module, "Message")
            elif level == LogLevel.DEBUG:
                FreeCAD.setLogLevel(module, "Log")
        except:
            pass  # Ignore if FreeCAD is not available
    else:
        if level == LogLevel.RESET:
            _defaultLogLevel = LogLevel.NOTICE
            _moduleLogLevel = {}
        else:
            _defaultLogLevel = level


def getLevel(module=None):
    """Get the current log level for a module or the global default.
    
    Args:
        module (str, optional): Module name. If None, returns global default level.
    
    Returns:
        int: The log level
    """
    # If a specific module level is set, use it
    if module and module in _moduleLogLevel:
        return _moduleLogLevel[module]
    
    # Fall back to ArchiModule-wide level if defined
    if MODULE_NAME in _moduleLogLevel:
        return _moduleLogLevel[MODULE_NAME]
    
    # Finally, fall back to global default
    return _defaultLogLevel


def _caller():
    """Internal function to determine the calling module."""
    filename, line, func, _ = traceback.extract_stack(limit=3)[0]
    return os.path.splitext(os.path.basename(filename))[0], line, func


def _log(level, module_line_func, msg):
    """Internal function to handle logging.
    
    Args:
        level (LogLevel): Log level for this message
        module_line_func (tuple): (module, line, function) information
        msg (str): Message to log
    
    Returns:
        str: The logged message or None if not logged due to level settings
    """
    module, line, func = module_line_func
    
    if getLevel(module) >= level:
        message = f"{MODULE_NAME}.{module}.{LogLevel.toString(level)}: {msg}"
        
        # Always print to stdout for debugging
        # print(f"[STDOUT] {message}")
        
        if _useConsole:
            message += "\n"
            try:
                if level == LogLevel.NOTICE:
                    FreeCAD.Console.PrintLog(message)
                elif level == LogLevel.WARNING:
                    FreeCAD.Console.PrintWarning(message)
                elif level == LogLevel.ERROR:
                    FreeCAD.Console.PrintError(message)
                else:
                    FreeCAD.Console.PrintMessage(message)
            except Exception as e:
                print(f"[STDOUT] Failed to log to FreeCAD console: {e}")
        else:
            print(message)
        return message
    return None


def debug(msg):
    """Log a debug message.
    
    Args:
        msg (str): Debug message to log
    """
    caller_info = _caller()
    _, line, _ = caller_info
    msg = f"({line}) - {msg}"
    return _log(LogLevel.DEBUG, caller_info, msg)


def info(msg):
    """Log an info message.
    
    Args:
        msg (str): Info message to log
    """
    return _log(LogLevel.INFO, _caller(), msg)


def notice(msg):
    """Log a notice message.
    
    Args:
        msg (str): Notice message to log
    """
    return _log(LogLevel.NOTICE, _caller(), msg)


def warning(msg):
    """Log a warning message.
    
    Args:
        msg (str): Warning message to log
    """
    return _log(LogLevel.WARNING, _caller(), msg)


def error(msg):
    """Log an error message.
    
    Args:
        msg (str): Error message to log
    """
    return _log(LogLevel.ERROR, _caller(), msg)


