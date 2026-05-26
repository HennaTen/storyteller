import json
import queue

import requests
from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication


generateUrl = "http://localhost:5001/api/v1/generate"
tokenCountUrl = "http://localhost:5001/api/extra/tokencount"
headers = {
    "Content-Type": "application/json",
}


def _beep() -> None:
    app = QApplication.instance()
    if app is not None:
        app.beep()


class CountTask(QObject):
    def __init__(self, data, source):
        super(CountTask, self).__init__()
        self.data = data
        self.source = source

    def execute(self):
        response = requests.post(tokenCountUrl, headers=headers, data=json.dumps({"prompt": self.data}))
        if response.status_code == 200:
            response_data = json.loads(response.text)
            self.source.onTokensCounted(response_data["value"])
        else:
            self.source.onTokensCounted(-1)


class GenerateTask(QObject):
    def __init__(self, data, source):
        super(GenerateTask, self).__init__()
        self.data = data
        self.source = source

    def execute(self):
        prompt = json.dumps(
            {
                "prompt": self.data,
                "max_length": 1024,
            }
        )
        response = requests.post(generateUrl, headers=headers, data=prompt)
        if response.status_code == 200:
            response_data = json.loads(response.text)
            _beep()
            self.source.onResponseGenerated(response_data["results"][0]["text"].strip())
        else:
            self.source.onResponseGenerated("Error generating response")


class Worker(QObject):
    finished = pyqtSignal()

    def __init__(self):
        super(Worker, self).__init__()
        self.tasks = queue.Queue()

    @pyqtSlot(QObject)
    def addTask(self, task):
        self.tasks.put(task)
        if not worker_thread.isRunning():
            worker_thread.start()

    @pyqtSlot()
    def processNextTask(self):
        while not self.tasks.empty():
            task = self.tasks.get()
            task.execute()
        self.finished.emit()


worker_thread = QThread()
worker = Worker()
worker.moveToThread(worker_thread)
worker_thread.started.connect(worker.processNextTask)
worker.finished.connect(worker_thread.quit)
