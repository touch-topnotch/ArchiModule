from enum import Enum, auto

class ProjectBehaviour:

    class Status(Enum):
        NOT_STARTED = auto()
        RUNNING = auto()
        INTERRUPTED = auto()
        COMPLETED = auto()

    status: Status = None
    def __init__(self, on_complete):
        self.on_complete = on_complete
        self.status = self.Status.NOT_STARTED
    def stop(self):
        pass
    def complete(self):
        self.on_complete(status=self.Status.COMPLETED)
    def interrupt(self):
        self.on_complete(status=self.Status.INTERRUPTED)
